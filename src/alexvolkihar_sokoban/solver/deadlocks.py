"""Deadlock detection: dead squares and freeze deadlocks (spec 7.4). Both rules are sound: a state they
reject can never be solved, so exhausting the search under them proves a level unsolvable."""

from __future__ import annotations

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.distances import UNREACHABLE, goal_distances
from alexvolkihar_sokoban.solver.reachability import Board

# (direction pair) in the neighbour table: UP=0, DOWN=1, LEFT=2, RIGHT=3
_AXES = ((2, 3), (0, 1))


def dead_cells(board: Board) -> bytearray:
    """1 for every cell from which a lone box can never reach any goal."""
    return bytearray(1 if d == UNREACHABLE else 0 for d in goal_distances(board))


def dead_squares(level: Level) -> frozenset[Pos]:
    """Floor cells from which a box can never reach any goal (corners off goal, dead walls...)."""
    board = Board(level)
    return frozenset(board.cells[i] for i, dead in enumerate(dead_cells(board)) if dead)


class FreezeChecker:
    """Freeze deadlock test on indices, reused by the search for every push."""

    def __init__(self, board: Board, dead: bytearray) -> None:
        self.nbr = board.nbr
        self.goals = board.goals
        self.dead = dead

    def is_deadlock(self, occ: bytearray, cell: int) -> bool:
        """True when the box on ``cell`` can never move again and the frozen group has a box off goal."""
        nbr, dead, base = self.nbr, self.dead, cell * 4
        for first, second in _AXES:  # fast path: an axis with two free, live neighbours lets the box move
            a, b = nbr[base + first], nbr[base + second]
            if a >= 0 and b >= 0 and not occ[a] and not occ[b] and not (dead[a] and dead[b]):
                return False
        group: list[int] = []
        if not self._frozen(occ, cell, set(), group):
            return False
        return any(b not in self.goals for b in group)

    def _frozen(self, occ: bytearray, cell: int, walls: set[int], group: list[int]) -> bool:
        # The boxes being examined up the call chain count as walls; a box found frozen joins `group`.
        mark = len(group)
        walls.add(cell)
        frozen = self._axis_blocked(occ, cell, _AXES[0], walls, group) and self._axis_blocked(
            occ, cell, _AXES[1], walls, group
        )
        walls.discard(cell)
        if frozen:
            group.append(cell)
        else:
            del group[mark:]
        return frozen

    def _axis_blocked(
        self, occ: bytearray, cell: int, axis: tuple[int, int], walls: set[int], group: list[int]
    ) -> bool:
        a = self.nbr[cell * 4 + axis[0]]
        b = self.nbr[cell * 4 + axis[1]]
        if a < 0 or b < 0 or a in walls or b in walls:
            return True
        if self.dead[a] and self.dead[b]:
            return True
        return bool(occ[a] and self._frozen(occ, a, walls, group)) or bool(
            occ[b] and self._frozen(occ, b, walls, group)
        )


def is_frozen(level: Level, boxes: frozenset[Pos], moved: Pos) -> bool:
    """True when the box on ``moved`` is part of a frozen group with at least one box off goal."""
    board = Board(level)
    checker = FreezeChecker(board, dead_cells(board))
    return checker.is_deadlock(board.occupancy(board.index[b] for b in boxes), board.index[moved])
