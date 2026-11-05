"""Admissible lower bound on the pushes left (spec 7.4).

First version from the spec: the sum over boxes of each box's push distance to its nearest goal. A push
moves one box by one cell, so it changes the sum by at most one: the bound is consistent, and A* with it
returns push-optimal solutions. The search updates it incrementally (one box changes per push).
"""

from __future__ import annotations

from collections.abc import Iterable

from alexvolkihar_sokoban.solver.distances import goal_distances
from alexvolkihar_sokoban.solver.reachability import Board


def box_costs(board: Board) -> list[int]:
    """Per-cell cost of a box: pushes to the nearest goal, negative on dead squares."""
    return goal_distances(board)


def lower_bound(costs: list[int], boxes: Iterable[int]) -> int:
    """Sum of the box costs; only meaningful when no box stands on a dead square."""
    return sum(costs[b] for b in boxes)
