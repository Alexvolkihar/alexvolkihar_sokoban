from collections.abc import Callable

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui import app as app_module
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes import load_scene_class
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.main_menu import MainMenuScene
from alexvolkihar_sokoban.ui.scenes.placeholder import PlaceholderScene


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


ESCAPE = key(pygame.K_ESCAPE, 41)
P_KEY = key(pygame.K_p, 19)


def recording_scenes(monkeypatch: pytest.MonkeyPatch, log: list[str]) -> None:
    """Make every scene name load a scene class that logs its calls as '<name>.<call>'."""

    def factory(name: str) -> type[Scene]:
        class Recorder(Scene):
            is_overlay = name.startswith("overlay")

            def on_enter(self, **params: object) -> None:
                log.append(f"{name}.enter{sorted(params)}")

            def on_exit(self) -> None:
                log.append(f"{name}.exit")

            def on_resume(self) -> None:
                log.append(f"{name}.resume")

            def handle_action(self, action: Action) -> None:
                log.append(f"{name}.{action.value}")
                if action is Action.PAUSE:
                    self.app.push("overlay")
                elif action is Action.BACK:
                    self.app.pop()

            def draw(self, surface: pygame.Surface) -> None:
                log.append(f"{name}.draw")

        return Recorder

    monkeypatch.setattr(app_module, "load_scene_class", factory)


def test_unknown_scene_gives_placeholder() -> None:
    assert load_scene_class("no_such_scene") is PlaceholderScene
    assert load_scene_class("main_menu") is MainMenuScene
    assert load_scene_class("game") is GameScene
    for bad in ("", "../app", "scenes.game", "Game Scene"):
        with pytest.raises(ValueError):
            load_scene_class(bad)


def test_app_step_push_pop() -> None:
    app = App(Settings(), headless=True)
    assert app.stack == () and app.top is None
    menu = app.push("main_menu")
    placeholder = app.push("no_such_scene")
    assert isinstance(placeholder, PlaceholderScene) and placeholder.name == "no_such_scene"
    assert app.top is placeholder and app.stack == (menu, placeholder)
    app.step([ESCAPE])
    assert app.top is menu and app.running
    app.pop()
    assert app.stack == () and not app.running


def test_replace_swaps_the_top_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    recording_scenes(monkeypatch, log)
    app = App(Settings(), headless=True)
    app.push("a")
    app.push("b", x=1)
    app.replace("c", y=2)
    assert [s.name for s in app.stack] == ["a", "c"]
    assert log == ["a.enter[]", "b.enter['x']", "b.exit", "c.enter['y']"]


def test_pop_resumes_the_scene_below(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    recording_scenes(monkeypatch, log)
    app = App(Settings(), headless=True)
    app.push("a")
    app.push("b")
    log.clear()
    app.pop()
    assert log == ["b.exit", "a.resume"]


def test_one_key_press_stops_at_the_scene_it_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    recording_scenes(monkeypatch, log)
    app = App(Settings(), headless=True)
    app.push("game")
    log.clear()
    # Escape is [pause, back]: pause opens the overlay, back must not reach (and close) it.
    app.step([ESCAPE])
    assert [s.name for s in app.stack] == ["game", "overlay"]
    assert "overlay.back" not in log and "game.back" not in log


def test_overlay_draws_over_the_scene_below(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    recording_scenes(monkeypatch, log)
    app = App(Settings(), headless=True)
    app.push("menu")
    app.push("game")
    app.step([])
    assert [e for e in log if e.endswith(".draw")] == ["game.draw"]
    log.clear()
    app.step([P_KEY])  # pause → overlay
    assert [e for e in log if e.endswith(".draw")] == ["game.draw", "overlay.draw"]


def test_quit_event_exits_every_scene_top_first(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    recording_scenes(monkeypatch, log)
    app = App(Settings(), headless=True)
    app.push("a")
    app.push("b")
    log.clear()
    app.step([pygame.event.Event(pygame.QUIT), P_KEY])
    assert log == ["b.exit", "a.exit"]
    assert not app.running and app.stack == ()
    app.quit()  # idempotent
    assert log == ["b.exit", "a.exit"]


def test_window_resize_clamped() -> None:
    settings = Settings()
    app = App(settings)
    assert app.screen.get_size() == (1024, 768)
    assert pygame.display.get_caption()[0] == "Alexvolkihar Sokoban"
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=300, h=200, size=(300, 200))])
    assert app.screen.get_size() == (640, 480) and settings.window == (640, 480)
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=800, h=600, size=(800, 600))])
    assert app.screen.get_size() == (800, 600) and settings.window == (800, 600)


def test_headless_app_renders_offscreen() -> None:
    app = App(Settings(window=(700, 500)), headless=True)
    assert app.screen.get_size() == (700, 500)
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=10, h=10, size=(10, 10))])
    assert app.screen.get_size() == (640, 480)
    for font in (app.fonts.small, app.fonts.normal, app.fonts.title):
        assert font.get_height() > 0
    assert app.fonts.small.get_height() < app.fonts.normal.get_height() < app.fonts.title.get_height()


def test_set_theme_updates_settings() -> None:
    settings = Settings(theme="no-such-theme")
    app = App(settings, headless=True)
    app.set_theme("kenney")
    assert settings.theme == app.theme.id


def test_run_starts_on_the_main_menu_and_stops_on_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    app = App(Settings(), headless=True)
    seen: list[str] = []
    steps: list[Callable[[], None]] = [
        lambda: seen.append(app.top.name if app.top else "-"),
        lambda: app.quit(),
    ]

    def fake_get() -> list[pygame.event.Event]:
        steps.pop(0)()
        return []

    monkeypatch.setattr(pygame.event, "get", fake_get)
    app.run()
    assert seen == ["main_menu"] and not app.running
