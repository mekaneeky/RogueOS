from __future__ import annotations

import argparse
import json
import logging
import socketserver
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from roguefs_core.hashing import node_id_for_path
from roguefs_core.index import IndexDB
from roguefs_core.node import NodeKind
from roguefs_core.worldgen import ensure_space_for_dir, generate_room


LOG = logging.getLogger("rogueos.web")


class RogueState:
    """Small helper that keeps the shared DB connection and exposes helpers for the handler."""

    def __init__(self, root: Path):
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Root '{root}' must be an existing directory")
        self.root = root.resolve()
        self.db = IndexDB(check_same_thread=False)
        self.root_id = node_id_for_path(self.root)
        generate_room(self.db, self.root, parent_id=None)
        ensure_space_for_dir(self.db, self.root_id)

    def close(self):
        try:
            self.db.close()
        except Exception:
            LOG.exception("Failed to close IndexDB cleanly")

    def _display_name(self, row) -> str:
        path = Path(row["path"])
        if path.name:
            return path.name
        return str(path)

    def _ensure_directory(self, node_id: str):
        row = self.db.get_node(node_id)
        if not row:
            return None
        if row["kind"] != NodeKind.DIRECTORY.value:
            return row
        dir_path = Path(row["path"])
        parent_id = row["parent"]
        generate_room(self.db, dir_path, parent_id=parent_id)
        ensure_space_for_dir(self.db, node_id)
        return row

    def _breadcrumbs(self, start_id: str):
        crumbs = []
        current = self.db.get_node(start_id)
        guard = 0
        while current is not None and guard < 128:
            crumbs.append({
                "id": current["id"],
                "name": self._display_name(current),
                "path": current["path"],
            })
            parent_row = self.db.parent_of(current["id"])
            current = parent_row
            guard += 1
        crumbs.reverse()
        return crumbs

    def _transform_dict(self, node_id: str):
        transform = self.db.get_transform(node_id)
        if transform is None:
            return None
        return {
            "position": {"x": transform.x, "y": transform.y, "z": transform.z},
            "rotation": {"x": transform.rx, "y": transform.ry, "z": transform.rz, "w": transform.rw},
            "scale": {"x": transform.sx, "y": transform.sy, "z": transform.sz},
        }

    def _space_dict(self, node_id: str):
        rec = self.db.get_space(node_id)
        if rec is None:
            return None
        return {
            "origin": {"x": rec["ox"], "y": rec["oy"], "z": rec["oz"]},
            "size": {"x": rec["sx"], "y": rec["sy"], "z": rec["sz"]},
        }

    def node_payload(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": self._display_name(row),
            "path": row["path"],
            "kind": row["kind"],
            "seed": row["seed"],
            "theme": row["theme"],
            "parent": row["parent"],
            "transform": self._transform_dict(row["id"]),
            "pinned": self.db.is_pinned(row["id"]),
        }

    def dir_payload(self, node_id: str):
        row = self._ensure_directory(node_id)
        if not row:
            return None
        space = self._space_dict(node_id)
        children = []
        for child in self.db.children_of(node_id):
            payload = self.node_payload(child)
            if child["kind"] == NodeKind.DIRECTORY.value:
                payload["childCount"] = len(self.db.children_of(child["id"]))
            children.append(payload)
        return {
            "id": row["id"],
            "name": self._display_name(row),
            "path": row["path"],
            "kind": row["kind"],
            "parent": row["parent"],
            "space": space,
            "breadcrumbs": self._breadcrumbs(node_id),
            "children": children,
        }

    def search_payload(self, needle: str, limit: int = 25):
        results = []
        for row in self.db.search_paths_like(needle, limit=limit):
            results.append(self.node_payload(row))
        return {"results": results}


class RogueRequestHandler(SimpleHTTPRequestHandler):
    """Serve the static Three.js app and a tiny JSON API backed by IndexDB."""

    def __init__(self, *args, state: RogueState, **kwargs):
        self.state = state
        super().__init__(*args, **kwargs)

    def _write_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_api(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/root":
            LOG.info("API /api/root")
            payload = self.state.dir_payload(self.state.root_id)
            if payload is None:
                self._write_json({"error": "root directory missing"}, HTTPStatus.NOT_FOUND)
                return
            self._write_json(payload)
            return
        if parsed.path == "/api/dir":
            node_id = query.get("id", [None])[0]
            LOG.info("API /api/dir id=%s", node_id)
            if not node_id:
                self._write_json({"error": "missing id parameter"}, HTTPStatus.BAD_REQUEST)
                return
            payload = self.state.dir_payload(node_id)
            if payload is None:
                self._write_json({"error": "directory not found"}, HTTPStatus.NOT_FOUND)
                return
            self._write_json(payload)
            return
        if parsed.path == "/api/search":
            needle = query.get("q", [""])[0]
            limit = query.get("limit", [None])[0]
            try:
                limit_val = int(limit) if limit else 25
            except ValueError:
                limit_val = 25
            payload = self.state.search_payload(needle, limit=max(1, min(limit_val, 200)))
            LOG.info("API /api/search q=%s count=%d", needle, len(payload["results"]))
            self._write_json(payload)
            return
        LOG.info("API unknown path=%s", parsed.path)
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._handle_api()
            return
        super().do_GET()

    def log_message(self, format, *args):  # noqa: A003 - SimpleHTTPRequestHandler interface
        LOG.info("%s - - %s", self.client_address[0], format % args)


def create_server(root: Path, host: str = "127.0.0.1", port: int = 8765, static_dir: Path | None = None):
    """Create and configure the HTTP server but do not start it."""
    static_path = static_dir or (Path(__file__).parent / "static")
    state = RogueState(root)
    handler = partial(RogueRequestHandler, state=state, directory=str(static_path))
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer((host, port), handler)
    except Exception:
        state.close()
        raise
    return httpd, state


def shutdown_server(httpd: socketserver.TCPServer, state: RogueState | None):
    """Gracefully stop server and release state resources."""
    if httpd:
        try:
            httpd.shutdown()
        except Exception:
            LOG.exception("Error while shutting down HTTP server")
        try:
            httpd.server_close()
        except Exception:
            LOG.exception("Error while closing HTTP server socket")
    if state:
        state.close()


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765):
    """Entry point that starts the HTTP server."""
    static_dir = Path(__file__).parent / "static"
    httpd, state = create_server(root, host=host, port=port, static_dir=static_dir)
    actual_host, actual_port = httpd.server_address
    LOG.info("Serving RogueOS web renderer at http://%s:%d", actual_host, actual_port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Received interrupt, shutting down.")
    finally:
        shutdown_server(httpd, state)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="RogueOS Three.js renderer")
    parser.add_argument("root", type=Path, help="Path to the directory to visualise")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    try:
        serve(args.root, host=args.host, port=args.port)
    except ValueError as exc:
        LOG.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
