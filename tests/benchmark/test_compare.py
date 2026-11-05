import dataclasses

from alexvolkihar_sokoban.benchmark.compare import compare, format_comparison
from alexvolkihar_sokoban.benchmark.machine import MachineInfo
from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult, Summary
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveStatus

MACHINE = MachineInfo("Linux", "6.8", "x86_64", False, "CPU A", 8, None, "CPython 3.13.1", None, "0.1.0")
H1, H2, H3 = ("sha256:" + c * 64 for c in "abc")


def result(level_id: str, h: str, status: SolveStatus, ms: int, nodes: int) -> LevelResult:
    pushes = 3 if status is SolveStatus.SOLVED else None
    return LevelResult("p", level_id, h, status, pushes, pushes, nodes, nodes * 2, ms, 1000)


def run(run_id: str, *results: LevelResult) -> BenchmarkRun:
    total_ms = sum(r.elapsed_ms for r in results)
    nodes = sum(r.nodes_expanded for r in results)
    solved = sum(r.status is SolveStatus.SOLVED for r in results)
    return BenchmarkRun(
        run_id,
        "2026-11-05T14:03:22Z",
        "0.1.0",
        {"name": "push-astar", "version": "1", "mode": "optimal"},
        MACHINE,
        "quick",
        SolveLimits(),
        tuple(results),
        Summary(solved, len(results), total_ms, nodes * 1000 // total_ms if total_ms else 0),
    )


A = run(
    "a",
    result("1", H1, SolveStatus.SOLVED, 100, 1000),
    result("2", H2, SolveStatus.SOLVED, 400, 4000),
    result("3", H3, SolveStatus.SOLVED, 50, 10),
)
B = run(
    "b",
    result("1", H1, SolveStatus.SOLVED, 50, 1000),
    result("2", H2, SolveStatus.LIMIT_TIME, 800, 9000),
    result("4", "sha256:" + "d" * 64, SolveStatus.SOLVED, 5, 5),
)


def test_compare_reports_time_delta_and_status_change() -> None:
    c = compare(A, B)
    by_id = {d.level_id: d for d in c.levels}
    assert by_id["1"].time_pct == -50.0 and not by_id["1"].status_changed
    assert by_id["2"].time_pct == 100.0 and by_id["2"].status_changed
    assert by_id["2"].nodes_delta == 5000
    assert by_id["3"].b is None and by_id["4"].a is None
    assert by_id["3"].time_pct is None and by_id["3"].nodes_delta is None
    assert [d.level_id for d in c.levels] == ["1", "2", "3", "4"]
    assert c.total_ms == (550, 855)
    assert c.solved == (3, 2)
    assert c.changed == ("p/2",)


def test_compare_matches_levels_by_hash() -> None:
    renamed = run("b", dataclasses.replace(A.results[0], level_id="one"))
    c = compare(A, renamed)
    assert [(d.a is not None, d.b is not None) for d in c.levels if d.a and d.a.level_id == "1"] == [
        (True, True)
    ]


def test_time_pct_with_a_zero_reference_is_none() -> None:
    a = run("a", result("1", H1, SolveStatus.SOLVED, 0, 1))
    b = run("b", result("1", H1, SolveStatus.SOLVED, 7, 1))
    assert compare(a, b).levels[0].time_pct is None


def test_format_comparison_lists_levels_totals_and_flags() -> None:
    text = format_comparison(compare(A, B))
    assert "p/1" in text and "-50.0%" in text and "+100.0%" in text
    assert "solved -> limit_time" in text
    assert "total" in text.lower()
    assert "a" in text and "b" in text
