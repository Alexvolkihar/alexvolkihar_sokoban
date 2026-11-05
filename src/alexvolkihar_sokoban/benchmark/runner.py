"""Run a benchmark suite: solve each level once, in-process, with ``tracemalloc`` on (spec 7.7)."""

from __future__ import annotations

import secrets
import tracemalloc
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from alexvolkihar_sokoban import __version__
from alexvolkihar_sokoban.benchmark.machine import MachineInfo, collect_machine_info
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveLimits, SolveResult, SolveStatus, solve

MODE = "optimal"
MEASURE = "tracemalloc"


@dataclass(frozen=True)
class LevelResult:
    pack_id: str
    level_id: str
    level_hash: str
    status: SolveStatus
    pushes: int | None
    moves: int | None
    nodes_expanded: int
    nodes_generated: int
    elapsed_ms: int
    peak_mem_bytes: int

    @property
    def label(self) -> str:
        return f"{self.pack_id}/{self.level_id}"


@dataclass(frozen=True)
class Summary:
    solved: int
    total: int
    total_ms: int
    nodes_per_s: int
    """Nodes expanded per second over the whole run: the headline "machine score"."""


@dataclass(frozen=True)
class BenchmarkRun:
    run_id: str
    created_at: str
    app_version: str
    solver: dict[str, str]
    machine: MachineInfo
    suite_id: str
    limits: SolveLimits
    results: tuple[LevelResult, ...]
    summary: Summary


def solver_info() -> dict[str, str]:
    name, _, version = SOLVER_ID.partition("/")
    return {"name": name, "version": version, "mode": MODE}


def summarize(results: Sequence[LevelResult]) -> Summary:
    total_ms = sum(r.elapsed_ms for r in results)
    nodes = sum(r.nodes_expanded for r in results)
    return Summary(
        solved=sum(r.status is SolveStatus.SOLVED for r in results),
        total=len(results),
        total_ms=total_ms,
        nodes_per_s=nodes * 1000 // total_ms if total_ms > 0 else 0,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def run_suite(
    items: Sequence[tuple[Pack, LevelEntry]],
    *,
    suite_id: str,
    limits: SolveLimits,
    solve_fn: Callable[..., SolveResult] = solve,
    on_level_start: Callable[[int, int, LevelEntry], None] | None = None,
    on_level_done: Callable[[int, LevelResult], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    now: Callable[[], datetime] | None = None,
) -> BenchmarkRun:
    """Solve every item once, in order. ``should_stop`` is checked before each level and handed to the
    solver, so a stop request also cancels the level being solved (it is kept with its ``cancelled``
    status) and no further level starts.
    """
    created_at = (now or _utc_now)().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = f"{created_at.replace(':', '-')}-{secrets.token_hex(2)}"
    results: list[LevelResult] = []
    started_tracing = not tracemalloc.is_tracing()
    if started_tracing:
        tracemalloc.start()
    try:
        for index, (pack, entry) in enumerate(items):
            if should_stop is not None and should_stop():
                break
            if on_level_start is not None:
                on_level_start(index, len(items), entry)
            tracemalloc.reset_peak()
            outcome = solve_fn(entry.level, limits=limits, mode=MODE, should_stop=should_stop)
            peak = tracemalloc.get_traced_memory()[1]
            result = LevelResult(
                pack_id=pack.id,
                level_id=entry.id,
                level_hash=entry.level.canonical_hash(),
                status=outcome.status,
                pushes=outcome.pushes,
                moves=outcome.moves,
                nodes_expanded=outcome.nodes_expanded,
                nodes_generated=outcome.nodes_generated,
                elapsed_ms=outcome.elapsed_ms,
                peak_mem_bytes=peak,
            )
            results.append(result)
            if on_level_done is not None:
                on_level_done(index, result)
    finally:
        if started_tracing:
            tracemalloc.stop()
    return BenchmarkRun(
        run_id=run_id,
        created_at=created_at,
        app_version=__version__,
        solver=solver_info(),
        machine=collect_machine_info(),
        suite_id=suite_id,
        limits=limits,
        results=tuple(results),
        summary=summarize(results),
    )
