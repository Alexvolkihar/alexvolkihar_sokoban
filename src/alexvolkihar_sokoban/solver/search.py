"""Push-based A* search (stub; plan Task 5 owns this file)."""

from __future__ import annotations

from collections.abc import Callable

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.api import Mode, ProgressCallback, SolveLimits, SolveResult


def run_search(
    level: Level,
    boxes: frozenset[Pos],
    player: Pos,
    limits: SolveLimits,
    mode: Mode,
    should_stop: Callable[[], bool] | None,
    on_progress: ProgressCallback | None,
) -> SolveResult:
    """Search from an already validated state. Called by ``solver.api.solve`` only."""
    raise NotImplementedError("the push-based search is not implemented yet")
