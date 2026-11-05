"""Colour helpers and drawing primitives shared by the procedurally drawn themes."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import pygame

from alexvolkihar_sokoban.ui.themes.base import RGB

BLACK: RGB = (0, 0, 0)
WHITE: RGB = (255, 255, 255)


# --- colours -------------------------------------------------------------------------------------------


def hex_rgb(value: str) -> RGB:
    """``"#357660"`` -> ``(53, 118, 96)``."""
    text = value.strip().removeprefix("#")
    if len(text) != 6:
        raise ValueError(f"expected a #rrggbb colour, got {value!r}")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """Linear blend: ``t = 0`` gives ``a``, ``t = 1`` gives ``b``."""
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def lighten(color: RGB, t: float) -> RGB:
    return mix(color, WHITE, t)


def darken(color: RGB, t: float) -> RGB:
    return mix(color, BLACK, t)


def relative_luminance(color: RGB) -> float:
    """WCAG 2 relative luminance."""

    def channel(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = color
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG 2 contrast ratio, from 1 (same luminance) to 21 (black on white)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def distance(a: RGB, b: RGB) -> float:
    """Perceptual-ish colour distance ("redmean"), 0 to about 765."""
    rmean = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt((2 + rmean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rmean) / 256) * db * db)


def most_distinct(candidates: Sequence[RGB], against: Iterable[RGB]) -> RGB:
    """The candidate whose nearest colour in ``against`` is the farthest (first one wins ties)."""
    others = list(against)
    return max(candidates, key=lambda c: min(distance(c, o) for o in others))


def first_distinct(candidates: Sequence[RGB], against: Iterable[RGB], minimum: float) -> RGB:
    """The first candidate at least ``minimum`` away from all of ``against``, else the most distinct one."""
    others = list(against)
    for candidate in candidates:
        if all(distance(candidate, o) >= minimum for o in others):
            return candidate
    return most_distinct(candidates, others)


def readable_on(background: RGB, color: RGB, minimum: float) -> RGB:
    """``color``, darkened or lightened just enough to reach ``minimum`` contrast on ``background``."""
    target = BLACK if relative_luminance(background) > 0.18 else WHITE
    for step in range(21):
        candidate = mix(color, target, step / 20)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return target


def ink_on(background: RGB) -> RGB:
    """A near-black or near-white ink, whichever reads better on ``background``."""
    dark, light = (24, 22, 28), (250, 248, 240)
    if contrast_ratio(dark, background) >= contrast_ratio(light, background):
        return dark
    return light


# --- surfaces and shapes -------------------------------------------------------------------------------


def new_tile(size: int, color: RGB | None = None) -> pygame.Surface:
    """A ``size`` x ``size`` surface with per-pixel alpha, filled with ``color`` or transparent."""
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    if color is not None:
        surface.fill(color)
    return surface


def px(size: int, fraction: float) -> int:
    """A stroke width or length proportional to the tile size, never below 1 px."""
    return max(1, round(size * fraction))


def inset_rect(size: int, fraction: float) -> pygame.Rect:
    margin = round(size * fraction)
    side = max(1, size - 2 * margin)
    return pygame.Rect(margin, margin, side, side)


def center(size: int) -> tuple[int, int]:
    return (size // 2, size // 2)


def ring(surface: pygame.Surface, color: RGB, size: int, radius: float, width: float) -> None:
    """A centred ring; ``radius`` and ``width`` are fractions of the tile size."""
    pygame.draw.circle(surface, color, center(size), px(size, radius), width=px(size, width))


def disc(surface: pygame.Surface, color: RGB, size: int, radius: float) -> None:
    pygame.draw.circle(surface, color, center(size), px(size, radius))


def cross(surface: pygame.Surface, color: RGB, rect: pygame.Rect, width: int) -> None:
    pygame.draw.line(surface, color, rect.topleft, (rect.right - 1, rect.bottom - 1), width)
    pygame.draw.line(surface, color, (rect.right - 1, rect.top), (rect.left, rect.bottom - 1), width)


def check_mark(surface: pygame.Surface, color: RGB, rect: pygame.Rect, width: int) -> None:
    points = [
        (rect.left + rect.width * 0.18, rect.top + rect.height * 0.52),
        (rect.left + rect.width * 0.42, rect.top + rect.height * 0.76),
        (rect.left + rect.width * 0.84, rect.top + rect.height * 0.26),
    ]
    pygame.draw.lines(surface, color, False, points, width)


def bevel(surface: pygame.Surface, rect: pygame.Rect, light: RGB, shadow: RGB, width: int) -> None:
    """Light top and left edges, dark bottom and right edges."""
    pygame.draw.rect(surface, light, (rect.left, rect.top, rect.width, width))
    pygame.draw.rect(surface, light, (rect.left, rect.top, width, rect.height))
    pygame.draw.rect(surface, shadow, (rect.left, rect.bottom - width, rect.width, width))
    pygame.draw.rect(surface, shadow, (rect.right - width, rect.top, width, rect.height))


def bricks(surface: pygame.Surface, rect: pygame.Rect, mortar: RGB, rows: int, width: int) -> None:
    """Running-bond brick joints inside ``rect``."""
    row_h = rect.height / rows
    for r in range(1, rows):
        y = rect.top + round(r * row_h)
        pygame.draw.line(surface, mortar, (rect.left, y), (rect.right - 1, y), width)
    for r in range(rows):
        top = rect.top + round(r * row_h)
        bottom = rect.top + round((r + 1) * row_h)
        offsets = (0.5,) if r % 2 == 0 else (0.0, 1.0)
        for o in offsets:
            x = rect.left + round(o * (rect.width - 1))
            pygame.draw.line(surface, mortar, (x, top), (x, bottom), width)


def glow_rect(
    surface: pygame.Surface, color: RGB, rect: pygame.Rect, width: int, layers: int = 3, radius: int = 0
) -> None:
    """A rectangle outline with a soft halo (wider, fainter copies underneath)."""
    for i in range(layers, 0, -1):
        halo = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        alpha = round(150 / (i + 1))
        grown = rect.inflate(2 * i * width, 2 * i * width)
        pygame.draw.rect(
            halo, (*color, alpha), grown, width=width * (i + 1), border_radius=radius + i * width
        )
        surface.blit(halo, (0, 0))
    pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)


def glow_circle(
    surface: pygame.Surface, color: RGB, pos: tuple[int, int], radius: int, width: int, layers: int = 3
) -> None:
    """A circle outline (``width = 0``: filled disc) with a soft halo."""
    stroke = width or radius
    for i in range(layers, 0, -1):
        halo = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        alpha = round(150 / (i + 1))
        pygame.draw.circle(halo, (*color, alpha), pos, radius + i * stroke // 2 + i, width=0)
        if width:
            pygame.draw.circle(halo, (0, 0, 0, 0), pos, max(0, radius - stroke - i), width=0)
        surface.blit(halo, (0, 0))
    pygame.draw.circle(surface, color, pos, radius, width=width)


def star(surface: pygame.Surface, color: RGB, pos: tuple[float, float], radius: float) -> None:
    """A four-pointed sparkle."""
    x, y = pos
    r, w = radius, radius * 0.3
    points = [(x, y - r), (x + w, y - w), (x + r, y), (x + w, y + w), (x, y + r), (x - w, y + w)]
    points += [(x - r, y), (x - w, y - w)]
    pygame.draw.polygon(surface, color, points)
