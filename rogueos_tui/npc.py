from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
from roguefs_core.config import load_config, save_config, ensure_container, ensure_npc

NPC_NAME = "dead_librarian"
LIBRARY_NAME = "Magic Library"

def _gather_pdfs(dir_path: Path) -> List[Dict[str, str]]:
    pdfs: List[Dict[str, str]] = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_file() and entry.suffix.lower() == ".pdf":
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            pdfs.append({
                "name": entry.name,
                "relpath": entry.name,
                "size": size
            })
    return pdfs

def summon_dead_librarian(dir_path: Path) -> Tuple[str, bool]:
    cfg = load_config(dir_path)
    npc_meta = ensure_npc(cfg, NPC_NAME)
    npc_meta["present"] = True
    library_meta = ensure_container(cfg, LIBRARY_NAME)
    pdfs = _gather_pdfs(dir_path)
    library_meta["items"] = pdfs
    library_meta["type"] = "magic_library"
    save_config(dir_path, cfg)
    if not pdfs:
        return ("Dead Librarian found no tomes to shelve.", True)
    return (f"Dead Librarian archived {len(pdfs)} book(s).", True)
