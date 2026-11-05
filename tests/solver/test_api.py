from typing import Any

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver import api, search
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveLimits, SolveResult, SolveStatus, solve

LV = Level.from_rows(["######", "#@$ .#", "#    #", "######"])


def test_solve_rejects_mismatched_state() -> None:
    r = solve(LV, boxes=frozenset({(1, 1), (1, 2)}))
    assert r.status is SolveStatus.INVALID
    assert (r.lurd, r.pushes, r.moves, r.nodes_expanded, r.nodes_generated) == (None, None, None, 0, 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"boxes": frozenset({(0, 0)})},  # box on a wall
        {"boxes": frozenset()},  # no box for one goal
        {"player": (0, 3)},  # player on a wall
        {"player": (1, 2)},  # player on the box
        {"player": (9, 9)},  # player off the grid
    ],
)
def test_solve_rejects_off_floor_states(kwargs: dict[str, Any]) -> None:
    assert solve(LV, **kwargs).status is SolveStatus.INVALID


def test_solve_delegates_to_search(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, ...]] = []
    done = SolveResult(SolveStatus.SOLVED, "rR", 1, 2, 3, 4, 5)

    def fake_run_search(*args: Any) -> SolveResult:
        calls.append(args)
        return done

    monkeypatch.setattr(search, "run_search", fake_run_search)

    def stop() -> bool:
        return False

    limits = SolveLimits(time_s=1.5, max_nodes=10)
    assert solve(LV, player=(2, 1), limits=limits, mode="fast", should_stop=stop) is done
    assert calls == [(LV, LV.boxes, (2, 1), limits, "fast", stop, None)]
    assert solve(LV) is done
    assert calls[1] == (LV, LV.boxes, LV.player, SolveLimits(), "optimal", None, None)


def test_contract_values() -> None:
    assert SOLVER_ID == "push-astar/1"
    assert SolveLimits() == SolveLimits(time_s=10.0, max_nodes=1_000_000)
    assert [s.value for s in SolveStatus] == [
        "solved",
        "unsolvable",
        "limit_time",
        "limit_nodes",
        "cancelled",
        "invalid",
    ]
    assert SolveStatus.SOLVED == "solved"
    assert api.Mode is not None and api.ProgressCallback is not None
