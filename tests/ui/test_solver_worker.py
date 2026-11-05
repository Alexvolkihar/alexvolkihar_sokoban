import threading
import time
from collections.abc import Callable

import pytest

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui import solver_worker
from alexvolkihar_sokoban.ui.solver_worker import SolverWorker
from tests.ui.game_helpers import ONE_BOX

LIMITS = SolveLimits(time_s=5.0, max_nodes=100_000)


def wait_poll(worker: SolverWorker, timeout: float = 5.0) -> tuple[object, SolveResult]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        got = worker.poll()
        if got is not None:
            return got
        time.sleep(0.005)
    raise AssertionError("no result in time")


def blocking_solve(release: threading.Event, calls: list[dict[str, object]]) -> Callable[..., SolveResult]:
    """A fake solver that waits for ``release`` (or for ``should_stop``) and reports what it was asked."""

    def fake(level: Level, **kw: object) -> SolveResult:
        calls.append(kw)
        should_stop = kw["should_stop"]
        assert callable(should_stop)
        while not release.is_set():
            if should_stop():
                return SolveResult(SolveStatus.CANCELLED, None, None, None, 0, 0, 0)
            on_progress = kw["on_progress"]
            assert callable(on_progress)
            on_progress(42, 7)
            time.sleep(0.002)
        return SolveResult(SolveStatus.SOLVED, "rU", 1, 2, 3, 4, 5)

    return fake


def test_worker_returns_result_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = SolverWorker()
    assert not worker.busy and worker.poll() is None
    worker.start(ONE_BOX, ONE_BOX.boxes, ONE_BOX.player, LIMITS, tag="first")
    tag, result = wait_poll(worker)
    assert tag == "first" and result.status is SolveStatus.SOLVED and result.lurd == "rU"
    assert not worker.busy and worker.poll() is None  # a result is delivered once

    release = threading.Event()
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(solver_worker, "solve", blocking_solve(release, calls))
    worker.start(ONE_BOX, ONE_BOX.boxes, ONE_BOX.player, LIMITS, mode="fast", tag="second")
    assert worker.busy
    worker.cancel()
    assert worker.join(2.0)
    assert not worker.busy and worker.poll() is None  # a cancelled job never delivers
    assert calls[0]["mode"] == "fast" and calls[0]["limits"] == LIMITS


def test_start_cancels_the_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(solver_worker, "solve", blocking_solve(release, calls))
    worker = SolverWorker()
    worker.start(ONE_BOX, ONE_BOX.boxes, ONE_BOX.player, LIMITS, tag="old")
    worker.start(ONE_BOX, ONE_BOX.boxes, ONE_BOX.player, LIMITS, tag="new")
    release.set()
    tag, _ = wait_poll(worker)
    assert tag == "new"
    assert worker.join(2.0) and worker.poll() is None


def test_progress_is_reported_while_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    monkeypatch.setattr(solver_worker, "solve", blocking_solve(release, []))
    worker = SolverWorker()
    assert worker.progress is None
    worker.start(ONE_BOX, ONE_BOX.boxes, ONE_BOX.player, LIMITS)
    deadline = time.monotonic() + 2.0
    while worker.progress is None and time.monotonic() < deadline:
        time.sleep(0.005)
    assert worker.progress == (42, 7)
    release.set()
    wait_poll(worker)
    assert worker.progress is None


def test_a_crashing_solver_reports_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(level: Level, **kw: object) -> SolveResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(solver_worker, "solve", broken)
    worker = SolverWorker()
    boxes: frozenset[Pos] = ONE_BOX.boxes
    worker.start(ONE_BOX, boxes, ONE_BOX.player, LIMITS, tag=1)
    tag, result = wait_poll(worker)
    assert tag == 1 and result.status is SolveStatus.INVALID
