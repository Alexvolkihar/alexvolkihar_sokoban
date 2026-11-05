"""Small pictures of levels for the level select grid, drawn with the theme's own tiles.

A thumbnail uses whole theme tiles when they are at least ``MIN_TILE`` px; a level too big for that is
drawn at ``MIN_TILE`` and scaled down smoothly. Results are memoised per (level hash, theme id, max size),
with a bounded cache so browsing many packs and themes does not keep every picture alive.
"""

from __future__ import annotations

from collections import OrderedDict

import pygame

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.ui.board_renderer import tile_kind_at
from alexvolkihar_sokoban.ui.themes.base import Theme

MIN_TILE = 4  # below this the theme's tiles are unreadable: draw bigger, then scale down
CACHE_SIZE = 256

_cache: OrderedDict[tuple[str, str, tuple[int, int]], pygame.Surface] = OrderedDict()


def clear_thumbnail_cache() -> None:
    _cache.clear()


def render_thumbnail(level: Level, theme: Theme, max_size: tuple[int, int]) -> pygame.Surface:
    """The level's start position, as large as fits in ``max_size`` with the level's proportions.

    The returned surface is shared through the cache: callers must not draw on it.
    """
    max_w, max_h = max_size
    if max_w < 1 or max_h < 1:
        raise ValueError(f"thumbnail size must be positive, got {max_size}")
    key = (level.canonical_hash(), theme.id, (max_w, max_h))
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached
    surface = _render(level, theme, max_w, max_h)
    _cache[key] = surface
    if len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return surface


def _render(level: Level, theme: Theme, max_w: int, max_h: int) -> pygame.Surface:
    tile = max(MIN_TILE, min(max_w // level.width, max_h // level.height))
    surface = pygame.Surface((tile * level.width, tile * level.height), pygame.SRCALPHA)
    surface.blits(
        [
            (
                theme.tile(tile_kind_at(level, (r, c), level.player, level.boxes), tile),
                (c * tile, r * tile),
            )
            for r in range(level.height)
            for c in range(level.width)
        ],
        doreturn=False,
    )
    w, h = surface.get_size()
    if w <= max_w and h <= max_h:
        return surface
    scale = min(max_w / w, max_h / h)
    size = (max(1, min(max_w, round(w * scale))), max(1, min(max_h, round(h * scale))))
    return pygame.transform.smoothscale(surface, size)
