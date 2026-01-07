from __future__ import annotations

import argparse
from pathlib import Path

from rogueos_web.server import serve


def main():
    parser = argparse.ArgumentParser(description="Launch the RogueOS Three.js renderer")
    parser.add_argument("root", type=Path, help="Directory to explore")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit("Root must be an existing directory.")

    serve(root, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
