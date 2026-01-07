
from __future__ import annotations
import math, random
from typing import List, Tuple, Dict, Any
Vec2 = Tuple[float,float]

def phyllotaxis_positions(n: int, radius: float = 8.0) -> List[Vec2]:
    golden_angle = math.pi * (3 - math.sqrt(5)); pts=[]
    for i in range(n):
        r = radius * math.sqrt(i / max(1,n)); th = i*golden_angle
        pts.append((r*math.cos(th), r*math.sin(th)))
    return pts

def grid_blue_noise(n: int, width: float = 36.0, height: float = 16.0, min_dist: float = 2.8, rng: random.Random|None=None) -> List[Vec2]:
    rng = rng or random.Random(); pts=[]; attempts=0; max_attempts=n*40
    while len(pts)<n and attempts<max_attempts:
        attempts+=1; x=(rng.random()-0.5)*width; y=(rng.random()-0.5)*height
        if all((x-px)**2+(y-py)**2 >= min_dist**2 for (px,py) in pts): pts.append((x,y))
    if len(pts)<n:
        cols = int(math.sqrt(n*(width/height)))+1; rows=(n+cols-1)//cols
        cw=width/max(1,cols); ch=height/max(1,rows); pts=[]
        for i in range(n):
            r,c = divmod(i,cols); x=-width/2 + c*cw + cw/2; y=-height/2 + r*ch + ch/2; pts.append((x,y))
    return pts

def bucketed_grid(n: int, width: float = 36.0, height: float = 16.0) -> List[Vec2]:
    cols=max(1,int(math.sqrt(n*(width/height)))); rows=(n+cols-1)//cols
    cw=width/max(1,cols); ch=height/max(1,rows); pts=[]
    for i in range(n):
        r,c = divmod(i,cols); x=-width/2 + c*cw + cw/2; y=-height/2 + r*ch + ch/2; pts.append((x,y))
    return pts

def choose_layout(n: int):
    return "phyllo" if n<=12 else ("blue" if n<=200 else "bucket")

def chamber_cells(n: int) -> List[Dict[str, Any]]:
    if n <= 0:
        return []
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = max(1, (n + cols - 1) // cols)
    cell_w = 1.0 / cols
    cell_h = 1.0 / rows
    pad_x = cell_w * 0.12
    pad_y = cell_h * 0.12
    cells = []
    for idx in range(n):
        r, c = divmod(idx, cols)
        min_x = c * cell_w + pad_x
        max_x = (c + 1) * cell_w - pad_x
        min_y = r * cell_h + pad_y
        max_y = (r + 1) * cell_h - pad_y
        min_x = min(max(min_x, 0.0), 1.0)
        max_x = max(min(max_x, 1.0), min_x + 1e-3)
        min_y = min(max(min_y, 0.0), 1.0)
        max_y = max(min(max_y, 1.0), min_y + 1e-3)
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        if r == 0:
            door_side = "south"
            door = (center_x, max_y)
        elif r == rows - 1:
            door_side = "north"
            door = (center_x, min_y)
        else:
            door_side = "south"
            door = (center_x, max_y)
        cells.append({
            "min": (min_x, min_y),
            "max": (max_x, max_y),
            "center": (center_x, center_y),
            "door_side": door_side,
            "door": door
        })
    return cells
