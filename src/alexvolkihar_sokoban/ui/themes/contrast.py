"""Colour-blind-safe theme: Okabe–Ito colours and shape coding, so no state relies on colour alone.

Goals are rings, boxes are squares with a cross, a box on a goal is a square with a check mark, the player
is a white disc; walls are outlined blocks.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.themes._draw import check_mark, cross, inset_rect, new_tile, px, ring
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

BACKGROUND: RGB = (0, 0, 0)
FLOOR: RGB = (34, 34, 34)
WALL: RGB = (86, 180, 233)  # sky blue
BOX: RGB = (230, 159, 0)  # orange
GOAL: RGB = (240, 228, 66)  # yellow
DONE: RGB = (0, 158, 115)  # bluish green
PLAYER: RGB = (255, 255, 255)


class ContrastTheme(CachedTheme):
    id = "contrast"
    name = "High contrast"
    background = BACKGROUND
    palette = UiPalette(
        text=(255, 255, 255),
        muted=(190, 190, 190),
        accent=GOAL,
        panel=(20, 20, 20),
        good=DONE,
        bad=(213, 94, 0),  # vermillion
    )

    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        if kind is TileKind.OUTSIDE:
            return new_tile(size)
        if kind is TileKind.WALL:
            surface = new_tile(size, BACKGROUND)
            block = inset_rect(size, 0.06)
            pygame.draw.rect(surface, WALL, block, width=px(size, 0.12))
            pygame.draw.rect(surface, WALL, inset_rect(size, 0.34))
            return surface
        surface = new_tile(size, FLOOR)
        if kind in (TileKind.GOAL, TileKind.PLAYER_ON_GOAL):
            ring(surface, GOAL, size, 0.36, 0.1)
        box = inset_rect(size, 0.12)
        if kind is TileKind.BOX:
            pygame.draw.rect(surface, BOX, box)
            cross(surface, BACKGROUND, box.inflate(-px(size, 0.16), -px(size, 0.16)), px(size, 0.1))
        elif kind is TileKind.BOX_ON_GOAL:
            pygame.draw.rect(surface, DONE, box)
            check_mark(surface, PLAYER, box, px(size, 0.12))
        elif kind in (TileKind.PLAYER, TileKind.PLAYER_ON_GOAL):
            pygame.draw.circle(surface, PLAYER, (size // 2, size // 2), px(size, 0.26))
        return surface
