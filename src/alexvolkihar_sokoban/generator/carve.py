"""Random room carving: a connected floor inside a walled ``width × height`` rectangle (spec 7.8)."""

from __future__ import annotations

import math
import random
from collections.abc import Set

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step

MIN_FLOOR_RATIO = 0.6
"""The carved floor keeps at least this share of the rectangle's interior."""


def is_connected(floor: Set[Pos]) -> bool:
    """True when every cell of ``floor`` is reachable from every other one by orthogonal steps."""
    if not floor:
        return False
    start = min(floor)
    seen = {start}
    todo = [start]
    while todo:
        pos = todo.pop()
        for d in Direction:
            nxt = step(pos, d)
            if nxt in floor and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return len(seen) == len(floor)


def _neighbours(pos: Pos, floor: Set[Pos]) -> list[Pos]:
    return [nxt for d in Direction if (nxt := step(pos, d)) in floor]


def _dead_end(pos: Pos, floor: Set[Pos]) -> bool:
    """A floor cell with at most one floor neighbour: a box pushed there is stuck."""
    return len(_neighbours(pos, floor)) <= 1


def carve_room(rng: random.Random, width: int, height: int) -> frozenset[Pos]:
    """A connected floor strictly inside the rectangle (its border stays wall), covering 60 % or more of
    the interior.

    The room starts as the whole interior; random cells then become walls, each one only when the rest of
    the floor stays connected and no floor cell becomes a dead end. Raises ``ValueError`` when the interior
    is narrower than 2 cells.
    """
    if width < 4 or height < 4:
        raise ValueError(f"rectangle {width}x{height} too small for a room (minimum 4x4)")
    floor = {(r, c) for r in range(1, height - 1) for c in range(1, width - 1)}
    keep = math.ceil(MIN_FLOOR_RATIO * len(floor))
    spare = len(floor) - keep
    walls_wanted = rng.randint(spare // 2, spare)
    candidates = sorted(floor)
    rng.shuffle(candidates)
    added = 0
    for pos in candidates:
        if added == walls_wanted:
            break
        floor.discard(pos)
        if not any(_dead_end(n, floor) for n in _neighbours(pos, floor)) and is_connected(floor):
            added += 1
        else:
            floor.add(pos)
    return frozenset(floor)
