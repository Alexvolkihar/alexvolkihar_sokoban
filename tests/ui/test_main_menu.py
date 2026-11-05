from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import Pack
from alexvolkihar_sokoban.persistence.session import SavedSession
from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.scoring.records import LastPlayed
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scene import Scene
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


# -- with an app context (plan Task 10) -------------------------------------------------------------------

ROWS = ["#####", "#@$.#", "#####"]


def context_app(
    tmp_path: Path, *, session: bool = False, last_played: bool = False
) -> tuple[App, AppContext]:
    levels = tmp_path / "levels"
    levels.mkdir(exist_ok=True)
    (levels / "mine.xsb").write_text("\n".join(ROWS) + "\n", encoding="utf-8")
    ctx = AppContext.load(tmp_path, bundled=[])
    level_hash = Level.from_rows(ROWS).canonical_hash()
    if last_played:
        ctx.progress.set_last_played(LastPlayed("custom", "mine/1", level_hash))
    if session:
        ctx.session = SavedSession("custom", "mine/1", level_hash, "", "", 0, False, "2026-11-05T14:03:22Z")
    return App(ctx.settings, context=ctx, headless=True), ctx


def test_continue_disabled_without_session_or_last_played(tmp_path: Path) -> None:
    app, _ = context_app(tmp_path)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene)
    assert not scene.menu.items[0].enabled
    assert labels(scene)[scene.menu.selected] == "Level select"


def test_continue_resumes_the_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, ctx = context_app(tmp_path, session=True)
    pushed: list[tuple[str, dict[str, object]]] = []
    real_push = app.push

    def spy(name: str, **params: object) -> Scene:
        pushed.append((name, params))
        return real_push(name, **params)

    monkeypatch.setattr(app, "push", spy)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene) and scene.menu.items[0].enabled
    assert scene.menu.selected == 0  # Continue is preselected once it is available
    app.step([ENTER])
    assert app.top is not None and app.top.name == "game"
    name, params = pushed[-1]
    assert params["resume"] is ctx.session
    assert (
        isinstance(params["pack"], Pack) and params["pack"].id == "custom" and params["level_id"] == "mine/1"
    )


def test_continue_opens_the_last_played_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = context_app(tmp_path, last_played=True)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene) and scene.menu.items[0].enabled
    app.step([ENTER])
    game = app.top
    assert game is not None and game.name == "game"
    assert game.entry.id == "mine/1"  # type: ignore[attr-defined]


def test_continue_follows_the_context_after_a_game(tmp_path: Path) -> None:
    app, ctx = context_app(tmp_path)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene)
    app.push("placeholder_for_a_game")
    ctx.progress.set_last_played(LastPlayed("custom", "mine/1", Level.from_rows(ROWS).canonical_hash()))
    app.pop()
    assert scene.menu.items[0].enabled


def test_warnings_shown_and_dismissed(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("{broken", encoding="utf-8")
    app, ctx = context_app(tmp_path)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene)
    assert len(scene.messages) == 1 and ctx.warnings == []
    app.step([])  # draws the message box
    app.step([DOWN])  # ignored while the message is shown
    assert labels(scene)[scene.menu.selected] == "Level select"
    app.step([ENTER])  # dismisses, does not open Level select
    assert scene.messages == [] and app.top is scene
    app.step([ENTER])
    assert app.top is not None and app.top.name == "level_select"


def test_escape_dismisses_warnings_and_click_too(tmp_path: Path) -> None:
    (tmp_path / "progress.json").write_text("{broken", encoding="utf-8")
    app, ctx = context_app(tmp_path)
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene)
    app.step([ESCAPE])
    assert scene.messages == [] and app.running
    ctx.warnings.append("later warning")
    app.push("credits")
    app.pop()  # warnings raised while away appear when the menu is back on top
    assert scene.messages == ["later warning"]
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))
    app.step([click])
    assert scene.messages == []


@pytest.mark.parametrize("size", [(640, 480), (1920, 1080)])
def test_many_long_warnings_fit_the_window(tmp_path: Path, size: tuple[int, int]) -> None:
    app, ctx = context_app(tmp_path)
    app.settings.window = size
    app.apply_display_settings()
    ctx.warnings.extend(f"warning {i} " + "x" * 300 for i in range(30))
    scene = app.push("main_menu")
    assert isinstance(scene, MainMenuScene) and len(scene.messages) == 30
    app.step([])
    assert scene.message_rect is not None and app.screen.get_rect().contains(scene.message_rect)
