"""Draws a board state with the current theme, scaled to an integer tile size (spec 7.9)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pygame

from alexvolkihar_sokoban.core.geometry import Direction, Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.ui.themes.base import Theme, TileKind


def tile_kind_at(level: Level, pos: Pos, player: Pos, boxes: frozenset[Pos]) -> TileKind:
    """What to draw at ``pos`` for this state; cells off the player's floor (except walls) are ``OUTSIDE``."""
    if pos in level.walls:
        return TileKind.WALL
    if not level.is_floor(pos):
        return TileKind.OUTSIDE
    goal = pos in level.goals
    if pos == player:
        return TileKind.PLAYER_ON_GOAL if goal else TileKind.PLAYER
    if pos in boxes:
        return TileKind.BOX_ON_GOAL if goal else TileKind.BOX
    return TileKind.GOAL if goal else TileKind.FLOOR


@dataclass(frozen=True)
class BoardLayout:
    """``tile`` px per cell; ``origin`` is the pixel ``(x, y)`` of cell ``(0, 0)``'s top-left corner."""

    tile: int
    origin: tuple[int, int]

    def cell_rect(self, pos: Pos) -> pygame.Rect:
        row, col = pos
        return pygame.Rect(
            self.origin[0] + col * self.tile, self.origin[1] + row * self.tile, self.tile, self.tile
        )


class BoardRenderer:
    MIN_TILE = 4
    MAX_TILE = 96  # beyond this a tiny level only gets blurrier, not more readable

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def layout(self, level: Level, area: pygame.Rect) -> BoardLayout:
        """The largest integer tile (between ``MIN_TILE`` and ``MAX_TILE``) that fits, board centred."""
        fit = min(area.width // max(1, level.width), area.height // max(1, level.height))
        tile = max(self.MIN_TILE, min(self.MAX_TILE, fit))
        x = area.x + (area.width - tile * level.width) // 2
        y = area.y + (area.height - tile * level.height) // 2
        return BoardLayout(tile, (x, y))

    def draw(
        self,
        surface: pygame.Surface,
        level: Level,
        player: Pos,
        boxes: frozenset[Pos],
        area: pygame.Rect,
        *,
        highlight: Iterable[Pos] = (),
        arrow: tuple[Pos, Direction] | None = None,
    ) -> BoardLayout:
        """Draw the state inside ``area`` (clipped to it) and return the layout used."""
        layout = self.layout(level, area)
        tile = layout.tile
        old_clip = surface.get_clip()
        surface.set_clip(area.clip(old_clip))
        try:
            blits = [
                (self.theme.tile(tile_kind_at(level, (r, c), player, boxes), tile), layout.cell_rect((r, c)))
                for r in range(level.height)
                for c in range(level.width)
            ]
            surface.blits(blits, doreturn=False)
            accent = self.theme.palette.accent
            for pos in highlight:
                pygame.draw.rect(surface, accent, layout.cell_rect(pos), width=max(1, tile // 10))
            if arrow is not None:
                _draw_arrow(surface, layout.cell_rect(arrow[0]), arrow[1], accent)
        finally:
            surface.set_clip(old_clip)
        return layout


def _draw_arrow(
    surface: pygame.Surface, cell: pygame.Rect, d: Direction, colour: tuple[int, int, int]
) -> None:
    """A triangle in ``cell`` pointing towards ``d``."""
    cx, cy = cell.center
    half = max(2, cell.width * 3 // 8)
    # Points for an arrow pointing right, then rotated: (x, y) → direction basis (dc, dr).
    shape = [(half, 0), (-half // 2, -half), (-half // 2, half)]
    dx, dy = d.dc, d.dr
    points = [(cx + px * dx - py * dy, cy + px * dy + py * dx) for px, py in shape]
    pygame.draw.polygon(surface, colour, points)
    pygame.draw.polygon(surface, (0, 0, 0), points, width=1)
