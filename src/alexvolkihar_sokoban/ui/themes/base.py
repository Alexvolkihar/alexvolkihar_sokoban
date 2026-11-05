"""Theme contract shared by every theme and the board renderer (spec 7.10)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

import pygame


class TileKind(Enum):
    FLOOR = auto()
    WALL = auto()
    GOAL = auto()
    BOX = auto()
    BOX_ON_GOAL = auto()
    PLAYER = auto()
    PLAYER_ON_GOAL = auto()
    OUTSIDE = auto()


RGB = tuple[int, int, int]


@dataclass(frozen=True)
class UiPalette:
    text: RGB
    muted: RGB
    accent: RGB
    panel: RGB
    good: RGB
    bad: RGB


class Theme(Protocol):
    id: str
    name: str
    background: RGB
    palette: UiPalette

    def tile(self, kind: TileKind, size: int) -> pygame.Surface:
        """A ``size`` x ``size`` tile. The surface may be shared: callers must not draw on it."""
        ...


class CachedTheme(ABC):
    """Base class for themes: ``tile()`` caches ``_draw()`` per ``(kind, size)``."""

    id: str
    name: str
    background: RGB
    palette: UiPalette

    def __init__(self) -> None:
        self._cache: dict[tuple[TileKind, int], pygame.Surface] = {}

    def tile(self, kind: TileKind, size: int) -> pygame.Surface:
        if size < 1:
            raise ValueError(f"tile size must be at least 1 px, got {size}")
        key = (kind, size)
        surface = self._cache.get(key)
        if surface is None:
            surface = self._draw(kind, size)
            self._cache[key] = surface
        return surface

    @abstractmethod
    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        """Draw one tile; called once per ``(kind, size)``."""
