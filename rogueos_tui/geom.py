
from __future__ import annotations
from typing import Dict, Tuple, List
from roguefs_core.index import IndexDB
from roguefs_core.node import NodeKind

def calc_interior_dims(term_w: int, term_h: int):
    cols = max(8, term_w - 2)
    rows = max(6, term_h - 4)
    x0 = 1; y0 = 1
    return cols, rows, x0, y0

def world_to_grid(db: IndexDB, dir_id: str, x: float, y: float, cols: int, rows: int) -> Tuple[int,int]:
    space = db.get_space(dir_id)
    W = max(1e-6, space["sx"]); H = max(1e-6, space["sy"])
    gx = int((x + W/2) / W * (cols-2))  # interior
    gy = int((y + H/2) / H * (rows-2))
    gx = max(0, min(cols-3, gx))
    gy = max(0, min(rows-3, gy))
    return gx, gy

def place_no_collision(occ: Dict[Tuple[int,int], str], gx: int, gy: int, cols: int, rows: int) -> Tuple[int,int]:
    if (gx, gy) not in occ:
        return gx, gy
    radius = 1
    while radius < max(cols, rows):
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                x = gx + dx; y = gy + dy
                if 0 <= x < (cols-2) and 0 <= y < (rows-2) and (x, y) not in occ:
                    return x, y
        radius += 1
    return gx, gy

def build_items_map(db: IndexDB, dir_id: str, cols: int, rows: int):
    children = db.children_of(dir_id)
    occ: Dict[Tuple[int,int], str] = {}
    items: List[Tuple[str, str, int, int]] = []  # (id, kind, gx, gy) in interior coords
    for c in children:
        t = db.get_transform(c["id"])
        if not t: continue
        gx, gy = world_to_grid(db, dir_id, t.x, t.y, cols, rows)
        gx, gy = place_no_collision(occ, gx, gy, cols, rows)
        occ[(gx, gy)] = c["id"]
        items.append((c["id"], c["kind"], gx, gy))
    return items, occ
