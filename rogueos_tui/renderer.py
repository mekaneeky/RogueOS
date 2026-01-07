
from __future__ import annotations
import curses, math
from typing import Tuple, Dict, List, Optional
from pathlib import Path
from roguefs_core.index import IndexDB
from roguefs_core.node import NodeKind
from roguefs_core.config import load_config
from roguefs_core.layout import chamber_cells
from .geom import calc_interior_dims, build_items_map

TILES = {
    "wall":"#",
    "floor":".",
    "stairs_up":"<",
    "dir":">",
    "door_closed":"+",
    "door_open":"/",
    "file":"*",
    "symlink":"=",
    "library":"L",
    "npc":"d",
    "cursor":"@"
}
COLORS = {
    "wall":6,
    "floor":1,
    "file":2,
    "dir":4,
    "door_closed":6,
    "door_open":4,
    "symlink":3,
    "library":2,
    "npc":5,
    "cursor":5,
    "title":7
}

def _init_colors():
    if not curses.has_colors(): return
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_BLUE, -1)
    curses.init_pair(7, curses.COLOR_WHITE, -1)

class RoomRender:
    def __init__(self, db: IndexDB, dir_id: str):
        self.db = db; self.dir_id = dir_id
        self.children = self.db.children_of(dir_id)

    def draw(self, stdscr, cursor_idx: int, player_gxy: Tuple[int,int], status: str = "", items: Optional[List[Tuple[str,str,int,int]]] = None, occ: Optional[Dict[Tuple[int,int], str]] = None) -> None:
        stdscr.erase(); _init_colors()
        h, w = stdscr.getmaxyx(); stdscr.box()
        cols, rows, x0, y0 = calc_interior_dims(w, h)

        # Title
        row = self.db.get_node(self.dir_id); title = row["path"]
        try: stdscr.addnstr(0, 2, f" {title} ", w-4, curses.color_pair(COLORS["title"]))
        except curses.error: pass

        # Walls + floor
        for x in range(cols):
            try:
                stdscr.addstr(y0, x0+x, TILES["wall"], curses.color_pair(COLORS["wall"]) | curses.A_DIM)
                stdscr.addstr(y0+rows-1, x0+x, TILES["wall"], curses.color_pair(COLORS["wall"]) | curses.A_DIM)
            except curses.error: pass
        for y in range(1, rows-1):
            try:
                stdscr.addstr(y0+y, x0, TILES["wall"], curses.color_pair(COLORS["wall"]) | curses.A_DIM)
                stdscr.addstr(y0+y, x0+cols-1, TILES["wall"], curses.color_pair(COLORS["wall"]) | curses.A_DIM)
                stdscr.addstr(y0+y, x0+1, TILES["floor"]*(cols-2), curses.color_pair(COLORS["floor"]))
            except curses.error: pass

        # Parent stairs '<'
        has_parent = self.db.parent_of(self.dir_id) is not None
        if has_parent:
            try: stdscr.addstr(y0+1, x0+1, TILES["stairs_up"], curses.color_pair(COLORS["dir"]))
            except curses.error: pass

        # Items map (positions in interior coords)
        if items is None or occ is None:
            items, occ = build_items_map(self.db, self.dir_id, cols, rows)

        cfg = load_config(Path(row["path"]))
        child_meta = cfg.get("children", {})
        presentation = cfg.get("presentation", "hall")

        door_overlays: Dict[str, Tuple[int, int, str, str]] = {}

        if presentation == "chambers":
            dir_nodes: List[Tuple[str, Dict[str, str], int, int]] = []
            for cid, kind, gx, gy in items:
                if kind != NodeKind.DIRECTORY.value:
                    continue
                node = self.db.get_node(cid)
                if not node:
                    continue
                dir_nodes.append((cid, node, gx, gy))

            interior_w = max(1, cols - 2)
            interior_h = max(1, rows - 2)

            def norm_range(nmin: float, nmax: float, size: int) -> Tuple[int, int]:
                if size <= 0:
                    return (0, 0)
                nmin = max(0.0, min(1.0, nmin))
                nmax = max(nmin + 1e-3, min(1.0, nmax))
                start = int(math.floor(nmin * size))
                end = int(math.ceil(nmax * size) - 1)
                start = max(0, min(size - 1, start))
                end = max(start, min(size - 1, end))
                return start, end

            def norm_to_idx(norm: float, size: int) -> int:
                if size <= 0:
                    return 0
                norm = max(0.0, min(1.0, norm))
                return max(0, min(size - 1, int(round(norm * (size - 1)))))

            cells = chamber_cells(len(dir_nodes))
            for (cid, node, gx, gy), cell in zip(dir_nodes, cells):
                name = Path(node["path"]).name
                meta = child_meta.get(name, {})
                door_state = meta.get("state", "open")
                color_key = "door_open" if door_state == "open" else "door_closed"
                min_x, min_y = cell["min"]
                max_x, max_y = cell["max"]
                left_idx, right_idx = norm_range(min_x, max_x, interior_w)
                top_idx, bottom_idx = norm_range(min_y, max_y, interior_h)
                left_abs = x0 + 1 + left_idx
                right_abs = x0 + 1 + right_idx
                top_abs = y0 + 1 + top_idx
                bottom_abs = y0 + 1 + bottom_idx
                door_norm_x, door_norm_y = cell["door"]
                door_side = cell["door_side"]
                door_idx_x = norm_to_idx(door_norm_x, interior_w)
                door_idx_y = norm_to_idx(door_norm_y, interior_h)
                door_abs_x = x0 + 1 + door_idx_x
                door_abs_y = y0 + 1 + door_idx_y

                # Draw walls, skipping the door location
                for ax in range(left_abs, right_abs + 1):
                    if (door_abs_x, door_abs_y) != (ax, top_abs):
                        try:
                            stdscr.addstr(top_abs, ax, TILES["wall"], curses.color_pair(COLORS["wall"]))
                        except curses.error:
                            pass
                    if (door_abs_x, door_abs_y) != (ax, bottom_abs):
                        try:
                            stdscr.addstr(bottom_abs, ax, TILES["wall"], curses.color_pair(COLORS["wall"]))
                        except curses.error:
                            pass
                for ay in range(top_abs, bottom_abs + 1):
                    if (door_abs_x, door_abs_y) != (left_abs, ay):
                        try:
                            stdscr.addstr(ay, left_abs, TILES["wall"], curses.color_pair(COLORS["wall"]))
                        except curses.error:
                            pass
                    if (door_abs_x, door_abs_y) != (right_abs, ay):
                        try:
                            stdscr.addstr(ay, right_abs, TILES["wall"], curses.color_pair(COLORS["wall"]))
                        except curses.error:
                            pass

                door_tile = TILES["door_open"] if door_state == "open" else TILES["door_closed"]
                door_overlays[cid] = (door_abs_x, door_abs_y, door_tile, color_key)

        for _, (dx, dy, ch, color_key) in door_overlays.items():
            try:
                stdscr.addstr(dy, dx, ch, curses.color_pair(COLORS[color_key]) | curses.A_BOLD)
            except curses.error:
                pass

        # Underfoot label near top-left
        underfoot_id = occ.get(player_gxy)
        label = "Underfoot: --"
        label_color = curses.color_pair(COLORS["floor"])
        if underfoot_id:
            node = self.db.get_node(underfoot_id)
            if node:
                kind_value = node["kind"]
                base_name = Path(node["path"]).name or node["path"]
                display_name = base_name
                if kind_value == NodeKind.CONTAINER.value and node["seed"]:
                    display_name = node["seed"]
                elif kind_value == NodeKind.NPC.value and node["seed"]:
                    display_name = node["seed"]
                if kind_value == NodeKind.DIRECTORY.value and not display_name.endswith("/"):
                    display_name = f"{display_name}/"
                label = f"Underfoot: {display_name}"
                if kind_value == NodeKind.DIRECTORY.value:
                    meta = child_meta.get(base_name, {})
                    door_state = meta.get("state", "open")
                    color_key = "door_open" if door_state == "open" else "door_closed"
                    label_color = curses.color_pair(COLORS[color_key])
                elif kind_value == NodeKind.SYMLINK.value:
                    label_color = curses.color_pair(COLORS["symlink"])
                elif kind_value == NodeKind.CONTAINER.value:
                    label_color = curses.color_pair(COLORS["library"])
                elif kind_value == NodeKind.NPC.value:
                    label_color = curses.color_pair(COLORS["npc"])
                else:
                    label_color = curses.color_pair(COLORS["file"])
        try:
            stdscr.addnstr(1, 2, label, w-4, label_color | curses.A_BOLD)
        except curses.error:
            pass

        # Draw items
        for idx, c in enumerate(items):
            cid, kind, gx, gy = c
            glyph = TILES["file"]; color_key = "file"
            if kind == NodeKind.DIRECTORY.value:
                node = self.db.get_node(cid)
                if not node:
                    continue
                name = Path(node["path"]).name
                meta = child_meta.get(name, {})
                door_state = meta.get("state", "open")
                glyph = TILES["dir"]
                color_key = "door_open" if door_state == "open" else "door_closed"
            elif kind == NodeKind.SYMLINK.value:
                glyph = TILES["symlink"]; color_key = "symlink"
            elif kind == NodeKind.CONTAINER.value:
                glyph = TILES["library"]; color_key = "library"
            elif kind == NodeKind.NPC.value:
                glyph = TILES["npc"]; color_key = "npc"
            ax, ay = x0+1+gx, y0+1+gy
            try: stdscr.addstr(ay, ax, glyph, curses.color_pair(COLORS[color_key]))
            except curses.error: pass

        # Draw '@' at player tile
        pgx, pgy = player_gxy
        pax, pay = x0+1+pgx, y0+1+pgy
        try: stdscr.addstr(pay, pax, TILES["cursor"], curses.color_pair(COLORS["cursor"])|curses.A_BOLD)
        except curses.error: pass

        # HUD
        try:
            stdscr.addnstr(h-3, 1, status, w-2)
            stdscr.addnstr(h-2, 1, "[WASD/Arrows] Move  [>] Descend  [<] Ascend  [o]Open  [e]Edit  [D]Summon Librarian  [m/M//] Teleport map  [p]Pin  [T]Reflow  [q]Quit", w-2)
        except curses.error: pass
        stdscr.refresh()
