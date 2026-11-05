"""Reverse play: start with every box on a goal and pull boxes away from the goals (spec 7.8).

A pull is a push played backwards, so the forward level is always solvable from any position reached. The
reverse play is breadth-first: every pull sequence is tried, shortest first, and a position needing the
most pulls is kept. The search starts from every solved position (the player in each area), so that
count is the exact push distance to the solution unless ``max_states`` cuts the search: the start is as
far from the solution as the room allows (a random walk keeps undoing its own pulls and rarely gets more
than a few pushes away).
"""

from __future__ import annotations

import random
from collections import deque

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step

MAX_STATES = 20_000
"""Default bound on the positions explored (boxes + player area); the search stops there."""

_ORDER: tuple[Direction, ...] = tuple(sorted(Direction, key=lambda d: d.char))
_OPPOSITE: tuple[int, ...] = tuple(_ORDER.index(Direction((-d.dr, -d.dc))) for d in _ORDER)


class _Grid:
    """Floor cells as row-major indices with a flat neighbour table (-1 off the floor)."""

    def __init__(self, floor: frozenset[Pos]) -> None:
        self.cells: tuple[Pos, ...] = tuple(sorted(floor))
        self.index = {pos: i for i, pos in enumerate(self.cells)}
        self.nbr = tuple(self.index.get(step(pos, d), -1) for pos in self.cells for d in _ORDER)

    def area(self, start: int, occ: bytearray) -> list[int]:
        """Cells the player reaches from ``start`` without pushing (``start`` first)."""
        seen = bytearray(len(self.cells))
        seen[start] = 1
        out = [start]
        nbr = self.nbr
        for cell in out:  # breadth-first: the list grows while it is iterated
            for k in range(cell * 4, cell * 4 + 4):
                nxt = nbr[k]
                if nxt >= 0 and not occ[nxt] and not seen[nxt]:
                    seen[nxt] = 1
                    out.append(nxt)
        return out

    def path(self, start: int, target: int, occ: bytearray) -> list[int]:
        """Directions (indices into ``_ORDER``) of a shortest walk from ``start`` to ``target``."""
        came: dict[int, tuple[int, int]] = {}
        todo = deque([start])
        seen = {start}
        while todo:
            cell = todo.popleft()
            if cell == target:
                break
            for d in range(4):
                nxt = self.nbr[cell * 4 + d]
                if nxt >= 0 and not occ[nxt] and nxt not in seen:
                    seen.add(nxt)
                    came[nxt] = (cell, d)
                    todo.append(nxt)
        moves: list[int] = []
        cell = target
        while cell != start:
            cell, d = came[cell]
            moves.append(d)
        moves.reverse()
        return moves


def _occupancy(size: int, boxes: tuple[int, ...]) -> bytearray:
    occ = bytearray(size)
    for b in boxes:
        occ[b] = 1
    return occ


def reverse_play(
    rng: random.Random,
    floor: frozenset[Pos],
    goals: frozenset[Pos],
    player: Pos,
    steps: int,
    *,
    trace: list[str] | None = None,
    max_states: int = MAX_STATES,
) -> tuple[frozenset[Pos], Pos]:
    """Boxes start on ``goals`` and the player at ``player``; pull sequences of at most ``steps`` pulls are
    explored breadth-first (at most ``max_states`` positions). Returns the boxes of a random position among
    those needing the most pulls, and a random cell of the player's area there.

    With ``trace``, the forward moves are appended as LURD characters (uppercase for a push), last move
    first: ``"".join(reversed(trace))`` solves the level from the returned position. Raises ``ValueError``
    when a goal or the player is off the floor, or the player stands on a goal (where a box starts).
    """
    if not goals <= floor:
        raise ValueError("every goal must be on the floor")
    if player not in floor or player in goals:
        raise ValueError(f"the player {player} must stand on a free floor cell")
    grid = _Grid(floor)
    size = len(grid.cells)
    nbr = grid.nbr
    root_boxes = tuple(sorted(grid.index[g] for g in goals))
    root_player = grid.index[player]

    # Explored positions: boxes, the player cell it was entered with, parent, pull (box, dir), depth.
    boxes_of: list[tuple[int, ...]] = []
    player_of: list[int] = []
    parent_of: list[int] = []
    pull_of: list[tuple[int, int]] = []
    depth_of: list[int] = []
    seen: set[tuple[tuple[int, ...], int]] = set()
    # Roots: the solved boxes with the player in each area, the given player's first, so that the depth
    # of a position is its exact push distance to a solved position.
    roots = [root_player]
    root_occ = _occupancy(size, root_boxes)
    covered = root_occ[:]
    for c in grid.area(root_player, root_occ):
        covered[c] = 1
    for cell in range(size):
        if not covered[cell]:
            roots.append(cell)
            for c in grid.area(cell, root_occ):
                covered[c] = 1
    queued: set[tuple[tuple[int, ...], int]] = {(root_boxes, r) for r in roots}
    todo: deque[tuple[tuple[int, ...], int, int, tuple[int, int], int]] = deque(
        (root_boxes, r, -1, (-1, -1), 0) for r in roots
    )
    while todo and len(boxes_of) < max_states:
        boxes, at, parent, pull, depth = todo.popleft()
        occ = _occupancy(size, boxes)
        area = grid.area(at, occ)
        key = (boxes, min(area))
        if key in seen:
            continue
        seen.add(key)
        me = len(boxes_of)
        boxes_of.append(boxes)
        player_of.append(at)
        parent_of.append(parent)
        pull_of.append(pull)
        depth_of.append(depth)
        if depth >= steps:
            continue
        reach = bytearray(size)
        for cell in area:
            reach[cell] = 1
        for i, b in enumerate(boxes):
            for d in range(4):
                stand = nbr[b * 4 + d]
                if stand < 0 or not reach[stand]:
                    continue
                beyond = nbr[stand * 4 + d]
                if beyond < 0 or occ[beyond]:
                    continue
                child = tuple(sorted((*boxes[:i], stand, *boxes[i + 1 :])))
                if (child, beyond) not in queued:
                    queued.add((child, beyond))
                    todo.append((child, beyond, me, (b, d), depth + 1))

    deepest = max(depth_of)
    if deepest == 0:
        return goals, player  # no box can be pulled
    chosen = rng.choice([i for i, depth in enumerate(depth_of) if depth == deepest])
    final_occ = _occupancy(size, boxes_of[chosen])
    final = rng.choice(sorted(grid.area(player_of[chosen], final_occ)))
    if trace is not None:
        _trace(grid, chosen, final, boxes_of, player_of, parent_of, pull_of, trace)
    return frozenset(grid.cells[b] for b in boxes_of[chosen]), grid.cells[final]


def _trace(
    grid: _Grid,
    chosen: int,
    final: int,
    boxes_of: list[tuple[int, ...]],
    player_of: list[int],
    parent_of: list[int],
    pull_of: list[tuple[int, int]],
    trace: list[str],
) -> None:
    """Replay the pulls from the root to ``chosen`` (walks included), recording the forward moves."""
    chain: list[int] = []
    node = chosen
    while parent_of[node] >= 0:
        chain.append(node)
        node = parent_of[node]
    chain.reverse()
    size = len(grid.cells)
    at = player_of[node]  # the root the chain starts from
    for node in chain:
        box, d = pull_of[node]
        occ = _occupancy(size, boxes_of[parent_of[node]])
        stand = grid.nbr[box * 4 + d]
        for move in grid.path(at, stand, occ):
            trace.append(_ORDER[_OPPOSITE[move]].char)
        trace.append(_ORDER[_OPPOSITE[d]].char.upper())
        at = grid.nbr[stand * 4 + d]
    for move in grid.path(at, final, _occupancy(size, boxes_of[chosen])):
        trace.append(_ORDER[_OPPOSITE[move]].char)
