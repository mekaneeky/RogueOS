
from __future__ import annotations
import os, hashlib
from pathlib import Path

def _b2(s: bytes) -> bytes: return hashlib.blake2b(s, digest_size=32).digest()
def hash_hex(s: bytes) -> str: return hashlib.blake2b(s, digest_size=16).hexdigest()

def node_key_for_path(p: Path) -> bytes:
    try:
        st = os.stat(p, follow_symlinks=False)
        dev = getattr(st, "st_dev", 0); ino = getattr(st, "st_ino", 0)
        if ino != 0: return _b2(f"inode:{dev}:{ino}".encode())
    except FileNotFoundError:
        pass
    try:
        st = os.stat(p, follow_symlinks=False)
        key = f"path:{os.path.abspath(p)}:{st.st_size}:{getattr(st,'st_mtime_ns',0)}".encode()
    except FileNotFoundError:
        key = f"path:{os.path.abspath(p)}:missing".encode()
    return _b2(key)

def node_id_for_path(p: Path) -> str: return hash_hex(node_key_for_path(p))

def seed_for_node_id(nid: str, salt: str = "layout_v1") -> int:
    return int.from_bytes(hashlib.blake2b((nid + '|' + salt).encode(), digest_size=8).digest(), 'big')
