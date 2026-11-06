import json
from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.board_renderer import tile_kind_at
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.themes import SAMPLE_LEVEL, ThemesScene, theme_label
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.themes.registry import THEME_IDS, available_themes


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


def themes_app(tmp_path: Path, **settings: object) -> tuple[App, AppContext, ThemesScene]:
    ctx = AppContext.load(tmp_path, bundled=[])
    for name, value in settings.items():
        setattr(ctx.settings, name, value)
    app = App(ctx.settings, context=ctx, headless=True)
    scene = app.push("themes")
    assert isinstance(scene, ThemesScene)
    return app, ctx, scene


def test_sample_board_has_one_of_each_piece() -> None:
    kinds = [
        tile_kind_at(SAMPLE_LEVEL, (r, c), SAMPLE_LEVEL.player, SAMPLE_LEVEL.boxes)
        for r in range(SAMPLE_LEVEL.height)
        for c in range(SAMPLE_LEVEL.width)
    ]
    assert (SAMPLE_LEVEL.width, SAMPLE_LEVEL.height) == (7, 7)
    assert kinds.count(TileKind.GOAL) == 1 and kinds.count(TileKind.BOX) == 1
    assert kinds.count(TileKind.BOX_ON_GOAL) == 1 and kinds.count(TileKind.PLAYER) == 1


def test_lists_every_theme_starting_on_the_current_one(tmp_path: Path) -> None:
    _, _, scene = themes_app(tmp_path, theme="neon")
    assert [th.id for th in scene.themes] == list(THEME_IDS) and len(scene.themes) == 20
    assert scene.highlighted.id == "neon"


def test_theme_selection_applies_and_saves(tmp_path: Path) -> None:
    app, ctx, scene = themes_app(tmp_path)
    app.step([DOWN, DOWN])
    assert scene.highlighted.id == "neon" and app.theme.id == "kenney"  # highlight alone applies nothing
    app.step([ENTER])
    assert app.theme.id == "neon" and ctx.settings.theme == "neon"
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["theme"] == "neon"
    assert app.top is scene  # stays open: Back returns


def test_back_keeps_the_applied_theme(tmp_path: Path) -> None:
    app, ctx, _ = themes_app(tmp_path)
    app.step([DOWN, ESCAPE])
    assert app.theme.id == "kenney" and ctx.settings.theme == "kenney" and app.top is None


def test_preview_uses_highlighted_theme(tmp_path: Path) -> None:
    app, _, scene = themes_app(tmp_path)
    app.step([DOWN, DOWN, DOWN])  # contrast: black background, distinct tiles
    contrast = scene.highlighted
    assert contrast.id == "contrast" and app.theme.id == "kenney"
    app.step([])
    assert scene.preview_rect is not None and scene.preview_layout is not None
    inner = scene.preview_rect.inflate(-8, -8)
    assert app.screen.get_at(inner.topleft)[:3] == contrast.background
    layout = scene.preview_layout
    for pos in (SAMPLE_LEVEL.player, *SAMPLE_LEVEL.boxes):
        kind = tile_kind_at(SAMPLE_LEVEL, pos, SAMPLE_LEVEL.player, SAMPLE_LEVEL.boxes)
        tile = contrast.tile(kind, layout.tile)
        cell = layout.cell_rect(pos)
        expected = tile.get_at((layout.tile // 2, layout.tile // 2))
        assert app.screen.get_at(cell.center)[:3] == expected[:3]


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
def test_list_scrolls_to_keep_the_selection_visible(tmp_path: Path, size: tuple[int, int]) -> None:
    app, _, scene = themes_app(tmp_path, window=size)
    app.step([UP])  # wraps from the first theme to the last
    assert scene.highlighted.id == THEME_IDS[-1]
    app.step([])
    screen = app.screen.get_rect()
    visible = dict(scene.scroll.item_rects)
    assert len(THEME_IDS) - 1 in visible
    assert all(scene.list_rect.contains(r) and screen.contains(r) for r in visible.values())
    if size == (640, 480):
        assert len(visible) < len(THEME_IDS) and scene.scroll.first > 0
    app.step([DOWN])
    app.step([])
    assert scene.highlighted.id == THEME_IDS[0] and scene.scroll.first == 0


def test_mouse_hover_previews_click_applies_wheel_moves(tmp_path: Path) -> None:
    app, ctx, scene = themes_app(tmp_path)
    app.step([])
    index, rect = scene.scroll.item_rects[2]
    app.step([pygame.event.Event(pygame.MOUSEMOTION, pos=rect.center, rel=(0, 0), buttons=(0, 0, 0))])
    assert scene.highlighted.id == THEME_IDS[index] and app.theme.id == "kenney"
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)])
    assert app.theme.id == THEME_IDS[index] and ctx.settings.theme == THEME_IDS[index]
    app.step([pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False)])
    assert scene.highlighted.id == THEME_IDS[index + 1]


def test_theme_names_follow_the_language(tmp_path: Path) -> None:
    themes = {th.id: th for th in available_themes()}
    set_language("en")
    assert theme_label(themes["contrast"]) == "High contrast"
    set_language("fr")
    assert theme_label(themes["classic"]) == "Classique"
    assert all(theme_label(th) for th in themes.values())


def test_without_context_applies_without_saving() -> None:
    app = App(Settings(), headless=True)
    scene = app.push("themes")
    assert isinstance(scene, ThemesScene)
    app.step([DOWN, ENTER])
    assert app.theme.id == "classic" and app.settings.theme == "classic"


@pytest.mark.parametrize("language", ["en", "fr"])
def test_every_theme_previews_at_min_size(tmp_path: Path, language: str) -> None:
    app, _, scene = themes_app(tmp_path, window=(640, 480), language=language)
    for _ in THEME_IDS:
        app.step([DOWN])
        app.step([])
        assert scene.preview_rect is not None and app.screen.get_rect().contains(scene.preview_rect)
