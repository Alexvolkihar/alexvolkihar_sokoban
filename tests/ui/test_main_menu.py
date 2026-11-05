from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.main_menu import MainMenuScene


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


DOWN = key(pygame.K_DOWN, 81)
UP = key(pygame.K_UP, 82)
ENTER = key(pygame.K_RETURN, 40)
ESCAPE = key(pygame.K_ESCAPE, 41)


def menu_app(**settings: object) -> tuple[App, MainMenuScene]:
    app = App(Settings(**settings), headless=True)  # type: ignore[arg-type]
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene)
    return app, scene


def labels(scene: MainMenuScene) -> list[str]:
    return [item.text for item in scene.menu.items]


def test_main_menu_items() -> None:
    _, scene = menu_app(language="en")
    assert labels(scene) == [
        "Continue",
        "Level select",
        "Random level",
        "Benchmark",
        "Themes",
        "Settings",
        "Credits",
        "Quit",
    ]
    assert not scene.menu.items[0].enabled  # wired by the app context (plan Task 10)
    set_language("fr")
    assert labels(scene)[0] == "Continuer" and labels(scene)[-1] == "Quitter"


def test_main_menu_navigation_pushes_level_select() -> None:
    app, scene = menu_app()
    assert labels(scene)[scene.menu.selected] == "Level select"
    app.step([ENTER])
    assert app.top is not None and app.top.name == "level_select"
    app.step([ESCAPE])
    assert app.top is scene
    app.step([DOWN, ENTER])
    assert app.top is not None and app.top.name == "generate"


@pytest.mark.parametrize(
    ("downs", "name"), [(2, "benchmark"), (3, "themes"), (4, "settings"), (5, "credits")]
)
def test_main_menu_pushes_each_scene(downs: int, name: str) -> None:
    app, _ = menu_app()
    app.step([DOWN] * downs + [ENTER])
    assert app.top is not None and app.top.name == name


def test_main_menu_quit() -> None:
    app, scene = menu_app()
    app.step([UP])  # wraps past the disabled Continue to Quit
    assert labels(scene)[scene.menu.selected] == "Quit"
    app.step([ENTER])
    assert not app.running


def test_main_menu_escape_does_not_close_the_game() -> None:
    app, scene = menu_app()
    app.step([ESCAPE])
    assert app.top is scene and app.running


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_main_menu_draws_and_fits(size: tuple[int, int], language: str) -> None:
    app, scene = menu_app(window=size, language=language)
    app.step([])
    screen = app.screen.get_rect()
    assert scene.menu.item_rects and all(screen.contains(r) for r in scene.menu.item_rects)
    assert app.screen.get_at((size[0] // 2, 5))[:3] == app.theme.background
