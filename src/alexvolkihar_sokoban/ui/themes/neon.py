"""Neon theme: dark background, glowing outlines, procedurally drawn."""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.themes._draw import (
    check_mark,
    glow_circle,
    glow_rect,
    inset_rect,
    new_tile,
    px,
)
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

BACKGROUND: RGB = (8, 6, 20)
FLOOR: RGB = (18, 16, 38)
GRID: RGB = (40, 34, 80)
WALL: RGB = (255, 46, 200)  # magenta
WALL_FILL: RGB = (60, 12, 64)
GOAL: RGB = (0, 240, 255)  # cyan
BOX: RGB = (255, 200, 40)  # amber
DONE: RGB = (60, 255, 120)  # green
PLAYER: RGB = (240, 240, 255)


class NeonTheme(CachedTheme):
    id = "neon"
    name = "Neon"
    background = BACKGROUND
    palette = UiPalette(
        text=(236, 234, 255),
        muted=(150, 146, 190),
        accent=GOAL,
        panel=(24, 20, 48),
        good=DONE,
        bad=(255, 90, 110),
    )

    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        if kind is TileKind.OUTSIDE:
            return new_tile(size)
        line = px(size, 0.06)
        if kind is TileKind.WALL:
            surface = new_tile(size, BACKGROUND)
            block = inset_rect(size, 0.14)
            pygame.draw.rect(surface, WALL_FILL, block, border_radius=px(size, 0.08))
            glow_rect(surface, WALL, block, line, radius=px(size, 0.08))
            return surface
        surface = new_tile(size, FLOOR)
        pygame.draw.rect(surface, GRID, (0, 0, size, size), width=1)
        mid = (size // 2, size // 2)
        if kind is TileKind.GOAL:
            glow_circle(surface, GOAL, mid, px(size, 0.3), line)
        elif kind is TileKind.PLAYER_ON_GOAL:
            glow_circle(surface, GOAL, mid, px(size, 0.38), line)
        box = inset_rect(size, 0.2)
        if kind is TileKind.BOX:
            glow_rect(surface, BOX, box, px(size, 0.08), radius=px(size, 0.05))
            pygame.draw.rect(surface, BOX, box.inflate(-px(size, 0.36), -px(size, 0.36)))
        elif kind is TileKind.BOX_ON_GOAL:
            pygame.draw.rect(surface, DONE, box, border_radius=px(size, 0.05))
            glow_rect(surface, DONE, box, px(size, 0.08), radius=px(size, 0.05))
            check_mark(surface, BACKGROUND, box, px(size, 0.1))
        elif kind in (TileKind.PLAYER, TileKind.PLAYER_ON_GOAL):
            glow_circle(surface, PLAYER, mid, px(size, 0.17), 0)
        return surface
