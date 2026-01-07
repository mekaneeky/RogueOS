
from __future__ import annotations
import os
from pathlib import Path
from .node import NodeKind
from .hashing import node_id_for_path

def iter_children(path: Path):
    try:
        with os.scandir(path) as it:
            for entry in it:
                p = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    yield (node_id_for_path(p), p, NodeKind.DIRECTORY)
                elif entry.is_symlink():
                    yield (node_id_for_path(p), p, NodeKind.SYMLINK)
                else:
                    yield (node_id_for_path(p), p, NodeKind.FILE)
    except PermissionError:
        return
