"""Push distances to the goals, computed backwards by pulling boxes away from them (spec 7.4)."""

from __future__ import annotations

from collections.abc import Iterable

from alexvolkihar_sokoban.solver.reachability import OPPOSITE, Board

UNREACHABLE = -1


def pull_distances(board: Board, sources: Iterable[int]) -> list[int]:
    """Fewest pushes that bring a lone box from each cell onto one of ``sources``.

    Other boxes are ignored and the player is assumed able to walk anywhere, so the values are lower
    bounds. ``UNREACHABLE`` marks cells from which no source can ever be reached.
    """
    nbr = board.nbr
    dist = [UNREACHABLE] * board.size
    queue: list[int] = []
    for s in sources:
        if dist[s] == UNREACHABLE:
            dist[s] = 0
            queue.append(s)
    for cell in queue:  # breadth-first: the list grows while it is iterated
        nd = dist[cell] + 1
        for d in range(4):
            back = OPPOSITE[d]
            prev = nbr[cell * 4 + back]  # the box came from here, pushed in direction d
            if prev < 0 or dist[prev] != UNREACHABLE:
                continue
            if nbr[prev * 4 + back] >= 0:  # room for the player behind the box
                dist[prev] = nd
                queue.append(prev)
    return dist


def goal_distances(board: Board) -> list[int]:
    """Fewest pushes from each cell to the nearest goal (``UNREACHABLE`` on dead squares)."""
    return pull_distances(board, board.goals)
