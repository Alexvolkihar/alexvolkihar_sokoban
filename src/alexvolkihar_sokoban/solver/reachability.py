"""Compiled floor graph and player reachability (spec 7.4).

The search works on integer cell indices rather than ``(row, col)`` tuples: floor cells are numbered in
row-major order, so the smallest index of a region is its top-left-most cell (the normalised player
position).
"""

from __future__ import annotations

from collections.abc import Iterable

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step
from alexvolkihar_sokoban.core.level import Level

DIRECTIONS: tuple[Direction, ...] = tuple(Direction)
"""Direction order used for the ``d`` in ``nbr[cell * 4 + d]``."""
OPPOSITE: tuple[int, ...] = tuple(DIRECTIONS.index(Direction((-d.dr, -d.dc))) for d in DIRECTIONS)
NO_CELL = -1


class Board:
    """Floor cells of a level as indices, with a flat neighbour table (``NO_CELL`` for walls/outside)."""

    def __init__(self, level: Level) -> None:
        self.level = level
        self.cells: tuple[Pos, ...] = tuple(sorted(level.floor))
        self.index: dict[Pos, int] = {pos: i for i, pos in enumerate(self.cells)}
        self.size = len(self.cells)
        nbr: list[int] = []
        for pos in self.cells:
            for d in DIRECTIONS:
                nbr.append(self.index.get(step(pos, d), NO_CELL))
        self.nbr: tuple[int, ...] = tuple(nbr)
        self.adj: tuple[tuple[int, ...], ...] = tuple(
            tuple(n for n in nbr[i * 4 : i * 4 + 4] if n >= 0) for i in range(self.size)
        )
        self.goals: frozenset[int] = frozenset(self.index[g] for g in level.goals)

    def occupancy(self, boxes: Iterable[int]) -> bytearray:
        occ = bytearray(self.size)
        for b in boxes:
            occ[b] = 1
        return occ

    def walk(self, occ: bytearray, start: int) -> list[int]:
        """Walking distance from ``start`` to every cell (``-1`` when unreachable without pushing)."""
        adj = self.adj
        dist = [-1] * self.size
        dist[start] = 0
        queue = [start]
        append = queue.append
        for cell in queue:  # the list grows while it is iterated: a breadth-first queue
            nd = dist[cell] + 1
            for n in adj[cell]:
                if dist[n] < 0 and not occ[n]:
                    dist[n] = nd
                    append(n)
        return dist

    def region(self, occ: bytearray, start: int) -> tuple[list[int], int]:
        """Walking distances from ``start`` and the normalised (smallest) reachable cell index."""
        dist = self.walk(occ, start)
        norm = start
        for i in range(start):
            if dist[i] >= 0:
                norm = i
                break
        return dist, norm


def reachable(level: Level, boxes: frozenset[Pos], start: Pos) -> tuple[frozenset[Pos], Pos]:
    """Cells the player at ``start`` can walk to without pushing, and the top-left-most of them."""
    board = Board(level)
    occ = board.occupancy(board.index[b] for b in boxes)
    dist, norm = board.region(occ, board.index[start])
    cells = frozenset(board.cells[i] for i, d in enumerate(dist) if d >= 0)
    return cells, board.cells[norm]
