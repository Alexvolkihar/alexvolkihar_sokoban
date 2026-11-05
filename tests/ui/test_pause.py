from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.pause import PauseScene
from tests.ui.game_helpers import DOWN, ENTER, ESCAPE, PACK, PAUSE, RIGHT, UP, names, start_game


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def open_pause(tmp_path: Path, language: str = "en") -> tuple[App, GameScene, PauseScene]:
    app, game = start_game(tmp_path, language=language)
    app.step([RIGHT, PAUSE], 0)
    pause = app.top
    assert isinstance(pause, PauseScene)
    return app, game, pause


def choose(app: App, pause: PauseScene, index: int) -> None:
    pause.menu.selected = index
    app.step([ENTER], 0)


def test_pause_is_an_overlay_with_five_items(tmp_path: Path) -> None:
    _, game, pause = open_pause(tmp_path)
    assert pause.is_overlay and game.paused
    assert [item.text for item in pause.menu.items] == [
        "Resume",
        "Restart",
        "Watch solution",
        "Level select",
        "Main menu",
    ]


def test_pause_items_in_french(tmp_path: Path) -> None:
    _, _, pause = open_pause(tmp_path, "fr")
    assert [item.text for item in pause.menu.items] == [
        "Reprendre",
        "Recommencer",
        "Voir la solution",
        "Choix du niveau",
        "Menu principal",
    ]


def test_resume_item_and_back_return_to_the_game(tmp_path: Path) -> None:
    app, game, pause = open_pause(tmp_path)
    choose(app, pause, 0)
    assert app.top is game and not game.paused
    app.step([PAUSE], 0)
    app.step([PAUSE], 0)  # the pause key toggles
    assert app.top is game
    app.step([ESCAPE], 0)
    app.step([ESCAPE], 0)
    assert app.top is game and game.state.lurd == "r"


def test_restart_item_restarts_at_once(tmp_path: Path) -> None:
    app, game, pause = open_pause(tmp_path)
    choose(app, pause, 1)
    assert app.top is game and game.state.moves == 0 and game.elapsed_ms == 0


def test_watch_solution_opens_the_replay_and_marks_the_run_assisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, game, pause = open_pause(tmp_path)
    pushed: list[tuple[str, dict[str, object]]] = []
    real_push = app.push

    def spy(name: str, **params: object) -> object:
        pushed.append((name, params))
        return real_push(name, **params)

    monkeypatch.setattr(app, "push", spy)
    choose(app, pause, 2)
    assert names(app) == ["main_menu", "game", "replay"]
    name, params = pushed[0]
    assert name == "replay" and params["pack"] == PACK and params["level_id"] == "one"
    assert params["on_watch"] == game.mark_assisted
    assert game.assisted  # the replay calls on_watch as soon as it opens


def test_level_select_item_opens_level_select_and_keeps_the_session(tmp_path: Path) -> None:
    app, _, pause = open_pause(tmp_path)
    choose(app, pause, 3)
    assert names(app) == ["main_menu", "level_select"]
    assert app.context is not None and app.context.session is not None


def test_level_select_item_returns_to_an_open_level_select(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.pop()  # rebuild the stack as [main_menu, level_select, game]
    app.push("level_select", pack_id=PACK.id)
    app.push("game", pack=PACK, level_id="one")
    app.step([PAUSE], 0)
    pause = app.top
    assert isinstance(pause, PauseScene)
    choose(app, pause, 3)
    assert names(app) == ["main_menu", "level_select"]


def test_main_menu_item(tmp_path: Path) -> None:
    app, _, pause = open_pause(tmp_path)
    choose(app, pause, 4)
    assert names(app) == ["main_menu"] and app.running


def test_main_menu_item_without_a_menu_below(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.pop()
    app.pop()  # empty stack: the app stopped; start again with the game alone
    app.running = True
    app.push("game", pack=PACK, level_id="one")
    app.step([PAUSE], 0)
    pause = app.top
    assert isinstance(pause, PauseScene)
    choose(app, pause, 4)
    assert names(app) == ["main_menu"] and app.running


def test_keyboard_navigation_wraps(tmp_path: Path) -> None:
    app, _, pause = open_pause(tmp_path)
    app.step([UP], 0)
    assert pause.menu.selected == 4
    app.step([DOWN], 0)
    assert pause.menu.selected == 0


def test_mouse_click_selects_an_item(tmp_path: Path) -> None:
    app, game, pause = open_pause(tmp_path)
    app.step([], 0)  # draw once so the items have rects
    rect = pause.menu.item_rects[0]
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)], 0)
    assert app.top is game


@pytest.mark.parametrize("size", [(640, 480), (1920, 1080)])
def test_pause_draws_at_any_size(tmp_path: Path, size: tuple[int, int]) -> None:
    app, _, _ = open_pause(tmp_path, "fr")
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size)])
