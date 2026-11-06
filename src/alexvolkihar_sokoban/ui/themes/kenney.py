"""Kenney theme: sprites from Kenney's "Sokoban" pack (CC0 1.0).

The wall, crate and goal sprites sit on a black square, so the floor is a sand ground drawn procedurally in
the pack's style; the goal marker is the goal sprite with its black background keyed out and the player is
the pack's character on a transparent background (``icon.png``), both over that ground. ``BOX_ON_GOAL``
and ``PLAYER_ON_GOAL`` have no sprite of their own and are composited: a green-tinted crate with a goal
ring, and the player over the goal. Sprites are loaded with ``importlib.resources`` and
``pygame.image.load`` without ``convert()``, so the theme works before a display exists.
"""

from __future__ import annotations

from importlib.resources import files

import pygame

from alexvolkihar_sokoban.ui.themes._draw import new_tile, ring
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

FLOOR = "ground"  # drawn by _draw_ground(), not a file
WALL = "WallRound_Brown"
GOAL = "EndPoint_Brown"
BOX = "Crate_Brown"
PLAYER = "icon"  # the pack's Character4 sprite, on a transparent background
BASE_SIZE = 64  # size of the Kenney sprites; the ground is drawn at this size too

_SAND: RGB = (221, 194, 148)
_SAND_EDGE: RGB = (200, 171, 124)
_SAND_LIGHT: RGB = (234, 212, 172)
_PEBBLE: RGB = (186, 156, 110)
# (x, y, w, h) at BASE_SIZE: a few pebbles, darker with a light highlight above, like the Kenney ground tiles.
_PEBBLES = ((12, 14, 6, 4), (40, 9, 4, 3), (47, 36, 7, 4), (19, 44, 4, 3), (30, 26, 3, 2), (8, 31, 3, 2))

_DONE_TINT: RGB = (140, 255, 140)
_DONE_GLOW: RGB = (0, 40, 10)
_GOAL_RING: RGB = (198, 160, 120)
_GOAL_RING_EDGE: RGB = (60, 40, 22)


def load_sprite(name: str) -> pygame.Surface:
    resource = files("alexvolkihar_sokoban.data") / "themes" / "kenney" / f"{name}.png"
    with resource.open("rb") as fh:
        return pygame.image.load(fh, f"{name}.png")


def _draw_ground() -> pygame.Surface:
    """A sand floor slab: flat sand, a slightly darker rim and a few pebbles."""
    size = BASE_SIZE
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    surface.fill(_SAND_EDGE)
    pygame.draw.rect(surface, _SAND, pygame.Rect(2, 2, size - 4, size - 4), border_radius=4)
    for x, y, w, h in _PEBBLES:
        pygame.draw.ellipse(surface, _SAND_LIGHT, pygame.Rect(x, y - 1, w, h))
        pygame.draw.ellipse(surface, _PEBBLE, pygame.Rect(x, y, w, h))
    return surface


def _key_out_black(sprite: pygame.Surface) -> pygame.Surface:
    """A copy of ``sprite`` where the pure black background pixels are transparent."""
    keyed = sprite.copy()
    w, h = keyed.get_size()
    for y in range(h):
        for x in range(w):
            colour = keyed.get_at((x, y))
            if colour.r == colour.g == colour.b == 0:
                keyed.set_at((x, y), (0, 0, 0, 0))
    return keyed


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
            if name == FLOOR:
                sprite = _draw_ground()
            elif name == GOAL:
                sprite = _key_out_black(load_sprite(GOAL))
            else:
                sprite = load_sprite(name)
            self._sprites[name] = sprite
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
        surface = self._sprite(FLOOR, size)
        if kind in (TileKind.GOAL, TileKind.PLAYER_ON_GOAL):
            surface.blit(self._sprite(GOAL, size), (0, 0))
        if kind is TileKind.GOAL:
            return surface
        if kind in (TileKind.PLAYER, TileKind.PLAYER_ON_GOAL):
            if kind is TileKind.PLAYER_ON_GOAL:
                ring(surface, _GOAL_RING_EDGE, size, 0.45, 0.1)
                ring(surface, _GOAL_RING, size, 0.44, 0.07)
            surface.blit(self._sprite(PLAYER, size), (0, 0))
            return surface
        crate = self._sprite(BOX, size)
        if kind is TileKind.BOX_ON_GOAL:
            crate.fill(_DONE_TINT, special_flags=pygame.BLEND_RGB_MULT)
            crate.fill(_DONE_GLOW, special_flags=pygame.BLEND_RGB_ADD)
            ring(crate, _GOAL_RING_EDGE, size, 0.2, 0.1)
            ring(crate, _GOAL_RING, size, 0.18, 0.06)
        surface.blit(crate, (0, 0))
        return surface
