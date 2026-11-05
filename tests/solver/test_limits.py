import time

from alexvolkihar_sokoban.solver.api import SolveLimits, SolveStatus, solve
from tests.solver.levels import BIG, LEVELS


def test_node_limit_is_enforced() -> None:
    r = solve(BIG, limits=SolveLimits(time_s=30, max_nodes=500))
    assert r.status is SolveStatus.LIMIT_NODES
    assert r.nodes_expanded <= 500
    assert (r.lurd, r.pushes, r.moves) == (None, None, None)


def test_zero_node_limit_stops_before_searching() -> None:
    r = solve(LEVELS["test3"], limits=SolveLimits(max_nodes=0))
    assert r.status is SolveStatus.LIMIT_NODES and r.nodes_expanded == 0


def test_time_limit_is_enforced() -> None:
    started = time.monotonic()
    r = solve(BIG, limits=SolveLimits(time_s=0.05))
    assert r.status is SolveStatus.LIMIT_TIME
    assert r.elapsed_ms < 1000
    assert time.monotonic() - started < 1.0


def test_should_stop_cancels() -> None:
    r = solve(BIG, should_stop=lambda: True)
    assert r.status is SolveStatus.CANCELLED
    assert r.lurd is None


def test_should_stop_is_polled_during_the_search() -> None:
    calls = 0

    def stop_later() -> bool:
        nonlocal calls
        calls += 1
        return calls > 3

    r = solve(BIG, should_stop=stop_later)
    assert r.status is SolveStatus.CANCELLED and r.nodes_expanded > 0


def test_cancel_wins_over_a_limit() -> None:
    r = solve(BIG, limits=SolveLimits(max_nodes=0), should_stop=lambda: True)
    assert r.status is SolveStatus.CANCELLED


def test_progress_callback_called() -> None:
    seen: list[tuple[int, int]] = []
    solve(BIG, limits=SolveLimits(max_nodes=3000), on_progress=lambda n, ms: seen.append((n, ms)))
    assert len(seen) >= 2
    assert [n for n, _ in seen] == sorted(n for n, _ in seen)
    assert all(ms >= 0 for _, ms in seen)


def test_progress_callback_called_once_on_a_quick_solve() -> None:
    seen: list[tuple[int, int]] = []
    r = solve(LEVELS["test1"], on_progress=lambda n, ms: seen.append((n, ms)))
    assert r.status is SolveStatus.SOLVED
    assert seen and seen[-1][0] == r.nodes_expanded
