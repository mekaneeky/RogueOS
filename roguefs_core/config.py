from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = {
    "type": "room",
    "presentation": "hall",
    "children": {},
    "containers": {},
    "npcs": {}
}

CONFIG_FILENAME = ".rogueos"

def _ensure_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
    merged["children"] = dict(cfg.get("children", {}))
    merged["containers"] = dict(cfg.get("containers", {}))
    merged["npcs"] = dict(cfg.get("npcs", {}))
    if "presentation" not in merged or not isinstance(merged["presentation"], str):
        merged["presentation"] = "hall"
    return merged

def load_config(dir_path: Path) -> Dict[str, Any]:
    cfg_path = dir_path / CONFIG_FILENAME
    if not cfg_path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return dict(DEFAULT_CONFIG)
            return _ensure_cfg(data)
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(dir_path: Path, cfg: Dict[str, Any]) -> None:
    cfg_path = dir_path / CONFIG_FILENAME
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)

def ensure_child_metadata(cfg: Dict[str, Any], child_name: str, *, access: str = "door", state: str = "open") -> None:
    children = cfg.setdefault("children", {})
    meta = children.get(child_name, {})
    if "access" not in meta:
        meta["access"] = access
    if "state" not in meta:
        meta["state"] = state
    children[child_name] = meta

def mark_child_state(cfg: Dict[str, Any], child_name: str, state: str) -> None:
    children = cfg.setdefault("children", {})
    meta = children.setdefault(child_name, {})
    meta["state"] = state

def ensure_container(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    containers = cfg.setdefault("containers", {})
    return containers.setdefault(name, {"type": "magic_library", "items": []})

def ensure_npc(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    npcs = cfg.setdefault("npcs", {})
    return npcs.setdefault(name, {"present": False})
