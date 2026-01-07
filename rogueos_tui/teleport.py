from __future__ import annotations
import curses
from pathlib import Path
from typing import List, Optional, Tuple
from roguefs_core.index import IndexDB
from roguefs_core.node import NodeKind
from roguefs_core.worldgen import generate_room

MAX_DIR_ENTRIES = 2000

def _ensure_children_generated(db: IndexDB, dir_id: str) -> None:
    row = db.get_node(dir_id)
    if not row:
        return
    generate_room(db, Path(row["path"]), parent_id=row["parent"])

def _collect_directories(db: IndexDB, dir_id: str, acc: List[Tuple[str, int]], depth: int, limit: int) -> None:
    if len(acc) >= limit:
        return
    acc.append((dir_id, depth))
    _ensure_children_generated(db, dir_id)
    for child in db.children_of(dir_id):
        if child["kind"] != NodeKind.DIRECTORY.value:
            continue
        if len(acc) >= limit:
            break
        _collect_directories(db, child["id"], acc, depth + 1, limit)

def _format_label(db: IndexDB, node_id: str, depth: int, root_id: str) -> str:
    row = db.get_node(node_id)
    if not row:
        return ""
    indent = "  " * depth
    if node_id == root_id:
        return f"{row['path']}/" if not str(row["path"]).endswith("/") else row["path"]
    name = Path(row["path"]).name or row["path"]
    label = f"{name}/"
    return f"{indent}{label}"

def teleport_via_map(stdscr, db: IndexDB, root_id: str, current_dir_id: str, max_entries: int = MAX_DIR_ENTRIES) -> Optional[str]:
    directories: List[Tuple[str, int]] = []
    _collect_directories(db, root_id, directories, 0, max_entries)
    if not directories:
        return None
    selected = next((i for i, (nid, _) in enumerate(directories) if nid == current_dir_id), 0)
    top = 0
    truncated = len(directories) >= max_entries

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.box()
        title = " Teleport Map "
        try:
            stdscr.addnstr(0, max(2, (w - len(title)) // 2), title, w - 4, curses.A_BOLD)
        except curses.error:
            pass

        visible = max(1, h - 4)
        if selected < top:
            top = selected
        elif selected >= top + visible:
            top = selected - visible + 1

        row_idx = 0
        for i in range(top, min(len(directories), top + visible)):
            node_id, depth = directories[i]
            label = _format_label(db, node_id, depth, root_id)
            if not label:
                continue
            attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
            try:
                stdscr.addnstr(1 + row_idx, 2, label, w - 4, attr)
            except curses.error:
                pass
            row_idx += 1

        if truncated:
            try:
                stdscr.addnstr(h - 3, 2, f"(Showing first {max_entries} directories)", w - 4, curses.A_DIM)
            except curses.error:
                pass

        instruction = "↑/↓ to move  Enter to teleport  q/Esc to cancel"
        try:
            stdscr.addnstr(h - 2, 2, instruction, w - 4)
        except curses.error:
            pass
        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (curses.KEY_UP, ord('k'), ord('w')):
            selected = (selected - 1) % len(directories)
        elif ch in (curses.KEY_DOWN, ord('j'), ord('s')):
            selected = (selected + 1) % len(directories)
        elif ch in (curses.KEY_PPAGE,):
            selected = max(0, selected - visible)
        elif ch in (curses.KEY_NPAGE,):
            selected = min(len(directories) - 1, selected + visible)
        elif ch in (10, 13, curses.KEY_ENTER):
            return directories[selected][0]
        elif ch in (27, ord('q')):
            return None
