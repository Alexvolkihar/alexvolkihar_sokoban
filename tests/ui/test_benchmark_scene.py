import csv
import dataclasses
import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.benchmark.export import read_json, write_json
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui import scenes
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes import benchmark
from alexvolkihar_sokoban.ui.scenes.benchmark import BenchmarkScene, status_label, suite_title


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


DOWN = key(pygame.K_DOWN, 81)
UP = key(pygame.K_UP, 82)
LEFT = key(pygame.K_LEFT, 80)
RIGHT = key(pygame.K_RIGHT, 79)
ENTER = key(pygame.K_RETURN, 40)
ESCAPE = key(pygame.K_ESCAPE, 41)

QUICK_LEVELS = 12  # first-steps


def solved(level: Level, **_: object) -> SolveResult:
    return SolveResult(SolveStatus.SOLVED, "R", 3, 10, 1000, 2500, 20)


def bench_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    solve_fn: Callable[..., SolveResult] = solved,
    *,
    language: str = "en",
    size: tuple[int, int] = (1024, 768),
) -> tuple[App, BenchmarkScene]:
    monkeypatch.setattr(benchmark, "solve", solve_fn)
    ctx = AppContext.load(tmp_path, bundled=[])
    ctx.settings.language = language  # type: ignore[assignment]
    ctx.settings.window = size
    set_language(ctx.settings.language)
    app = App(ctx.settings, context=ctx, headless=True)
    scene = app.push("benchmark")
    assert isinstance(scene, BenchmarkScene)
    return app, scene


def step_until(app: App, condition: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app.step([], 16)
        time.sleep(0.002)


def run_quick(app: App, scene: BenchmarkScene) -> None:
    assert scene.selected_suite is not None and scene.selected_suite.id == "quick"
    app.step([ENTER])  # a fast fake solver may already be done when this step updates the scene
    assert scene.view in ("running", "results")
    step_until(app, lambda: scene.view == "results")


def bench_files(tmp_path: Path, suffix: str = ".json") -> list[Path]:
    return sorted((tmp_path / "benchmarks").glob(f"*{suffix}"))


# --- suite picker ----------------------------------------------------------------------------------------


def test_scene_is_registered() -> None:
    assert scenes.load_scene_class("benchmark") is BenchmarkScene


def test_picker_lists_bundled_suites_with_translated_titles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, scene = bench_app(tmp_path, monkeypatch, language="fr")
    assert [s.id for s in scene.suites] == ["quick", "standard", "stress"]
    assert scene.selected_suite is not None and scene.selected_suite.id == "quick"
    assert suite_title("quick", "Quick") == "Rapide"
    assert suite_title("someday", "Someday") == "Someday"  # unknown id: the file's English title


def test_bundled_suites_miss_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, scene = bench_app(tmp_path, monkeypatch)
    assert [scene.missing_line(suite) for suite in scene.suites] == [None, None, None]


def test_missing_items_are_a_warning_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    scene.suites[1] = dataclasses.replace(scene.suites[1], items=("first-steps", "not-installed/1"))
    line = scene.missing_line(scene.suites[1])
    assert line is not None and "not-installed" in line
    app.step([DOWN])
    app.step([])  # draws the warning without error


@pytest.mark.parametrize("language", ["en", "fr"])
def test_suite_descriptions_name_only_shipped_packs(language: str) -> None:
    set_language(language)
    for suite_id in ("quick", "standard", "stress"):
        assert "microban" not in benchmark.suite_description(suite_id).lower()
    assert "Boxoban" in benchmark.suite_description("standard")


def test_back_from_the_picker_leaves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = bench_app(tmp_path, monkeypatch)
    app.step([ESCAPE])
    assert app.top is None


# --- running ---------------------------------------------------------------------------------------------


def test_scene_runs_quick_suite_with_fake_solver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    run = scene.run
    assert run is not None and run.suite_id == "quick" and not scene.cancelled
    assert run.summary.solved == run.summary.total == QUICK_LEVELS
    assert [r.level_id for r in scene.results] == [e.id for e in scene.packs["first-steps"].levels]
    assert scene.saved_path == tmp_path / "benchmarks" / f"{run.run_id}.json"
    assert read_json(scene.saved_path) == run  # auto-saved
    app.step([])  # results table with the machine panel


def test_live_progress_shows_level_and_elapsed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[int] = []

    def slow(level: Level, **kw: object) -> SolveResult:
        calls.append(1)
        if len(calls) == 2:
            release.wait(10)
        return solved(level)

    app, scene = bench_app(tmp_path, monkeypatch, slow)
    app.step([ENTER])
    step_until(app, lambda: len(scene.results) == 1 and scene.current is not None and scene.current[0] == 1)
    app.step([], 1500)
    text = scene.progress_text()
    assert f"2/{QUICK_LEVELS}" in text and "Two crates" in text and "1.5 s" in text
    release.set()
    step_until(app, lambda: scene.view == "results")


def test_cancel_stops_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def until_stopped(level: Level, *, should_stop: Callable[[], bool], **_: object) -> SolveResult:
        while not should_stop():
            time.sleep(0.001)
        return SolveResult(SolveStatus.CANCELLED, None, None, None, 7, 9, 3)

    app, scene = bench_app(tmp_path, monkeypatch, until_stopped)
    app.step([ENTER])
    step_until(app, lambda: scene.current is not None)
    app.step([ESCAPE])
    step_until(app, lambda: scene.view == "results")
    assert scene.cancelled and scene.run is not None
    assert [r.status for r in scene.run.results] == [SolveStatus.CANCELLED]
    assert bench_files(tmp_path) == []  # a cancelled run is not saved on its own
    app.step([])
    app.step([ESCAPE])
    assert scene.view == "suites" and app.top is scene


def test_solver_error_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(level: Level, **_: object) -> SolveResult:
        raise RuntimeError("boom")

    app, scene = bench_app(tmp_path, monkeypatch, broken)
    app.step([ENTER])
    step_until(app, lambda: scene.view != "running")
    assert scene.view == "suites" and "boom" in scene.message
    app.step([])


def test_leaving_while_running_stops_the_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stopped = threading.Event()

    def until_stopped(level: Level, *, should_stop: Callable[[], bool], **_: object) -> SolveResult:
        while not should_stop():
            time.sleep(0.001)
        stopped.set()
        return SolveResult(SolveStatus.CANCELLED, None, None, None, 0, 0, 0)

    app, scene = bench_app(tmp_path, monkeypatch, until_stopped)
    app.step([ENTER])
    step_until(app, lambda: scene.current is not None)
    app.quit()
    assert stopped.wait(5)


# --- results, export, compare ----------------------------------------------------------------------------


def choose_action(app: App, scene: BenchmarkScene, action_id: str) -> None:
    ids = [a for a, _ in scene.actions()]
    for _ in range(len(ids)):
        if ids[scene.action_index] == action_id:
            break
        app.step([RIGHT])
    assert ids[scene.action_index] == action_id
    app.step([ENTER])


def test_export_csv_writes_one_row_per_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    choose_action(app, scene, "export_csv")
    (path,) = bench_files(tmp_path, ".csv")
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 1 + QUICK_LEVELS
    assert path.name in scene.message


def test_export_json_after_a_cancelled_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def until_stopped(level: Level, *, should_stop: Callable[[], bool], **_: object) -> SolveResult:
        while not should_stop():
            time.sleep(0.001)
        return SolveResult(SolveStatus.CANCELLED, None, None, None, 0, 0, 0)

    app, scene = bench_app(tmp_path, monkeypatch, until_stopped)
    app.step([ENTER])
    step_until(app, lambda: scene.current is not None)
    app.step([ESCAPE])
    step_until(app, lambda: scene.view == "results")
    choose_action(app, scene, "export_json")
    (path,) = bench_files(tmp_path)
    assert scene.run is not None and read_json(path) == scene.run


def test_results_saved_and_comparable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    first = scene.run
    assert first is not None

    def slower(level: Level, **_: object) -> SolveResult:
        if level is first_level:
            return SolveResult(SolveStatus.LIMIT_TIME, None, None, None, 4000, 9000, 40)
        return SolveResult(SolveStatus.SOLVED, "R", 3, 10, 1000, 2500, 30)

    first_level = scene.packs["first-steps"].levels[0].level
    monkeypatch.setattr(benchmark, "solve", slower)
    app.step([ESCAPE])  # back to the picker
    run_quick(app, scene)
    second = scene.run
    assert second is not None and len(bench_files(tmp_path)) == 2

    choose_action(app, scene, "compare")
    assert scene.view == "runs"
    assert [r.run_id for _, r in scene.saved_runs] == [first.run_id]  # the current run is not listed
    app.step([ENTER])
    assert scene.view == "compare" and scene.comparison is not None
    c = scene.comparison
    assert c.a == first and c.b == second
    assert c.changed == (f"first-steps/{scene.packs['first-steps'].levels[0].id}",)
    delta = c.levels[1]
    assert delta.time_pct == pytest.approx(50.0)
    app.step([])  # comparison table
    app.step([ESCAPE])
    assert scene.view == "results"


def test_compare_prefers_the_latest_run_of_the_same_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    quick = scene.run
    assert quick is not None
    other = dataclasses.replace(quick, run_id="9999-other", suite_id="stress")
    write_json(other, tmp_path / "benchmarks" / "9999-other.json")
    (tmp_path / "benchmarks" / "broken.json").write_text("{", encoding="utf-8")
    app.step([ESCAPE])
    run_quick(app, scene)
    choose_action(app, scene, "compare")
    ids = [r.run_id for _, r in scene.saved_runs]
    assert ids == ["9999-other", quick.run_id]  # newest first, unreadable files skipped
    assert scene.saved_runs[scene.runs_scroll.selected][1].run_id == quick.run_id


def test_compare_without_previous_run_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    choose_action(app, scene, "compare")
    assert scene.view == "runs" and scene.saved_runs == []
    app.step([ENTER])  # nothing to compare
    assert scene.view == "runs"
    app.step([])
    app.step([ESCAPE])
    assert scene.view == "results"


def test_saved_runs_can_be_opened_from_the_picker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    run = scene.run
    app.step([ESCAPE])
    for _ in scene.suites:
        app.step([DOWN])
    assert scene.selected_suite is None  # the "saved runs" row
    app.step([ENTER])
    assert scene.view == "runs"
    app.step([ENTER])
    assert scene.view == "results" and scene.run == run and scene.saved_path is not None
    app.step([ESCAPE])
    assert scene.view == "runs"


def test_save_failure_is_a_message_not_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = bench_app(tmp_path, monkeypatch)
    (tmp_path / "benchmarks").write_text("not a folder", encoding="utf-8")
    run_quick(app, scene)
    assert scene.saved_path is None and scene.message
    app.step([])


# --- labels and drawing ----------------------------------------------------------------------------------


def test_status_labels_are_translated() -> None:
    set_language("fr")
    assert status_label(SolveStatus.SOLVED) == "résolu"
    set_language("en")
    assert status_label(SolveStatus.LIMIT_NODES) == "node limit"
    assert len({status_label(s) for s in SolveStatus}) == len(SolveStatus)


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_every_view_draws_at_any_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int], language: str
) -> None:
    app, scene = bench_app(tmp_path, monkeypatch, language=language, size=size)
    app.step([])
    run_quick(app, scene)
    app.step([UP, DOWN])
    choose_action(app, scene, "compare")
    app.step([])
    app.step([ESCAPE])
    app.step([ESCAPE])
    run_quick(app, scene)
    choose_action(app, scene, "compare")
    app.step([ENTER])
    assert scene.view == "compare"
    app.step([DOWN])
    assert app.screen.get_size() == size


def test_limits_text_uses_seconds_and_nodes() -> None:
    set_language("en")
    assert benchmark.limits_text(SolveLimits(time_s=10.0, max_nodes=1_000_000)) == "10 s / 1,000,000 nodes"
    set_language("fr")
    assert benchmark.limits_text(SolveLimits(time_s=0.5, max_nodes=3000)) == "0,5 s / 3 000 nœuds"


def test_machine_lines_have_no_hostname(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    app, scene = bench_app(tmp_path, monkeypatch)
    run_quick(app, scene)
    assert scene.run is not None
    lines = benchmark.machine_lines(scene.run.machine)
    host = socket.gethostname()
    assert lines and (len(host) < 4 or all(host not in line for line in lines))
    assert json.dumps(lines)  # plain strings


def test_level_labels_use_titles_and_name_the_pack_only_when_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, scene = bench_app(tmp_path, monkeypatch)
    first = scene.packs["first-steps"].levels[0]
    assert scene.level_label("first-steps", first.id, multi=False) == first.title
    assert scene.level_label("first-steps", first.id, multi=True) == f"first-steps · {first.title}"
    assert scene.level_label("gone", "x9", multi=False) == "x9"
