
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

class NodeKind(str, Enum):
    DIRECTORY = "Directory"
    FILE = "File"
    SYMLINK = "Symlink"
    MOUNT = "Mount"
    CONTAINER = "Container"
    NPC = "NPC"

@dataclass(frozen=True)
class Transform:
    x: float = 0.0; y: float = 0.0; z: float = 0.0
    rx: float = 0.0; ry: float = 0.0; rz: float = 0.0; rw: float = 1.0
    sx: float = 1.0; sy: float = 1.0; sz: float = 1.0

@dataclass
class Space:
    origin: Tuple[float,float,float] = (0.0,0.0,0.0)
    size:   Tuple[float,float,float] = (40.0,20.0,8.0)

def transform_to_tuple(t: Transform):
    return (t.x,t.y,t.z,t.rx,t.ry,t.rz,t.rw,t.sx,t.sy,t.sz)

def transform_from_tuple(vals):
    return Transform(*vals)
