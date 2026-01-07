
from __future__ import annotations
import os, sqlite3, time, sys
from pathlib import Path
from typing import Optional
from .node import Transform, transform_to_tuple, transform_from_tuple, NodeKind

DEFAULT_DB = os.path.expanduser("~/.roguefs/index.sqlite")
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, path TEXT NOT NULL, kind TEXT NOT NULL, parent TEXT, seed TEXT, theme TEXT, last_seen REAL);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent);
CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE TABLE IF NOT EXISTS transforms (id TEXT PRIMARY KEY, x REAL,y REAL,z REAL, rx REAL,ry REAL,rz REAL,rw REAL, sx REAL,sy REAL,sz REAL);
CREATE TABLE IF NOT EXISTS spaces (id TEXT PRIMARY KEY, ox REAL,oy REAL,oz REAL, sx REAL,sy REAL,sz REAL);
CREATE TABLE IF NOT EXISTS pins (id TEXT PRIMARY KEY, pinned INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS visits (id TEXT PRIMARY KEY, count INTEGER DEFAULT 0, last REAL);
"""

def _ensure_parent(path: str):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

class IndexDB:
    def __init__(self, path: Optional[str] = None, *, check_same_thread: bool = True):
        wanted = path or os.environ.get("ROGUEFS_DB", DEFAULT_DB)
        try:
            _ensure_parent(wanted)
            self._conn = sqlite3.connect(wanted, check_same_thread=check_same_thread)
        except Exception as e:
            fallback_dir = os.path.abspath("./.roguefs")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback = os.path.join(fallback_dir, "index.sqlite")
            print(f"[IndexDB] Could not open DB at '{wanted}' ({e}). Falling back to '{fallback}'.", file=sys.stderr)
            self._conn = sqlite3.connect(fallback, check_same_thread=check_same_thread)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(SCHEMA)

    def upsert_node(self, id: str, path: Path, kind: NodeKind, parent: Optional[str], seed: Optional[str], theme: Optional[str] = None):
        now = time.time()
        with self._conn:
            self._conn.execute(
                "INSERT INTO nodes(id,path,kind,parent,seed,theme,last_seen) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET path=excluded.path, kind=excluded.kind, parent=excluded.parent, seed=excluded.seed, theme=excluded.theme, last_seen=?",
                (id, str(path), kind.value, parent, seed, theme, now, now)
            )

    def get_node(self, id: str):
        return self._conn.execute("SELECT * FROM nodes WHERE id=?", (id,)).fetchone()

    def get_node_by_path(self, path: Path):
        return self._conn.execute("SELECT * FROM nodes WHERE path=?", (str(path),)).fetchone()

    def children_of(self, parent_id: str):
        return self._conn.execute("SELECT * FROM nodes WHERE parent=? ORDER BY path", (parent_id,)).fetchall()

    def parent_of(self, id: str):
        row = self.get_node(id); 
        if not row: return None
        pid = row["parent"]; 
        return None if not pid else self.get_node(pid)

    def set_transform(self, id: str, t: Transform):
        with self._conn:
            self._conn.execute(
                "INSERT INTO transforms(id,x,y,z,rx,ry,rz,rw,sx,sy,sz) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET x=excluded.x,y=excluded.y,z=excluded.z,rx=excluded.rx,ry=excluded.ry,rz=excluded.rz,rw=excluded.rw,sx=excluded.sx,sy=excluded.sy,sz=excluded.sz",
                (id, *transform_to_tuple(t))
            )

    def get_transform(self, id: str):
        r = self._conn.execute("SELECT * FROM transforms WHERE id=?", (id,)).fetchone()
        return None if not r else transform_from_tuple((r["x"],r["y"],r["z"],r["rx"],r["ry"],r["rz"],r["rw"],r["sx"],r["sy"],r["sz"]))

    def set_space(self, id: str, origin=(0.0,0.0,0.0), size=(40.0,20.0,8.0)):
        with self._conn:
            self._conn.execute(
                "INSERT INTO spaces(id,ox,oy,oz,sx,sy,sz) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET ox=excluded.ox,oy=excluded.oy,oz=excluded.oz,sx=excluded.sx,sy=excluded.sy,sz=excluded.sz",
                (id, origin[0],origin[1],origin[2], size[0],size[1],size[2])
            )

    def get_space(self, id: str):
        return self._conn.execute("SELECT * FROM spaces WHERE id=?", (id,)).fetchone()

    def is_pinned(self, id: str) -> bool:
        r = self._conn.execute("SELECT * FROM pins WHERE id=?", (id,)).fetchone()
        return bool(r and r["pinned"])

    def toggle_pin(self, id: str) -> bool:
        with self._conn:
            r = self._conn.execute("SELECT * FROM pins WHERE id=?", (id,)).fetchone()
            if r:
                self._conn.execute("DELETE FROM pins WHERE id=?", (id,))
                return False
            else:
                self._conn.execute("INSERT INTO pins(id,pinned) VALUES(?,1)", (id,))
                return True

    def visit(self, id: str):
        now = time.time()
        with self._conn:
            r = self._conn.execute("SELECT * FROM visits WHERE id=?", (id,)).fetchone()
            if r:
                self._conn.execute("UPDATE visits SET count=count+1,last=? WHERE id=?", (now,id))
            else:
                self._conn.execute("INSERT INTO visits(id,count,last) VALUES(?,?,?)", (id,1,now))

    def search_paths_like(self, needle: str, limit: int = 50):
        q = f"%{needle}%"
        return self._conn.execute("SELECT * FROM nodes WHERE path LIKE ? ORDER BY path LIMIT ?", (q, limit)).fetchall()

    def remove_missing_children(self, parent_id: str, existing_paths: set[str]):
        cur = self._conn.execute("SELECT id,path FROM nodes WHERE parent=?", (parent_id,))
        to_remove = [r["id"] for r in cur.fetchall() if r["path"] not in existing_paths]
        with self._conn:
            for nid in to_remove:
                self._conn.execute("DELETE FROM transforms WHERE id=?", (nid,))
                self._conn.execute("DELETE FROM nodes WHERE id=?", (nid,))

    def close(self):
        self._conn.close()
