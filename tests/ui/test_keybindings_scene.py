import json
from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import ACTIONS, DEFAULT_KEYBINDINGS, Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scenes.keybindings import KeybindingsScene


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0, mod: int = pygame.KMOD_NONE) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=mod, unicode="")


DOWN = key(pygame.K_DOWN, 81)
UP = key(pygame.K_UP, 82)
ENTER = key(pygame.K_RETURN, 40)
ESCAPE = key(pygame.K_ESCAPE, 41)
DELETE = key(pygame.K_DELETE, 76)
J_KEY = key(pygame.K_j, 13)


def keys_app(tmp_path: Path, **settings: object) -> tuple[App, AppContext, KeybindingsScene]:
    ctx = AppContext.load(tmp_path, bundled=[])
    for name, value in settings.items():
        setattr(ctx.settings, name, value)
    set_language(ctx.settings.language)
    app = App(ctx.settings, context=ctx, headless=True)
    scene = app.push("keybindings")
    assert isinstance(scene, KeybindingsScene)
    return app, ctx, scene


def saved_bindings(tmp_path: Path) -> dict[str, list[str]]:
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    bindings = data["keybindings"]
    assert isinstance(bindings, dict)
    return bindings


def select(app: App, scene: KeybindingsScene, row: str) -> None:
    while scene.rows[scene.scroll.selected] != row:
        app.step([DOWN])


def test_one_row_per_action_then_reset_and_back(tmp_path: Path) -> None:
    _, _, scene = keys_app(tmp_path, language="en")
    assert scene.rows == [*ACTIONS, "reset_all", "close"]
    assert scene.row_text("up") == ("Up", "Up, W")
    assert scene.row_text("undo") == ("Undo", "U, Backspace, Ctrl+Z")
    assert scene.row_text("reset_all")[0] == "Reset all"
    set_language("fr")
    assert scene.row_text("left") == ("Gauche", "Gauche, A")
    assert scene.row_text("close")[0] == "Retour"
    assert scene.row_text("back")[0] == "Retour (menus)"  # the action


def test_rebind_action_captures_next_key(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "undo")
    app.step([ENTER])
    assert scene.capturing == "undo"  # the Enter that started the capture is not captured
    assert ctx.settings.keybindings["undo"] == DEFAULT_KEYBINDINGS["undo"]
    app.step([J_KEY])
    assert scene.capturing is None and ctx.settings.keybindings["undo"] == ("key:j",)
    assert app.input.actions_for(J_KEY) == [Action.UNDO]
    assert app.input.actions_for(key(pygame.K_u, 24)) == []
    assert saved_bindings(tmp_path)["undo"] == ["key:j"]


def test_capture_takes_navigation_keys_and_ctrl(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "hint")
    app.step([ENTER, DOWN])  # while capturing, Down is the new key, not navigation
    assert ctx.settings.keybindings["hint"] == ("key:down",) and scene.rows[scene.scroll.selected] == "hint"
    app.step([ENTER, key(pygame.K_LCTRL, 224, pygame.KMOD_LCTRL)])  # a lone modifier keeps waiting
    assert scene.capturing == "hint"
    app.step([key(pygame.K_h, 11, pygame.KMOD_LCTRL)])
    assert ctx.settings.keybindings["hint"] == ("ctrl+key:h",)


def test_escape_cancels_capture(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "restart")
    app.step([ENTER, ESCAPE])
    assert scene.capturing is None and app.top is scene
    assert ctx.settings.keybindings["restart"] == ("key:r",)
    app.step([ESCAPE])
    assert app.top is None


def test_rebind_conflict_swaps(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path, language="en")
    select(app, scene, "left")
    app.step([ENTER, UP])  # the Up arrow already moves up
    bindings = ctx.settings.keybindings
    assert bindings["left"] == ("key:up",)
    assert bindings["up"] == ("key:left", "scan:4", "scan:26")
    assert "Up" in scene.message and "swapped" in scene.message
    assert app.input.actions_for(UP) == [Action.LEFT]
    assert saved_bindings(tmp_path)["up"] == ["key:left", "scan:4", "scan:26"]


def test_rebind_conflict_found_by_physical_key(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "down")
    app.step([ENTER, key(pygame.K_w, 26)])  # W is "up" by scancode 26, captured as key:w
    bindings = ctx.settings.keybindings
    assert bindings["down"] == ("key:w",)
    assert bindings["up"] == ("key:up", "key:down", "scan:22")
    assert app.input.actions_for(key(pygame.K_w, 26)) == [Action.DOWN]


def test_conflict_outside_movement_only_warns(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path, language="en")
    select(app, scene, "hint")
    app.step([ENTER, key(pygame.K_r, 21)])
    assert ctx.settings.keybindings["hint"] == ("key:r",)
    assert ctx.settings.keybindings["restart"] == ("key:r",)
    assert "Restart" in scene.message


def test_delete_restores_that_action_defaults(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "redo")
    app.step([ENTER, J_KEY])
    assert ctx.settings.keybindings["redo"] == ("key:j",)
    app.step([DELETE])
    assert ctx.settings.keybindings["redo"] == DEFAULT_KEYBINDINGS["redo"]
    assert saved_bindings(tmp_path)["redo"] == list(DEFAULT_KEYBINDINGS["redo"])


def test_reset_all_restores_defaults(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "left")
    app.step([ENTER, UP])
    select(app, scene, "reset_all")
    app.step([ENTER])
    assert ctx.settings.keybindings == dict(DEFAULT_KEYBINDINGS)
    assert app.input.actions_for(UP) == [Action.UP]
    assert saved_bindings(tmp_path) == {a: list(b) for a, b in DEFAULT_KEYBINDINGS.items()}


def test_back_row_returns(tmp_path: Path) -> None:
    app, _, scene = keys_app(tmp_path)
    select(app, scene, "close")
    app.step([ENTER])
    assert app.top is None


def test_click_starts_capture(tmp_path: Path) -> None:
    app, _, scene = keys_app(tmp_path)
    app.step([])
    index, rect = scene.scroll.item_rects[1]
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)])
    assert scene.capturing == scene.rows[index]


def test_without_context_rebinds_in_memory() -> None:
    app = App(Settings(), headless=True)
    scene = app.push("keybindings")
    assert isinstance(scene, KeybindingsScene)
    app.step([ENTER, J_KEY])
    assert app.settings.keybindings["up"] == ("key:j",)


@pytest.mark.parametrize("size", [(640, 480), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_draws_and_fits_while_capturing(tmp_path: Path, size: tuple[int, int], language: str) -> None:
    app, _, scene = keys_app(tmp_path, window=size, language=language)
    select(app, scene, "close")
    app.step([])
    select(app, scene, "confirm")
    app.step([ENTER])
    app.step([])
    screen = app.screen.get_rect()
    rows = dict(scene.scroll.item_rects)
    assert scene.rows.index("confirm") in rows
    assert all(scene.list_rect.contains(r) and screen.contains(r) for r in rows.values())


def test_held_enter_repeat_is_not_captured_but_a_new_press_is(tmp_path: Path) -> None:
    app, ctx, scene = keys_app(tmp_path)
    select(app, scene, "hint")
    app.step([ENTER, ENTER])  # the second one is the key repeat of the first
    assert scene.capturing == "hint"
    app.step([pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN, scancode=40, mod=0, unicode=""), ENTER])
    assert scene.capturing is None and ctx.settings.keybindings["hint"] == ("key:return",)
    assert "Confirm" in scene.message
