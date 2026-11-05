import threading
import time
from collections.abc import Callable
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui import solver_worker
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.pause import PauseScene
from alexvolkihar_sokoban.ui.scenes.replay import REPLAY_LIMITS, SPEEDS, ReplayScene
from tests.ui.game_helpers import (
    CORRIDOR,
    DOWN,
    ENTER,
    ESCAPE,
    LEFT,
    ONE_BOX,
    PACK,
    PAUSE,
    RIGHT,
    UP,
    names,
    start_game,
)

# Solved in 3 pushes: "RRR" (the par below takes a detour first).
LONG = Level.from_rows(["#######", "#@$  .#", "#     #", "#######"])
BAD_PAR = Par(pushes=1, moves=2, lurd="lL", solver="push-astar/1")
OTHER = Pack(
    id="other",
    title="Other pack",
    levels=(
        LevelEntry("bad-par", ONE_BOX, par=BAD_PAR),
        LevelEntry("long", LONG, par=Par(pushes=3, moves=3, lurd="RRR", solver="push-astar/1")),
    ),
)


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def open_replay(
    tmp_path: Path, pack: Pack = PACK, level_id: str = "one", language: str = "en"
) -> tuple[App, GameScene, ReplayScene, list[int]]:
    app, game = start_game(tmp_path, language=language)
    watched: list[int] = []
    scene = app.push("replay", pack=pack, level_id=level_id, on_watch=lambda: watched.append(1))
    assert isinstance(scene, ReplayScene)
    return app, game, scene, watched


def step_until(app: App, done: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not done():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        app.step([], 0)
        time.sleep(0.002)


def test_replay_plays_par_to_solved(tmp_path: Path) -> None:
    app, _, scene, watched = open_replay(tmp_path)
    assert watched == [1]  # entering marks the run assisted
    assert scene.playing and scene.position == 0 and scene.total == 2
    for _ in range(10):
        app.step([], 1_000)
    assert scene.state.is_solved and scene.position == 2 and not scene.playing


def test_replay_plays_at_the_chosen_speed(tmp_path: Path) -> None:
    app, _, scene, _ = open_replay(tmp_path, OTHER, "long")
    assert scene.speed == 4 and SPEEDS == (1, 2, 4, 8)
    app.step([], 249)
    assert scene.position == 0
    app.step([], 1)
    assert scene.position == 1
    app.step([], 500)
    assert scene.position == 3 and scene.state.is_solved


def test_replay_speed_and_step_controls(tmp_path: Path) -> None:
    app, _, scene, _ = open_replay(tmp_path, OTHER, "long")
    app.step([UP], 0)
    assert scene.speed == 8
    app.step([UP], 0)
    assert scene.speed == 8  # fastest
    app.step([DOWN, DOWN, DOWN, DOWN], 0)
    assert scene.speed == 1  # slowest
    app.step([ENTER], 0)
    assert not scene.playing
    app.step([], 5_000)
    assert scene.position == 0  # paused: time does not advance it
    app.step([RIGHT, RIGHT], 0)
    assert scene.position == 2 and not scene.playing
    assert scene.state.player == (1, 3) and scene.state.boxes == frozenset({(1, 4)})
    app.step([LEFT], 0)
    assert scene.position == 1 and scene.state.boxes == frozenset({(1, 3)})
    app.step([LEFT, LEFT, LEFT], 0)
    assert scene.position == 0
    app.step([RIGHT, RIGHT, RIGHT, RIGHT], 0)
    assert scene.position == 3 and scene.state.is_solved
    app.step([ENTER], 0)  # at the end, play starts over
    assert scene.playing and scene.position == 0


def test_right_while_playing_pauses(tmp_path: Path) -> None:
    app, _, scene, _ = open_replay(tmp_path, OTHER, "long")
    app.step([RIGHT], 0)
    assert not scene.playing and scene.position == 1


def test_back_returns_to_the_game(tmp_path: Path) -> None:
    app, game, _, _ = open_replay(tmp_path)
    app.step([ESCAPE], 0)
    assert app.top is game and names(app) == ["main_menu", "game"]
    assert game.state.moves == 0


def test_watch_from_pause_marks_the_run_and_comes_back(tmp_path: Path) -> None:
    app, game = start_game(tmp_path)
    app.step([RIGHT, PAUSE], 0)
    pause = app.top
    assert isinstance(pause, PauseScene)
    pause.menu.selected = 2
    app.step([ENTER], 0)
    assert isinstance(app.top, ReplayScene) and game.assisted
    app.step([ESCAPE], 0)
    assert app.top is game and not game.paused and game.state.lurd == "r"


def fake_solve(
    answer: SolveResult, calls: list[dict[str, object]], release: threading.Event | None = None
) -> Callable[..., SolveResult]:
    def fake(level: Level, **kw: object) -> SolveResult:
        calls.append(kw)
        while release is not None and not release.is_set():
            should_stop = kw["should_stop"]
            assert callable(should_stop)
            if should_stop():
                return SolveResult(SolveStatus.CANCELLED, None, None, None, 0, 0, 0)
            time.sleep(0.002)
        return answer

    return fake


def test_replay_solves_a_level_without_par(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[dict[str, object]] = []
    answer = SolveResult(SolveStatus.SOLVED, "R", 1, 1, 1, 1, 1)
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answer, calls, release))
    app, _, scene, watched = open_replay(tmp_path, PACK, "two")
    assert watched == [1] and scene.solving
    assert scene.message is not None and scene.message.startswith("Solving…")
    app.step([], 1_000)
    assert scene.position == 0  # nothing to play yet, the UI keeps running
    release.set()
    step_until(app, lambda: not scene.solving)
    assert calls[0]["limits"] == REPLAY_LIMITS == SolveLimits(time_s=30.0, max_nodes=3_000_000)
    assert calls[0]["boxes"] == CORRIDOR.boxes and calls[0]["player"] == CORRIDOR.player
    assert scene.total == 1 and scene.message is None
    app.step([], 1_000)
    assert scene.state.is_solved


def test_replay_with_a_broken_par_solves_instead(tmp_path: Path) -> None:
    app, _, scene, _ = open_replay(tmp_path, OTHER, "bad-par")
    step_until(app, lambda: not scene.solving)
    assert scene.total == 2  # the real solver's "rU"
    for _ in range(4):
        app.step([], 1_000)
    assert scene.state.is_solved


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (SolveStatus.UNSOLVABLE, "This level has no solution"),
        (SolveStatus.LIMIT_TIME, "No solution found within the solver's limits"),
        (SolveStatus.LIMIT_NODES, "No solution found within the solver's limits"),
        (SolveStatus.INVALID, "This level cannot be solved here"),
    ],
)
def test_replay_without_solution_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: SolveStatus, text: str
) -> None:
    answer = SolveResult(status, None, None, None, 5, 5, 5)
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answer, []))
    app, game, scene, _ = open_replay(tmp_path, PACK, "two")
    step_until(app, lambda: not scene.solving)
    assert scene.message == text and scene.total == 0
    app.step([ENTER, RIGHT, LEFT, UP], 1_000)  # nothing to play: no crash
    app.step([ESCAPE], 0)
    assert app.top is game


def test_back_while_solving_cancels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    answer = SolveResult(SolveStatus.SOLVED, "R", 1, 1, 1, 1, 1)
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answer, [], release))
    app, game, scene, _ = open_replay(tmp_path, PACK, "two")
    app.step([ESCAPE], 0)
    assert app.top is game and not scene.worker.busy
    assert scene.worker.join(2.0)


def test_replay_in_french(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answer = SolveResult(SolveStatus.UNSOLVABLE, None, None, None, 5, 5, 5)
    monkeypatch.setattr(solver_worker, "solve", fake_solve(answer, []))
    app, _, scene, _ = open_replay(tmp_path, PACK, "two", language="fr")
    step_until(app, lambda: not scene.solving)
    assert scene.message == "Ce niveau n'a pas de solution"


def test_replay_needs_a_pack_and_a_level(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    with pytest.raises(TypeError):
        app.push("replay", pack="nope", level_id="one")


@pytest.mark.parametrize("size", [(640, 480), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_replay_draws_at_any_size(tmp_path: Path, size: tuple[int, int], language: str) -> None:
    app, _, scene, _ = open_replay(tmp_path, language=language)
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size)], 300)
    app.step([ENTER], 0)
    assert app.screen.get_size() == size and not scene.playing
