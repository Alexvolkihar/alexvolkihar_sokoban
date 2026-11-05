import threading
import time
from collections.abc import Callable
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.persistence.settings import DEFAULT_KEYBINDINGS
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui import solver_worker
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.hud import key_hints
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.game import HINT_LIMITS
from alexvolkihar_sokoban.ui.scenes.victory import VictoryScene
from tests.ui.game_helpers import DOWN, LEFT, RIGHT, UP, key, start_game

HINT = key(pygame.K_h, 11)


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def step_until(app: App, done: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not done():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        app.step([], 16)
        time.sleep(0.002)


def result(status: SolveStatus, lurd: str | None = None) -> SolveResult:
    pushes = None if lurd is None else sum(c.isupper() for c in lurd)
    moves = None if lurd is None else len(lurd)
    return SolveResult(status, lurd, pushes, moves, 10, 20, 30)


def fake_solve(
    answers: dict[str, SolveResult], calls: list[dict[str, object]], release: threading.Event | None = None
) -> Callable[..., SolveResult]:
    """Answers by mode; waits for ``release`` first when given (the UI keeps running meanwhile)."""

    def fake(level: Level, **kw: object) -> SolveResult:
        calls.append(kw)
        while release is not None and not release.is_set():
            time.sleep(0.002)
        mode = kw["mode"]
        assert isinstance(mode, str)
        return answers[mode]

    return fake


def test_hint_key_is_listed_in_the_hud() -> None:
    assert "H hint" in key_hints(DEFAULT_KEYBINDINGS)
    set_language("fr")
    assert "H indice" in key_hints(DEFAULT_KEYBINDINGS)


def test_hint_highlights_next_push(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = start_game(tmp_path)
    drawn: list[dict[str, object]] = []
    real_draw = scene.renderer.draw

    def spy(*args: object, **kw: object) -> object:
        drawn.append(kw)
        return real_draw(*args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(scene.renderer, "draw", spy)
    app.step([HINT])
    step_until(app, lambda: scene.hint is not None)
    hint = scene.hint
    assert hint is not None
    # ONE_BOX is solved by "rU": walk right to (4, 2), then push the box at (3, 2) up to (2, 2).
    assert hint.arrow == ((2, 2), Direction.UP)
    assert hint.highlight == ((4, 2), (3, 2))
    app.step([])
    assert drawn[-1]["arrow"] == hint.arrow and tuple(drawn[-1]["highlight"]) == hint.highlight  # type: ignore[arg-type]
    app.step([RIGHT])  # the next move clears it
    assert scene.hint is None
    app.step([])
    assert drawn[-1].get("arrow") is None


def test_hint_uses_the_hint_limits_from_the_current_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    answers = {"optimal": result(SolveStatus.SOLVED, "U")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, calls))
    app, scene = start_game(tmp_path)
    app.step([RIGHT, HINT])
    step_until(app, lambda: scene.hint is not None)
    assert SolveLimits(time_s=3.0, max_nodes=500_000) == HINT_LIMITS
    assert calls[0]["limits"] == HINT_LIMITS and calls[0]["mode"] == "optimal"
    assert calls[0]["player"] == (4, 2) and calls[0]["boxes"] == frozenset({(3, 2)})
    assert scene.hint is not None and scene.hint.highlight == ((3, 2),)


def test_stale_hint_is_discarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[dict[str, object]] = []
    answers = {"optimal": result(SolveStatus.SOLVED, "rU")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, calls, release))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    assert scene.hint_pending
    app.step([UP])  # the player moves before the answer arrives
    release.set()
    for _ in range(20):
        app.step([], 16)
        time.sleep(0.002)
    assert scene.hint is None and not scene.hint_pending


def test_hint_result_for_another_position_is_never_shown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    answers = {"optimal": result(SolveStatus.SOLVED, "rU")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, [], release))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    scene.state.move(Direction.UP)  # the state changes without going through the scene
    release.set()
    step_until(app, lambda: not scene.worker.busy)
    app.step([])
    assert scene.hint is None and not scene.hint_pending


def test_hint_on_dead_end_shows_message(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([UP, UP, RIGHT, DOWN])  # pushes the box down against the bottom wall
    assert scene.state.lurd == "uurD"
    app.step([HINT])
    step_until(app, lambda: not scene.hint_pending)
    assert scene.hint is None
    assert scene.message == "Dead end — undo some moves"


def test_hint_on_dead_end_in_french(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, language="fr")
    app.step([UP, UP, RIGHT, DOWN, HINT])
    step_until(app, lambda: not scene.hint_pending)
    assert scene.message == "Impasse — annulez quelques coups"


def test_hint_falls_back_to_fast_once_on_a_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    answers = {"optimal": result(SolveStatus.LIMIT_TIME), "fast": result(SolveStatus.SOLVED, "rU")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, calls))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    step_until(app, lambda: scene.hint is not None)
    assert [c["mode"] for c in calls] == ["optimal", "fast"]


def test_hint_reports_when_no_answer_is_found_in_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    answers = {"optimal": result(SolveStatus.LIMIT_NODES), "fast": result(SolveStatus.LIMIT_TIME)}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, calls))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    step_until(app, lambda: not scene.hint_pending)
    assert [c["mode"] for c in calls] == ["optimal", "fast"]
    assert scene.hint is None and scene.message == "No hint found in time"


def test_hint_shows_progress_while_solving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    answers = {"optimal": result(SolveStatus.SOLVED, "rU")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, [], release))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    assert scene.message is not None and scene.message.startswith("Looking for a hint")
    app.step([HINT])  # asking again while it thinks starts nothing new
    release.set()
    step_until(app, lambda: scene.hint is not None)
    assert scene.message is None


def test_hint_marks_run_assisted(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    assert not scene.assisted
    app.step([HINT])
    assert scene.assisted
    step_until(app, lambda: scene.hint is not None)
    app.step([RIGHT, UP])
    victory = app.top
    assert isinstance(victory, VictoryScene)
    assert victory.run.assisted and victory.record_update.stars_earned == 0


def test_leaving_the_game_cancels_the_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[dict[str, object]] = []
    answers = {"optimal": result(SolveStatus.SOLVED, "rU")}
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answers, calls, release))
    app, scene = start_game(tmp_path)
    app.step([HINT])
    assert scene.worker.busy
    app.pop()
    assert not scene.worker.busy
    release.set()


def test_hint_after_undo_and_redo_is_cleared(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([LEFT, RIGHT, HINT])  # LEFT is blocked by the wall
    step_until(app, lambda: scene.hint is not None)
    app.step([key(pygame.K_u, 24)])
    assert scene.hint is None
