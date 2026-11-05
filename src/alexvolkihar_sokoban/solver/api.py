"""Public solver API (spec 7.4), frozen for every caller: CLI, hints, annotate, benchmark, generator.

The search itself lives in ``solver.search.run_search``; it imports its types from here, never the reverse
at module level.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level

SOLVER_ID = "push-astar/1"

Mode = Literal["optimal", "fast"]
ProgressCallback = Callable[[int, int], None]
"""Called with ``(nodes_expanded, elapsed_ms)`` while the search runs."""


class SolveStatus(StrEnum):
    SOLVED = "solved"
    UNSOLVABLE = "unsolvable"
    LIMIT_TIME = "limit_time"
    LIMIT_NODES = "limit_nodes"
    CANCELLED = "cancelled"
    INVALID = "invalid"


@dataclass(frozen=True)
class SolveLimits:
    """Both limits are always enforced."""

    time_s: float = 10.0
    max_nodes: int = 1_000_000


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    lurd: str | None
    pushes: int | None
    moves: int | None
    nodes_expanded: int
    nodes_generated: int
    elapsed_ms: int


def _invalid() -> SolveResult:
    return SolveResult(SolveStatus.INVALID, None, None, None, 0, 0, 0)


def solve(
    level: Level,
    *,
    boxes: frozenset[Pos] | None = None,
    player: Pos | None = None,
    limits: SolveLimits = SolveLimits(),
    mode: Mode = "optimal",
    should_stop: Callable[[], bool] | None = None,
    on_progress: ProgressCallback | None = None,
) -> SolveResult:
    """Solve ``level`` from its start, or from ``boxes``/``player`` when given (hints from mid-game).

    Returns ``INVALID`` without searching when the box count differs from the goal count, or when a box or
    the player is off the floor (or the player stands on a box). An already solved start state returns
    ``SOLVED`` with an empty LURD without searching.
    """
    start_boxes = level.boxes if boxes is None else boxes
    start_player = level.player if player is None else player
    if (
        len(start_boxes) != len(level.goals)
        or not start_boxes <= level.floor
        or start_player not in level.floor
        or start_player in start_boxes
    ):
        return _invalid()
    if start_boxes == level.goals:
        return SolveResult(SolveStatus.SOLVED, "", 0, 0, 0, 0, 0)

    from alexvolkihar_sokoban.solver import search  # late import: search depends on this module

    return search.run_search(level, start_boxes, start_player, limits, mode, should_stop, on_progress)
