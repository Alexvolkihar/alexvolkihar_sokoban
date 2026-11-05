"""Kenney theme: the original Sokoban-LAMA sprites (Kenney "Sokoban" pack, CC0 1.0).

``BOX_ON_GOAL`` and ``PLAYER_ON_GOAL`` have no sprite of their own and are composited: a green-tinted crate
with a goal ring, and the player over the goal sprite. Sprites are loaded with ``importlib.resources`` and
``pygame.image.load`` without ``convert()``, so the theme works before a display exists.
"""

from __future__ import annotations

from importlib.resources import files

import pygame

from alexvolkihar_sokoban.ui.themes._draw import new_tile, ring
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

FLOOR = "empty"
WALL = "WallRound_Brown"
GOAL = "EndPoint_Brown"
BOX = "Crate_Brown"
PLAYER = "Character4"
PLAYER_CUTOUT = "icon"  # the same character on a transparent background

_DONE_TINT: RGB = (140, 255, 140)
_DONE_GLOW: RGB = (0, 40, 10)
_GOAL_RING: RGB = (198, 160, 120)
_GOAL_RING_EDGE: RGB = (60, 40, 22)


def load_sprite(name: str) -> pygame.Surface:
    resource = files("alexvolkihar_sokoban.data") / "themes" / "kenney" / f"{name}.png"
    with resource.open("rb") as fh:
        return pygame.image.load(fh, f"{name}.png")


class KenneyTheme(CachedTheme):
    id = "kenney"
    name = "Kenney"
    background: RGB = (236, 226, 206)
    palette = UiPalette(
        text=(48, 36, 26),
        muted=(112, 92, 70),
        accent=(160, 96, 30),
        panel=(250, 244, 232),
        good=(36, 118, 60),
        bad=(168, 48, 30),
    )

    def __init__(self) -> None:
        super().__init__()
        self._sprites: dict[str, pygame.Surface] = {}

    def _sprite(self, name: str, size: int) -> pygame.Surface:
        sprite = self._sprites.get(name)
        if sprite is None:
            sprite = self._sprites[name] = load_sprite(name)
        if sprite.get_size() == (size, size):
            return sprite.copy()
        return pygame.transform.smoothscale(sprite, (size, size))

    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        if kind is TileKind.OUTSIDE:
            return new_tile(size)
        if kind is TileKind.WALL:
            return self._sprite(WALL, size)
        if kind is TileKind.FLOOR:
            return self._sprite(FLOOR, size)
        if kind is TileKind.GOAL:
            return self._sprite(GOAL, size)
        if kind is TileKind.PLAYER:
            return self._sprite(PLAYER, size)
        if kind is TileKind.PLAYER_ON_GOAL:
            surface = self._sprite(GOAL, size)
            ring(surface, _GOAL_RING, size, 0.44, 0.07)
            surface.blit(self._sprite(PLAYER_CUTOUT, size), (0, 0))
            return surface
        surface = self._sprite(FLOOR, size)
        crate = self._sprite(BOX, size)
        if kind is TileKind.BOX_ON_GOAL:
            crate.fill(_DONE_TINT, special_flags=pygame.BLEND_RGB_MULT)
            crate.fill(_DONE_GLOW, special_flags=pygame.BLEND_RGB_ADD)
            ring(crate, _GOAL_RING_EDGE, size, 0.2, 0.1)
            ring(crate, _GOAL_RING, size, 0.18, 0.06)
        surface.blit(crate, (0, 0))
        return surface
