
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
from .index import IndexDB
from .node import NodeKind

class LocationSystem:
    def __init__(self, db: IndexDB, root: Path):
        self.db = db; self.root = root

    def get_current_dir(self, node_id: str) -> Optional[str]:
        row = self.db.get_node(node_id); 
        if not row: return None
        return row["id"] if row["kind"] == NodeKind.DIRECTORY.value else row["parent"]

    def siblings(self, dir_id: str) -> List[str]:
        p = self.db.parent_of(dir_id); 
        if not p: return []
        return [r["id"] for r in self.db.children_of(p["id"]) if r["kind"] == NodeKind.DIRECTORY.value]

    def up(self, dir_id: str) -> Optional[str]:
        p = self.db.parent_of(dir_id); return None if not p else p["id"]

    def down(self, dir_id: str, child_dir_id: str) -> Optional[str]:
        ch = [c["id"] for c in self.db.children_of(dir_id) if c["id"] == child_dir_id and c["kind"] == NodeKind.DIRECTORY.value]
        return child_dir_id if ch else None
