from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.ui import thumbnails
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.themes.registry import get_theme
from alexvolkihar_sokoban.ui.thumbnails import clear_thumbnail_cache, render_thumbnail

SMALL = Level.from_rows(["#####", "#@$.#", "#####"])
SQUARE = Level.from_rows(["#######", "#     #", "# @$. #", "#     #", "#######"])


def big_level(size: int = 60) -> Level:
    inner = " " * (size - 2)
    rows = ["#" * size] + [f"#{inner}#" for _ in range(size - 2)] + ["#" * size]
    rows[1] = "#@$." + " " * (size - 5) + "#"
    return Level.from_rows(rows)


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    pygame.display.init()
    clear_thumbnail_cache()
    yield
    clear_thumbnail_cache()


@pytest.mark.parametrize("max_size", [(160, 100), (100, 160), (40, 40), (13, 9)])
@pytest.mark.parametrize("level", [SMALL, SQUARE, big_level()], ids=["small", "square", "60x60"])
def test_thumbnail_fits_max_size_and_keeps_aspect(level: Level, max_size: tuple[int, int]) -> None:
    surface = render_thumbnail(level, get_theme("classic"), max_size)
    w, h = surface.get_size()
    assert 1 <= w <= max_size[0] and 1 <= h <= max_size[1]
    # The board fills the limiting side (no needless margin) and keeps the level's proportions.
    assert w == max_size[0] or h == max_size[1] or w >= level.width * 4
    assert abs(w / h - level.width / level.height) < 0.25


def test_thumbnail_uses_integer_theme_tiles_when_they_fit() -> None:
    theme = get_theme("classic")
    surface = render_thumbnail(SMALL, theme, (200, 200))
    tile = 200 // SMALL.width
    assert surface.get_size() == (tile * SMALL.width, tile * SMALL.height)
    # The box cell (row 1, col 2) is the theme's box tile, unscaled.
    box = theme.tile(TileKind.BOX, tile)
    centre = (2 * tile + tile // 2, tile + tile // 2)
    assert surface.get_at(centre) == box.get_at((tile // 2, tile // 2))


def test_thumbnail_is_cached_per_level_theme_and_size() -> None:
    classic, neon = get_theme("classic"), get_theme("neon")
    first = render_thumbnail(SQUARE, classic, (120, 90))
    assert render_thumbnail(SQUARE, classic, (120, 90)) is first
    # Same layout, another Level object: same hash, same thumbnail.
    assert render_thumbnail(Level.from_rows(SQUARE.to_rows()), classic, (120, 90)) is first
    assert render_thumbnail(SQUARE, neon, (120, 90)) is not first
    assert render_thumbnail(SQUARE, classic, (121, 90)) is not first
    assert render_thumbnail(SMALL, classic, (120, 90)) is not first


def test_thumbnail_cache_is_bounded() -> None:
    theme = get_theme("classic")
    first = render_thumbnail(SMALL, theme, (10, 10))
    for size in range(11, 11 + thumbnails.CACHE_SIZE):
        render_thumbnail(SMALL, theme, (size, size))
    assert len(thumbnails._cache) == thumbnails.CACHE_SIZE
    assert render_thumbnail(SMALL, theme, (10, 10)) is not first  # the oldest entry was dropped


def test_thumbnail_rejects_empty_size() -> None:
    with pytest.raises(ValueError):
        render_thumbnail(SMALL, get_theme("classic"), (0, 40))
