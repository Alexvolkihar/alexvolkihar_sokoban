"""Kenney theme floor: a sand ground under every tile instead of the legacy all-black ``empty.png``."""

import pygame
import pytest

from alexvolkihar_sokoban.ui.themes._draw import distance
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.themes.kenney import KenneyTheme

SIZE = 64


def _pixels(surface: pygame.Surface) -> list[pygame.Color]:
    w, h = surface.get_size()
    return [surface.get_at((x, y)) for y in range(h) for x in range(w)]


def _black_fraction(surface: pygame.Surface) -> float:
    pixels = _pixels(surface)
    return sum(1 for p in pixels if p.a > 0 and p.r + p.g + p.b < 30) / len(pixels)


def _mean(surface: pygame.Surface) -> tuple[int, int, int]:
    pixels = _pixels(surface)
    n = len(pixels)
    return (sum(p.r for p in pixels) // n, sum(p.g for p in pixels) // n, sum(p.b for p in pixels) // n)


def test_floor_is_an_opaque_light_ground() -> None:
    floor = KenneyTheme().tile(TileKind.FLOOR, SIZE)
    assert all(p.a == 255 for p in _pixels(floor))
    assert sum(_mean(floor)) > 3 * 140  # no longer the black legacy sprite
    assert _black_fraction(floor) == 0


def test_floor_stands_out_from_the_background() -> None:
    theme = KenneyTheme()
    assert distance(_mean(theme.tile(TileKind.FLOOR, SIZE)), theme.background) > 40


def test_floor_is_textured_not_flat() -> None:
    floor = KenneyTheme().tile(TileKind.FLOOR, SIZE)
    assert len({tuple(p) for p in _pixels(floor)}) >= 3


@pytest.mark.parametrize(
    "kind", [TileKind.GOAL, TileKind.BOX, TileKind.BOX_ON_GOAL, TileKind.PLAYER, TileKind.PLAYER_ON_GOAL]
)
def test_pieces_stand_on_the_floor_without_a_black_square(kind: TileKind) -> None:
    theme = KenneyTheme()
    floor, tile = theme.tile(TileKind.FLOOR, SIZE), theme.tile(kind, SIZE)
    assert _black_fraction(tile) < 0.02
    for corner in ((0, 0), (SIZE - 1, 0), (0, SIZE - 1), (SIZE - 1, SIZE - 1)):
        assert tile.get_at(corner) == floor.get_at(corner)


@pytest.mark.parametrize("size", [4, 7, 16, 33, 96])
def test_floor_scales(size: int) -> None:
    theme = KenneyTheme()
    assert theme.tile(TileKind.FLOOR, size).get_size() == (size, size)
    assert _black_fraction(theme.tile(TileKind.PLAYER, size)) < 0.05
