import pygame
import pytest

from alexvolkihar_sokoban.ui.themes.base import CachedTheme, Theme, TileKind, UiPalette
from alexvolkihar_sokoban.ui.themes.fallback import FallbackTheme
from alexvolkihar_sokoban.ui.themes.registry import DEFAULT_THEME_ID, available_themes, get_theme


def test_fallback_theme_draws_every_tile_kind() -> None:
    for k in TileKind:
        assert get_theme("anything").tile(k, 32).get_size() == (32, 32)


def test_tile_kinds() -> None:
    assert [k.name for k in TileKind] == [
        "FLOOR",
        "WALL",
        "GOAL",
        "BOX",
        "BOX_ON_GOAL",
        "PLAYER",
        "PLAYER_ON_GOAL",
        "OUTSIDE",
    ]


def test_fallback_theme_metadata() -> None:
    theme = FallbackTheme()
    assert isinstance(theme, CachedTheme)
    assert theme.id == "fallback" and theme.name
    assert isinstance(theme.palette, UiPalette) and len(theme.background) == 3


def test_registry_contract() -> None:
    # Only properties that stay true once the real themes are registered.
    assert DEFAULT_THEME_ID == "kenney"
    themes: list[Theme] = available_themes()
    ids = {t.id for t in themes}
    assert themes and all(t.id and t.name for t in themes)
    assert get_theme("no-such-theme").id in ids and get_theme(DEFAULT_THEME_ID).id in ids


def test_tiles_are_cached_per_kind_and_size() -> None:
    theme = FallbackTheme()
    assert theme.tile(TileKind.BOX, 16) is theme.tile(TileKind.BOX, 16)
    assert theme.tile(TileKind.BOX, 16) is not theme.tile(TileKind.BOX, 17)
    assert theme.tile(TileKind.BOX, 4).get_size() == (4, 4)


def test_tile_kinds_look_different() -> None:
    theme = FallbackTheme()
    pixels = {k: pygame.image.tobytes(theme.tile(k, 16), "RGBA") for k in TileKind}
    assert len(set(pixels.values())) == len(TileKind)


def test_tile_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        FallbackTheme().tile(TileKind.FLOOR, 0)


def test_cached_theme_calls_draw_once() -> None:
    calls: list[tuple[TileKind, int]] = []

    class Counting(FallbackTheme):
        def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
            calls.append((kind, size))
            return super()._draw(kind, size)

    t = Counting()
    t.tile(TileKind.WALL, 8)
    t.tile(TileKind.WALL, 8)
    assert calls == [(TileKind.WALL, 8)]


def test_tile_cache_keeps_only_recent_sizes() -> None:
    calls: list[int] = []

    class Counting(FallbackTheme):
        def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
            calls.append(size)
            return super()._draw(kind, size)

    t = Counting()
    for size in (8, 9, 10, 11, 12):  # e.g. a window being resized
        t.tile(TileKind.WALL, size)
    t.tile(TileKind.WALL, 12)
    assert calls == [8, 9, 10, 11, 12]
    t.tile(TileKind.WALL, 8)  # evicted long ago: drawn again
    assert calls[-1] == 8 and len({s for _, s in t._cache}) <= 3
