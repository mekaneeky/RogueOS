
from __future__ import annotations
import sys
from pathlib import Path
from roguefs_core.worldgen import generate_room
from roguefs_core.index import IndexDB
from rogueos_tui.app import run_ui

def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py /path/to/root"); raise SystemExit(1)
    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print("Root must be an existing directory."); raise SystemExit(1)
    db = IndexDB()
    generate_room(db, root, parent_id=None)
    run_ui(root)

if __name__ == "__main__":
    main()
