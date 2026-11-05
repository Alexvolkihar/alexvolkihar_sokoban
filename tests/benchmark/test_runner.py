import dataclasses
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from alexvolkihar_sokoban import __version__
from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult, Summary, run_suite
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus, solve

LV1 = Level.from_rows(["#####", "#@$.#", "#####"])
LV2 = Level.from_rows(["######", "#@$ .#", "######"])
LV3 = Level.from_rows(["######", "#@ $.#", "######"])
PACK = Pack("p", "P", (LevelEntry("1", LV1), LevelEntry("2", LV2), LevelEntry("3", LV3)))
ITEMS = [(PACK, e) for e in PACK.levels]
LIMITS = SolveLimits(5.0, 1000)
WHEN = datetime(2026, 11, 5, 14, 3, 22, 123456, tzinfo=UTC)

RESULTS = {
    LV1: SolveResult(SolveStatus.SOLVED, "R", 1, 1, 10, 30, 100),
    LV2: SolveResult(SolveStatus.LIMIT_TIME, None, None, None, 2000, 5000, 400),
    LV3: SolveResult(SolveStatus.SOLVED, "rR", 1, 2, 990, 1000, 1500),
}


class FakeSolver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, level: Level, **kwargs: Any) -> SolveResult:
        self.calls.append(kwargs)
        return RESULTS[level]


def test_runner_with_fake_solver() -> None:
    fake = FakeSolver()
    run = run_suite(ITEMS, suite_id="quick", limits=LIMITS, solve_fn=fake, now=lambda: WHEN)
    assert isinstance(run, BenchmarkRun)
    assert run.created_at == "2026-11-05T14:03:22Z"
    assert re.fullmatch(r"2026-11-05T14-03-22Z-[0-9a-f]{4}", run.run_id)
    assert run.app_version == __version__
    assert run.solver == {"name": "push-astar", "version": "1", "mode": "optimal"}
    assert run.suite_id == "quick" and run.limits == LIMITS
    assert [c["limits"] for c in fake.calls] == [LIMITS] * 3
    assert [(r.pack_id, r.level_id, r.status) for r in run.results] == [
        ("p", "1", SolveStatus.SOLVED),
        ("p", "2", SolveStatus.LIMIT_TIME),
        ("p", "3", SolveStatus.SOLVED),
    ]
    first = run.results[0]
    assert first == LevelResult(
        "p", "1", LV1.canonical_hash(), SolveStatus.SOLVED, 1, 1, 10, 30, 100, first.peak_mem_bytes
    )
    assert all(r.peak_mem_bytes >= 0 for r in run.results)
    total_nodes = 10 + 2000 + 990
    assert run.summary == Summary(solved=2, total=3, total_ms=2000, nodes_per_s=total_nodes * 1000 // 2000)


def test_runner_is_deterministic_apart_from_the_random_suffix() -> None:
    def strip(run: BenchmarkRun) -> BenchmarkRun:
        results = tuple(dataclasses.replace(r, peak_mem_bytes=0) for r in run.results)
        return dataclasses.replace(run, run_id=run.run_id[:-4], results=results)

    a = run_suite(ITEMS, suite_id="q", limits=LIMITS, solve_fn=FakeSolver(), now=lambda: WHEN)
    b = run_suite(ITEMS, suite_id="q", limits=LIMITS, solve_fn=FakeSolver(), now=lambda: WHEN)
    assert strip(a) == strip(b)


def test_runner_reports_progress() -> None:
    events: list[tuple[str, int, object]] = []
    run_suite(
        ITEMS,
        suite_id="q",
        limits=LIMITS,
        solve_fn=FakeSolver(),
        on_level_start=lambda i, n, e: events.append(("start", i, (n, e.id))),
        on_level_done=lambda i, r: events.append(("done", i, r.level_id)),
        now=lambda: WHEN,
    )
    assert events == [
        ("start", 0, (3, "1")),
        ("done", 0, "1"),
        ("start", 1, (3, "2")),
        ("done", 1, "2"),
        ("start", 2, (3, "3")),
        ("done", 2, "3"),
    ]


def test_runner_stops_on_should_stop() -> None:
    done: list[str] = []
    fake = FakeSolver()
    run = run_suite(
        ITEMS,
        suite_id="q",
        limits=LIMITS,
        solve_fn=fake,
        on_level_done=lambda i, r: done.append(r.level_id),
        should_stop=lambda: len(done) >= 1,
        now=lambda: WHEN,
    )
    assert [r.level_id for r in run.results] == ["1"]
    assert run.summary.total == 1
    stop: Callable[[], bool] = fake.calls[0]["should_stop"]
    assert stop() is True  # the solver is handed the same flag, so a long solve is cancelled too


def test_runner_with_no_items_has_an_empty_summary() -> None:
    run = run_suite([], suite_id="q", limits=LIMITS, solve_fn=FakeSolver(), now=lambda: WHEN)
    assert run.results == () and run.summary == Summary(0, 0, 0, 0)


def test_runner_with_the_real_solver_measures_memory() -> None:
    run = run_suite(ITEMS, suite_id="q", limits=LIMITS, solve_fn=solve)
    assert [r.status for r in run.results] == [SolveStatus.SOLVED] * 3
    assert run.results[1].pushes == 2 and run.results[1].peak_mem_bytes > 0
