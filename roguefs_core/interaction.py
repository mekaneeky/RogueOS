
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

def open_with_default_app(path: Path):
    try:
        if sys.platform.startswith("darwin"): subprocess.Popen(["open", str(path)])
        elif os.name == "nt": os.startfile(str(path))  # type: ignore
        else: subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print(f"[open] Failed: {e}")

def edit_with_editor(path: Path):
    editor = os.environ.get("EDITOR")
    if editor:
        try:
            os.system(f"{editor} '{str(path)}'"); return
        except Exception as e:
            print(f"[edit] Editor failed: {e}")
    open_with_default_app(path)

def rename_path(path: Path, new_name: str) -> Path:
    target = path.with_name(new_name); os.rename(path, target); return target
