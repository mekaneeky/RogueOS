
from __future__ import annotations
from .index import IndexDB
from .node import NodeKind

def by_type(db: IndexDB, dir_id: str, typ: str):
    return [r["id"] for r in db.children_of(dir_id) if r["kind"] == typ]
