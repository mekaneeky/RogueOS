from __future__ import annotations
import curses
from pathlib import Path
from typing import Dict, List
import textwrap
import string

def _preview_ascii(path: Path, max_lines: int = 12, width: int = 56) -> List[str]:
    try:
        with path.open("rb") as f:
            data = f.read(8192)
    except Exception:
        return ["(Unable to read tome.)"]
    text = "".join(chr(b) for b in data if chr(b) in string.printable)
    text = text.replace("\r", "")
    paragraphs = text.split("\n")
    lines: List[str] = []
    for para in paragraphs:
        if not para.strip():
            lines.append("")
            continue
        for chunk in textwrap.wrap(para.strip(), width=width):
            lines.append(chunk)
            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break
    if not lines:
        lines = ["(No decipherable runes.)"]
    return lines[:max_lines]

def browse_magic_library(stdscr, dir_path: Path, entries: List[Dict[str, str]]):
    if not entries:
        h, w = stdscr.getmaxyx()
        stdscr.addnstr(h-3, 1, "Magic Library is empty.", w-2)
        stdscr.refresh()
        stdscr.getch()
        return
    index = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.box()
        title = " Magic Library "
        try:
            stdscr.addnstr(0, max(2, (w-len(title))//2), title, w-4, curses.A_BOLD)
        except curses.error:
            pass
        visible = max(1, h - 6)
        top = max(0, min(index - visible // 2, len(entries) - visible))
        for row_idx, entry in enumerate(entries[top:top+visible]):
            line = f"{entry['name']}"
            attr = curses.A_REVERSE if (top + row_idx) == index else curses.A_NORMAL
            try:
                stdscr.addnstr(1 + row_idx, 2, line, w-4, attr)
            except curses.error:
                pass
        try:
            stdscr.addnstr(h-3, 2, "↑/↓ select  Enter read  q to exit", w-4, curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (curses.KEY_UP, ord('k'), ord('w')):
            index = (index - 1) % len(entries)
        elif ch in (curses.KEY_DOWN, ord('j'), ord('s')):
            index = (index + 1) % len(entries)
        elif ch in (10, 13, curses.KEY_ENTER):
            _read_tome(stdscr, dir_path, entries[index])
        elif ch in (27, ord('q')):
            break

def _read_tome(stdscr, dir_path: Path, entry: Dict[str, str]):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    stdscr.box()
    rel = entry.get("relpath", entry.get("name", ""))
    path = dir_path / rel
    header = f" Tome: {entry.get('name', '?')} "
    try:
        stdscr.addnstr(0, max(2, (w-len(header))//2), header, w-4, curses.A_BOLD)
    except curses.error:
        pass
    info_line = f"Location: {rel}"
    try:
        stdscr.addnstr(1, 2, info_line, w-4)
    except curses.error:
        pass
    preview = _preview_ascii(path)
    for i, line in enumerate(preview):
        if 3 + i >= h - 2:
            break
        try:
            stdscr.addnstr(3 + i, 4, line, w-8)
        except curses.error:
            pass
    try:
        stdscr.addnstr(h-2, 2, "Press any key to return to stacks.", w-4, curses.A_DIM)
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.getch()
