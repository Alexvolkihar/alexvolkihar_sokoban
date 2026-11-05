import json
from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.scoring.records import LastPlayed, LevelRecord
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.settings import SettingsScene

HASH = "sha256:" + "a" * 64


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

LANGUAGE, ANIMATION, TIMER, FULLSCREEN, KEYS, RESET, BACK = range(7)


def settings_app(tmp_path: Path, **settings: object) -> tuple[App, AppContext, SettingsScene]:
    ctx = AppContext.load(tmp_path, bundled=[])
    for name, value in settings.items():
        setattr(ctx.settings, name, value)
    set_language(ctx.settings.language)
    app = App(ctx.settings, context=ctx, headless=True)
    scene = app.push("settings")
    assert isinstance(scene, SettingsScene)
    return app, ctx, scene


def saved(tmp_path: Path, name: str) -> dict[str, object]:
    data = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def labels(scene: SettingsScene) -> list[str]:
    return [item.text for item in scene.menu.items]


def select(app: App, scene: SettingsScene, index: int) -> None:
    while scene.menu.selected != index:
        app.step([DOWN])


def test_settings_items(tmp_path: Path) -> None:
    _, _, scene = settings_app(tmp_path, language="en")
    assert labels(scene) == [
        "Language: English",
        "Animation: Normal",
        "Show timer: On",
        "Fullscreen: Off",
        "Key bindings…",
        "Reset progress",
        "Back",
    ]
    assert scene.menu.selected == LANGUAGE


def test_language_switch_saves_and_translates(tmp_path: Path) -> None:
    app, ctx, scene = settings_app(tmp_path, language="en")
    app.step([ENTER])
    assert ctx.settings.language == "fr" and get_language() == "fr"
    assert labels(scene)[LANGUAGE] == "Langue : Français"
    assert labels(scene)[BACK] == "Retour"
    assert saved(tmp_path, "settings")["language"] == "fr"
    app.step([LEFT])  # left/right change the value too
    assert ctx.settings.language == "en" and labels(scene)[LANGUAGE] == "Language: English"
    assert saved(tmp_path, "settings")["language"] == "en"


def test_animation_cycles_both_ways(tmp_path: Path) -> None:
    app, ctx, scene = settings_app(tmp_path)
    select(app, scene, ANIMATION)
    app.step([RIGHT])
    assert ctx.settings.animation == "fast"
    app.step([RIGHT])
    assert ctx.settings.animation == "off" and labels(scene)[ANIMATION] == "Animation: Off"
    app.step([LEFT, LEFT])
    assert ctx.settings.animation == "normal"
    app.step([ENTER])
    assert ctx.settings.animation == "fast"
    assert saved(tmp_path, "settings")["animation"] == "fast"


def test_timer_and_fullscreen_toggle_and_save(tmp_path: Path) -> None:
    app, ctx, scene = settings_app(tmp_path)
    select(app, scene, TIMER)
    app.step([ENTER])
    assert ctx.settings.show_timer is False and labels(scene)[TIMER] == "Show timer: Off"
    app.step([DOWN, ENTER])
    assert ctx.settings.fullscreen is True and labels(scene)[FULLSCREEN] == "Fullscreen: On"
    app.step([])  # the screen was re-created and still draws
    data = saved(tmp_path, "settings")
    assert data["show_timer"] is False and data["fullscreen"] is True


def test_key_bindings_item_opens_the_rebinding_scene(tmp_path: Path) -> None:
    app, _, scene = settings_app(tmp_path)
    select(app, scene, KEYS)
    app.step([ENTER])
    assert app.top is not None and app.top.name == "keybindings"
    app.step([ESCAPE])
    assert app.top is scene


def test_reset_progress_requires_confirmation(tmp_path: Path) -> None:
    app, ctx, scene = settings_app(tmp_path)
    ctx.progress.levels[HASH] = LevelRecord("p", "1", completed=True, stars=3)
    ctx.progress.set_last_played(LastPlayed("p", "1", HASH))
    select(app, scene, RESET)
    app.step([ENTER])
    assert ctx.progress.get(HASH) is not None and scene.reset_armed
    assert "again" in labels(scene)[RESET] and "Return" in labels(scene)[RESET]
    app.step([UP, DOWN])  # moving away disarms
    assert not scene.reset_armed and labels(scene)[RESET] == "Reset progress"
    app.step([ENTER, ENTER])
    assert ctx.progress.get(HASH) is None and ctx.progress.last_played is None
    assert not scene.reset_armed and scene.status == "Progress reset."
    assert saved(tmp_path, "progress")["levels"] == {}


def test_reset_progress_disarms_on_back_without_leaving(tmp_path: Path) -> None:
    app, ctx, scene = settings_app(tmp_path)
    ctx.progress.levels[HASH] = LevelRecord("p", "1", completed=True)
    select(app, scene, RESET)
    app.step([ENTER, ESCAPE])
    assert app.top is scene and not scene.reset_armed
    app.step([ENTER])
    assert ctx.progress.get(HASH) is not None


def test_back_returns_to_the_menu(tmp_path: Path) -> None:
    ctx = AppContext.load(tmp_path, bundled=[])
    app = App(ctx.settings, context=ctx, headless=True)
    menu = app.push("main_menu")
    scene = app.push("settings")
    assert isinstance(scene, SettingsScene)
    select(app, scene, BACK)
    app.step([ENTER])
    assert app.top is menu
    app.push("settings")
    app.step([ESCAPE])
    assert app.top is menu


def test_without_context_changes_apply_and_nothing_is_saved() -> None:
    app = App(Settings(language="en"), headless=True)
    scene = app.push("settings")
    assert isinstance(scene, SettingsScene)
    app.step([ENTER])
    assert app.settings.language == "fr"
    assert not scene.menu.items[RESET].enabled


@pytest.mark.parametrize("size", [(640, 480), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_settings_draws_and_fits(tmp_path: Path, size: tuple[int, int], language: str) -> None:
    app, _, scene = settings_app(tmp_path, window=size, language=language)
    app.step([])
    screen = app.screen.get_rect()
    assert scene.menu.item_rects and all(screen.contains(r) for r in scene.menu.item_rects)
    select(app, scene, RESET)
    app.step([ENTER])  # the armed label and the status line also fit
    assert all(screen.contains(r) for r in scene.menu.item_rects)
