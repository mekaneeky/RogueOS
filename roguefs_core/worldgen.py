
from __future__ import annotations
import random, json
from pathlib import Path
from typing import List
from .index import IndexDB
from .node import NodeKind, Transform, Space
from .scanner import iter_children
from .hashing import seed_for_node_id, node_id_for_path, hash_hex
from .layout import choose_layout, phyllotaxis_positions, grid_blue_noise, bucketed_grid, chamber_cells
from .config import load_config, save_config, ensure_child_metadata

def _virtual_node_id(dir_id: str, category: str, name: str) -> str:
    key = f"virtual:{dir_id}:{category}:{name}"
    return hash_hex(key.encode("utf-8"))

def _virtual_path(dir_path: Path, category: str, name: str) -> Path:
    safe = name.replace(" ", "_")
    return dir_path / f".rogueos::{category}::{safe}"

def _sync_parent_config(dir_path: Path, parent_id: str | None):
    if parent_id is None:
        return
    parent_path = dir_path.parent
    cfg = load_config(parent_path)
    before = json.dumps(cfg, sort_keys=True)
    ensure_child_metadata(cfg, dir_path.name, access="stairs")
    if json.dumps(cfg, sort_keys=True) != before:
        save_config(parent_path, cfg)

def ensure_space_for_dir(db: IndexDB, dir_id: str):
    if db.get_space(dir_id) is None:
        db.set_space(dir_id, origin=(0.0,0.0,0.0), size=(40.0,20.0,8.0))

def _scatter_layout(db: IndexDB, dir_id: str, ids: List[str], width: float, height: float, salt: str):
    if not ids:
        return
    seed = seed_for_node_id(dir_id, salt)
    rng = random.Random(seed)
    n = len(ids)
    layout_kind = choose_layout(n)
    if layout_kind == "phyllo":
        pts = phyllotaxis_positions(n, radius=min(width, height)/2.5)
    elif layout_kind == "blue":
        pts = grid_blue_noise(n, width=width*0.9, height=height*0.9, min_dist=2.0, rng=rng)
    else:
        pts = bucketed_grid(n, width=width*0.9, height=height*0.9)
    for idx, cid in enumerate(ids):
        x, y = pts[idx]
        db.set_transform(cid, Transform(x=x, y=y, z=0.0))

def generate_room(db: IndexDB, dir_path: Path, parent_id: str | None):
    cfg = load_config(dir_path)
    if parent_id is None:
        cfg["type"] = "level"
    else:
        cfg.setdefault("type", "room")
    presentation = cfg.get("presentation", "hall")
    _sync_parent_config(dir_path, parent_id)
    dir_id = node_id_for_path(dir_path)
    db.upsert_node(dir_id, dir_path, NodeKind.DIRECTORY, parent_id, seed=None, theme="room")
    ensure_space_for_dir(db, dir_id)

    children = list(iter_children(dir_path))
    existing_paths = set(str(p) for _,p,_ in children)
    for _, path, kind in children:
        if kind == NodeKind.DIRECTORY:
            ensure_child_metadata(cfg, path.name, access="stairs")

    containers = cfg.get("containers", {})
    npcs = cfg.get("npcs", {})
    for name in containers.keys():
        existing_paths.add(str(_virtual_path(dir_path, "container", name)))
    for name, meta in npcs.items():
        if meta.get("present"):
            existing_paths.add(str(_virtual_path(dir_path, "npc", name)))

    db.remove_missing_children(dir_id, existing_paths)

    child_ids: List[str] = []
    sorted_children = sorted(children, key=lambda t: t[1].name.lower())
    dir_children: List[tuple[str, Path]] = []
    other_children: List[tuple[str, Path, NodeKind]] = []
    for cid, p, kind in sorted_children:
        db.upsert_node(cid, p, kind, dir_id, seed=None, theme=None)
        child_ids.append(cid)
        if kind == NodeKind.DIRECTORY:
            dir_children.append((cid, p))
        else:
            other_children.append((cid, p, kind))

    # Virtual containers from config
    for name, meta in containers.items():
        node_id = _virtual_node_id(dir_id, "container", name)
        vpath = _virtual_path(dir_path, "container", name)
        db.upsert_node(node_id, vpath, NodeKind.CONTAINER, dir_id, seed=name, theme=meta.get("type"))
        existing_paths.add(str(vpath))
        if node_id not in child_ids:
            child_ids.append(node_id)
            other_children.append((node_id, vpath, NodeKind.CONTAINER))

    # NPCs
    for name, meta in npcs.items():
        if not meta.get("present"):
            continue
        node_id = _virtual_node_id(dir_id, "npc", name)
        vpath = _virtual_path(dir_path, "npc", name)
        db.upsert_node(node_id, vpath, NodeKind.NPC, dir_id, seed=name, theme=name)
        existing_paths.add(str(vpath))
        if node_id not in child_ids:
            child_ids.append(node_id)
            other_children.append((node_id, vpath, NodeKind.NPC))

    space_rec = db.get_space(dir_id); width=space_rec["sx"]; height=space_rec["sy"]

    if presentation == "chambers" and dir_children:
        cells = chamber_cells(len(dir_children))
        for (cid, path), cell in zip(dir_children, cells):
            cx, cy = cell["center"]
            # Map normalized coordinates to world space [-width/2, width/2]
            wx = (cx - 0.5) * width
            wy = (cy - 0.5) * height
            db.set_transform(cid, Transform(x=wx, y=wy, z=0.0))
            meta = cfg.setdefault("children", {}).setdefault(path.name, {})
            meta.setdefault("door_side", cell["door_side"])
        _scatter_layout(db, dir_id, [cid for cid, _, _ in other_children], width, height, "layout_v1_others")
    else:
        _scatter_layout(db, dir_id, child_ids, width, height, "layout_v1")

    save_config(dir_path, cfg)

def reflow_room(db: IndexDB, dir_id: str, include_pins: bool = False):
    row = db.get_node(dir_id)
    if not row:
        return
    cfg = load_config(Path(row["path"]))
    presentation = cfg.get("presentation", "hall")
    children = db.children_of(dir_id)
    space_rec = db.get_space(dir_id); width=space_rec["sx"]; height=space_rec["sy"]
    if presentation == "chambers":
        candidates = [c for c in children if c["kind"] != NodeKind.DIRECTORY.value]
        if not include_pins:
            candidates = [c for c in candidates if not db.is_pinned(c["id"])]
        ids = [c["id"] for c in candidates]
        _scatter_layout(db, dir_id, ids, width, height, "layout_v1_others")
        return
    movable = [c for c in children if include_pins or not db.is_pinned(c["id"])]
    ids = [c["id"] for c in movable]
    _scatter_layout(db, dir_id, ids, width, height, "layout_v1")
