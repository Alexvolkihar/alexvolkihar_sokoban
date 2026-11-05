"""Flat-colour theme drawn with pygame primitives; always available, needs no asset."""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

_FLOOR: RGB = (214, 205, 186)
_WALL: RGB = (92, 72, 58)
_GOAL: RGB = (200, 60, 60)
_BOX: RGB = (176, 120, 56)
_BOX_DONE: RGB = (70, 150, 80)
_PLAYER: RGB = (40, 90, 200)
_OUTSIDE: RGB = (36, 36, 44)


class FallbackTheme(CachedTheme):
    id = "fallback"
    name = "Fallback"
    background: RGB = _OUTSIDE
    palette = UiPalette(
        text=(240, 240, 240),
        muted=(150, 150, 160),
        accent=(240, 180, 60),
        panel=(52, 52, 64),
        good=(90, 190, 100),
        bad=(220, 80, 80),
    )

    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        surface = pygame.Surface((size, size))
        if kind is TileKind.OUTSIDE:
            surface.fill(_OUTSIDE)
            return surface
        if kind is TileKind.WALL:
            surface.fill(_WALL)
            return surface
        surface.fill(_FLOOR)
        inset = max(1, size // 6)
        inner = pygame.Rect(inset, inset, max(1, size - 2 * inset), max(1, size - 2 * inset))
        if kind in (TileKind.GOAL, TileKind.PLAYER_ON_GOAL):
            dot = max(1, size // 4)
            pygame.draw.rect(surface, _GOAL, pygame.Rect((size - dot) // 2, (size - dot) // 2, dot, dot))
        if kind is TileKind.BOX:
            pygame.draw.rect(surface, _BOX, inner)
        elif kind is TileKind.BOX_ON_GOAL:
            pygame.draw.rect(surface, _BOX_DONE, inner)
        elif kind in (TileKind.PLAYER, TileKind.PLAYER_ON_GOAL):
            pygame.draw.circle(
                surface, _PLAYER, (size // 2, size // 2), max(1, size // 3), width=max(1, size // 8)
            )
        return surface
