from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext, load_bundled_packs
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scenes.credits import CreditsScene, credit_sections

BOXOBAN_CITATION = "An investigation of Model-free planning: boxoban levels"


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


DOWN = key(pygame.K_DOWN, 81)
UP = key(pygame.K_UP, 82)
ESCAPE = key(pygame.K_ESCAPE, 41)


def credits_app(tmp_path: Path, *, bundled: list[Pack] | None = None) -> tuple[App, CreditsScene]:
    ctx = AppContext.load(tmp_path, bundled=bundled)
    ctx.settings.window = (640, 480)
    app = App(ctx.settings, context=ctx, headless=True)
    app.apply_display_settings()
    app.push("main_menu")
    scene = app.push("credits")
    assert isinstance(scene, CreditsScene)
    return app, scene


def _text(scene: CreditsScene) -> str:
    return " ".join(scene.text_lines())


def test_credits_name_the_author_the_original_project_and_pack_authors(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([])
    text = _text(scene)
    assert "Alexis MABANZA" in text and "MIT" in text
    assert "Remake of Sokoban-LAMA, my first-year university project (2022)." in text
    assert "https://github.com/Alexvolkihar/Sokoban-LAMA" in text
    assert "Levels: First steps" in text
    assert "Arthur Guez" in text and "Victor Valdes" in text and "DeepMind" in text
    assert BOXOBAN_CITATION in text and "Apache" in text


def test_credits_cover_assets_libraries_and_palettes(tmp_path: Path) -> None:
    _, scene = credits_app(tmp_path)
    text = _text(scene)
    assert "Kenney" in text and "CC0" in text
    assert "pygame-ce" in text and "LGPL" in text
    assert "platformdirs" in text
    assert "Dobble 3D" in text


def test_microban_is_not_credited(tmp_path: Path) -> None:
    _, scene = credits_app(tmp_path)
    text = _text(scene)
    assert "Microban" not in text and "Skinner" not in text


def test_new_bundled_packs_appear_automatically(tmp_path: Path) -> None:
    level = Level.from_rows(["#####", "#@$.#", "#####"])
    extra = Pack("extra", "Extra pack", (LevelEntry("1", level),), author="Jane Doe", license="CC-BY 4.0")
    _, scene = credits_app(tmp_path, bundled=[extra])
    text = _text(scene)
    assert "Extra pack" in text and "Jane Doe" in text and "CC-BY 4.0" in text


def test_player_packs_are_not_credited(tmp_path: Path) -> None:
    _, scene = credits_app(tmp_path, bundled=[])
    titles = [section.title for section in scene.sections]
    text = _text(scene)
    assert "Generated" not in text and "Custom" not in text
    assert len(titles) == len(set(titles))


def test_credits_without_a_context_read_the_bundled_packs() -> None:
    app = App(Settings(), headless=True)
    scene = app.push("credits")
    assert isinstance(scene, CreditsScene)
    assert "Arthur Guez" in _text(scene)


def test_credit_sections_follow_the_language() -> None:
    packs, _ = load_bundled_packs()
    set_language("en")
    english = [s.title for s in credit_sections(packs)]
    set_language("fr")
    french = [s.title for s in credit_sections(packs)]
    assert english != french
    assert "This game" in english and "Ce jeu" in french


def test_scrolls_with_up_and_down_within_bounds(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([])
    assert scene.scroll == 0 and scene.max_scroll > 0  # 640×480: the credits do not fit
    app.step([UP])
    assert scene.scroll == 0
    app.step([DOWN])
    assert scene.scroll > 0
    for _ in range(500):
        app.step([DOWN])
    assert scene.scroll == scene.max_scroll
    for _ in range(500):
        app.step([UP])
    assert scene.scroll == 0


def test_mouse_wheel_scrolls(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([])
    app.step([pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1)])
    assert scene.scroll > 0
    app.step([pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1)])
    assert scene.scroll == 0


def test_page_and_home_end_keys(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([])
    app.step([key(pygame.K_END)])
    assert scene.scroll == scene.max_scroll
    app.step([key(pygame.K_HOME)])
    assert scene.scroll == 0
    app.step([key(pygame.K_PAGEDOWN)])
    assert scene.scroll > 0


def test_back_returns_to_the_menu(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([ESCAPE])
    assert app.top is not None and app.top.name == "main_menu"


def test_back_action_pops(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    scene.handle_action(Action.BACK)
    assert app.top is not None and app.top.name == "main_menu"


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_draws_at_any_size_with_lines_inside_the_window(
    tmp_path: Path, size: tuple[int, int], language: str
) -> None:
    set_language(language)  # type: ignore[arg-type]
    app, scene = credits_app(tmp_path)
    app.screen = pygame.Surface(size)
    app.step([])
    for _ in range(3):
        app.step([DOWN])
    assert scene.body_rect.width < size[0]
    assert scene.wrapped
    for role, line in scene.wrapped:
        assert getattr(app.fonts, role).size(line)[0] <= scene.body_rect.width


def test_scroll_survives_a_resize(tmp_path: Path) -> None:
    app, scene = credits_app(tmp_path)
    app.step([])
    app.step([key(pygame.K_END)])
    app.screen = pygame.Surface((1920, 1080))
    app.step([])
    assert 0 <= scene.scroll <= scene.max_scroll
