
from __future__ import annotations
from typing import Callable, Dict, List, Any
class EventBus:
    def __init__(self): self._sub: Dict[str, List[Callable[[Any], None]]] = {}
    def on(self, event: str, cb): self._sub.setdefault(event, []).append(cb)
    def emit(self, event: str, payload): 
        for cb in self._sub.get(event, []): cb(payload)
