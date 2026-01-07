
from __future__ import annotations
import curses, os, time
from pathlib import Path
from roguefs_core.index import IndexDB
from roguefs_core.worldgen import generate_room, reflow_room
from roguefs_core.hashing import node_id_for_path
from roguefs_core.node import NodeKind
from roguefs_core.interaction import open_with_default_app, edit_with_editor, rename_path
from roguefs_core.config import load_config
from .renderer import RoomRender
from .geom import calc_interior_dims, build_items_map
from .teleport import teleport_via_map
from .library import browse_magic_library
from .npc import summon_dead_librarian, LIBRARY_NAME

def _prompt_on_status(stdscr, prompt: str) -> str:
    h, w = stdscr.getmaxyx()
    y = h - 3
    curses.echo(); curses.curs_set(1)
    try:
        stdscr.move(y, 1)
        stdscr.clrtoeol()
        stdscr.addnstr(y, 1, prompt, w-2)
        stdscr.refresh()
        s = stdscr.getstr(y, 1+len(prompt)).decode('utf-8').strip()
    finally:
        curses.noecho(); curses.curs_set(0)
    return s

def _interior_dims(stdscr):
    """Return interior dimensions (cols, rows, x0, y0) using curses' (y, x) order."""
    h, w = stdscr.getmaxyx()
    return calc_interior_dims(w, h)

def run_ui(root: Path):
    db = IndexDB()
    generate_room(db, root, parent_id=None)
    root_id = node_id_for_path(root)
    current_dir_id = root_id
    cursor_idx = 0
    status = ""
    ROOM_REFRESH_INTERVAL = float(os.environ.get("ROGUEOS_ROOM_REFRESH_SECS", "10"))
    room_refresh_at = {}
    items_cache: list = []
    occ_cache: dict = {}
    items_dirty = True
    items_cols = None
    items_rows = None
    current_items_dir = None

    # Player tile (interior coords)
    stdscr = curses.initscr(); curses.noecho(); curses.cbreak(); stdscr.keypad(True); curses.curs_set(0)
    try:
        cols, rows, x0, y0 = _interior_dims(stdscr)
        player_gx, player_gy = ( (cols-2)//2, (rows-2)//2 )  # center spawn

        room_refresh_at[current_dir_id] = time.time()

        def mark_items_dirty():
            nonlocal items_dirty
            items_dirty = True

        def ensure_room(dir_id: str, force: bool = False):
            nonlocal items_dirty
            row = db.get_node(dir_id)
            if not row:
                return
            now = time.time()
            last = room_refresh_at.get(dir_id, 0.0)
            if force or (now - last) > ROOM_REFRESH_INTERVAL:
                generate_room(db, Path(row["path"]), parent_id=row["parent"])
                room_refresh_at[dir_id] = now
                items_dirty = True

        def get_items():
            nonlocal items_cache, occ_cache, items_dirty, items_cols, items_rows, current_items_dir
            ensure_room(current_dir_id)
            cols, rows, _, _ = _interior_dims(stdscr)
            if items_dirty or items_cols != cols or items_rows != rows or current_items_dir != current_dir_id:
                items_cache, occ_cache = build_items_map(db, current_dir_id, cols, rows)
                items_cols, items_rows = cols, rows
                current_items_dir = current_dir_id
                items_dirty = False
            return items_cache, occ_cache

        def recompute_selection():
            nonlocal cursor_idx
            # Snap selection to nearest item by grid distance
            items, occ = get_items()
            if not items: 
                cursor_idx = 0
                return
            # find nearest
            best_i = 0; best_d = 1e9
            for i, (cid, kind, gx, gy) in enumerate(items):
                d = (gx - player_gx)**2 + (gy - player_gy)**2
                if d < best_d:
                    best_d = d; best_i = i
            cursor_idx = best_i

        def step(dx: int, dy: int):
            nonlocal player_gx, player_gy
            cols, rows, _, _ = _interior_dims(stdscr)
            player_gx = max(0, min(cols-3, player_gx + dx))
            player_gy = max(0, min(rows-3, player_gy + dy))
            recompute_selection()

        recompute_selection()

        while True:
            room_row = db.get_node(current_dir_id)
            if room_row is None:
                status = "Room data missing."
                break
            room_path = Path(room_row["path"])
            items, occ = get_items()
            renderer = RoomRender(db, current_dir_id)
            renderer.draw(stdscr, cursor_idx, (player_gx, player_gy), status=status, items=items, occ=occ)
            status = ""

            # Input
            ch = stdscr.getch()
            if ch in (ord('q'), 27): break
            elif ch in (ord('w'), curses.KEY_UP, ord('k')): step(0,-1)
            elif ch in (ord('s'), curses.KEY_DOWN, ord('j')): step(0,+1)
            elif ch in (ord('a'), curses.KEY_LEFT, ord('h')): step(-1,0)
            elif ch in (ord('d'), curses.KEY_RIGHT, ord('l')): step(+1,0)
            elif ch in (ord('D'),):
                message, _ = summon_dead_librarian(room_path)
                ensure_room(current_dir_id, force=True)
                mark_items_dirty()
                recompute_selection()
                status = message
            elif ch in (ord('p'),):
                # Pin/unpin nearest item
                items, occ = get_items()
                if items:
                    cid, kind, gx, gy = items[cursor_idx]
                    pinned = db.toggle_pin(cid)
                    status = f"{'Pinned' if pinned else 'Unpinned'}"
            elif ch in (ord('o'),):
                # Open item underfoot (file)
                items, occ = get_items()
                target_id = occ.get((player_gx, player_gy))
                if target_id:
                    row = db.get_node(target_id)
                    if row["kind"] == NodeKind.FILE.value:
                        open_with_default_app(Path(row["path"]))
                    elif row["kind"] == NodeKind.DIRECTORY.value:
                        status = "Use '>' to descend into directory."
                    elif row["kind"] == NodeKind.CONTAINER.value:
                        cfg = load_config(room_path)
                        container_name = row["seed"] or LIBRARY_NAME
                        container_meta = cfg.get("containers", {}).get(container_name, {})
                        browse_magic_library(stdscr, room_path, container_meta.get("items", []))
                        status = "Perused the Magic Library."
                    elif row["kind"] == NodeKind.NPC.value:
                        status = "The dead librarian grins silently."
                    else:
                        status = "Nothing to open here."
                else:
                    status = "No item underfoot."
            elif ch in (ord('e'),):
                items, occ = get_items()
                target_id = occ.get((player_gx, player_gy))
                if target_id:
                    row = db.get_node(target_id)
                    if row["kind"] == NodeKind.FILE.value:
                        edit_with_editor(Path(row["path"]))
                    else:
                        status = "Edit works on files."
                else:
                    status = "No file underfoot."
            elif ch in (ord('>'),):
                # Descend only if standing on a directory
                items, occ = get_items()
                target_id = occ.get((player_gx, player_gy))
                if target_id:
                    row = db.get_node(target_id)
                    if row["kind"] == NodeKind.DIRECTORY.value:
                        current_dir_id = row["id"]
                        current_items_dir = None
                        ensure_room(current_dir_id, force=True)
                        # spawn near center in new room
                        cols, rows, _, _ = _interior_dims(stdscr)
                        player_gx, player_gy = ( (cols-2)//2, (rows-2)//2 )
                        cursor_idx = 0
                        recompute_selection()
                    else:
                        status = "Stand on a '>' (directory) tile to descend."
                else:
                    status = "Stand on a '>' (directory) tile to descend."
            elif ch in (ord('<'),):
                # Ascend only if standing on the '<' tile (1,1)
                parent_row = db.parent_of(current_dir_id)
                if parent_row is None:
                    status = "No parent (at root)."
                else:
                    if (player_gx, player_gy) == (0,0) or (player_gx, player_gy) == (1,1):
                        current_dir_id = parent_row["id"]
                        current_items_dir = None
                        ensure_room(current_dir_id, force=True)
                        cols, rows, _, _ = _interior_dims(stdscr)
                        # place player near the top-left stairs again
                        player_gx, player_gy = (1,1)
                        cursor_idx = 0
                        recompute_selection()
                    else:
                        status = "Move onto '<' (top-left) to ascend."
            elif ch in (ord('T'),):
                reflow_room(db, current_dir_id, include_pins=False)
                mark_items_dirty()
                recompute_selection()
                status = "Reflowed unpinned items."
            elif ch in (ord('r'),):
                # Rename item underfoot
                items, occ = get_items()
                target_id = occ.get((player_gx, player_gy))
                if target_id:
                    row = db.get_node(target_id)
                    new_name = _prompt_on_status(stdscr, "New name: ")
                    try:
                        newp = rename_path(Path(row["path"]), new_name)
                        new_id = node_id_for_path(newp)
                        db.upsert_node(new_id, newp, NodeKind(row["kind"]), current_dir_id, seed=None, theme=None)
                        ensure_room(current_dir_id, force=True)
                        mark_items_dirty()
                        recompute_selection()
                        status = "Renamed."
                    except Exception as e: status = f"Rename failed: {e}"
                else:
                    status = "No item underfoot to rename."
            elif ch in (ord('M'), ord('m'), ord('/')):
                target_dir = teleport_via_map(stdscr, db, root_id, current_dir_id)
                if target_dir:
                    row = db.get_node(target_dir)
                    if row and row["kind"] == NodeKind.DIRECTORY.value:
                        current_dir_id = row["id"]
                        current_items_dir = None
                        ensure_room(current_dir_id, force=True)
                        cols, rows, _, _ = _interior_dims(stdscr)
                        player_gx, player_gy = ( (cols-2)//2, (rows-2)//2 )
                        cursor_idx = 0
                        recompute_selection()
                        status = "Teleported to directory."
                    else:
                        status = "Selection unavailable."
                else:
                    status = "Teleport canceled."
            else:
                status = ""
    finally:
        curses.nocbreak(); stdscr.keypad(False); curses.echo(); curses.endwin()
