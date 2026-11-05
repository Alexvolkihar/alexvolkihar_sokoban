"""Game HUD (spec 7.9): level title, moves, pushes, time, par and key reminders, plus a toast message.

The HUD is a band at the top (title, then one "chip" per counter) and a line of key reminders at the bottom;
``draw_hud`` returns the rectangle left for the board between them.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import pygame

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import describe_binding
from alexvolkihar_sokoban.ui.themes.base import UiPalette

NO_PAR = "—"
HINT_SEPARATOR = "   ·   "


class _Fonts(Protocol):
    @property
    def small(self) -> pygame.font.Font: ...
    @property
    def normal(self) -> pygame.font.Font: ...


@dataclass(frozen=True)
class HudStat:
    label: str
    value: str
    short_label: str = ""  # used when ``label`` does not fit its chip


@dataclass(frozen=True)
class HudData:
    title: str
    stats: Sequence[HudStat]
    hints: Sequence[str]


def format_time(ms: int) -> str:
    """``m:ss``, or ``h:mm:ss`` from one hour on; partial seconds are dropped."""
    seconds = max(0, ms) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def par_text(par: Par | None) -> str:
    """``"pushes/moves"`` of the par, or a dash when the level has none."""
    return NO_PAR if par is None else f"{par.pushes}/{par.moves}"


def hud_stats(*, moves: int, pushes: int, elapsed_ms: int | None, par: Par | None) -> list[HudStat]:
    """The counters shown in the HUD; ``elapsed_ms=None`` hides the timer (setting ``show_timer``)."""
    stats = [HudStat(t("Moves", "Pas"), str(moves)), HudStat(t("Pushes", "Poussées"), str(pushes))]
    if elapsed_ms is not None:
        stats.append(HudStat(t("Time", "Temps"), format_time(elapsed_ms)))
    stats.append(HudStat(t("Par pushes/moves", "Par poussées/pas"), par_text(par), short_label="Par"))
    return stats


# (action, label, needs a double press)
_HINTS: tuple[tuple[str, Callable[[], str], bool], ...] = (
    ("undo", lambda: t("undo", "annuler"), False),
    ("redo", lambda: t("redo", "rétablir"), False),
    ("restart", lambda: t("restart", "recommencer"), True),
    ("pause", lambda: t("pause", "pause"), False),
    ("hint", lambda: t("hint", "indice"), False),
)


def key_hints(bindings: Mapping[str, Sequence[str]]) -> list[str]:
    """``"<first key> <action>"`` for the game's commands; an action without any key is left out."""
    hints = []
    for action, label, double in _HINTS:
        keys = bindings.get(action, ())
        if not keys:
            continue
        name = describe_binding(keys[0])
        if double:
            name += " ×2"
        hints.append(f"{name} {label()}")
    return hints


def fit_text(text: str, font: pygame.font.Font, width: int) -> str:
    """``text``, cut with an ellipsis when it is wider than ``width``."""
    if font.size(text)[0] <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # longest prefix that still fits with the ellipsis
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid].rstrip() + "…")[0] <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def _margin(screen: pygame.Rect) -> int:
    return max(6, min(screen.width, screen.height) // 60)


def draw_hud(surface: pygame.Surface, fonts: _Fonts, palette: UiPalette, data: HudData) -> pygame.Rect:
    """Draw the top band and the key reminders; return the area left for the board."""
    screen = surface.get_rect()
    margin = _margin(screen)
    small, normal = fonts.small, fonts.normal

    chip_h = small.get_linesize() + normal.get_linesize() + margin
    band_h = margin + normal.get_linesize() + margin + chip_h + margin
    band = pygame.Rect(0, 0, screen.width, band_h)
    pygame.draw.rect(surface, palette.panel, band)
    pygame.draw.line(surface, palette.accent, (0, band.bottom - 1), (band.right - 1, band.bottom - 1), 2)

    inner_w = screen.width - 2 * margin
    title = normal.render(fit_text(data.title, normal, inner_w), True, palette.text)
    surface.blit(title, (margin, margin))

    count = max(1, len(data.stats))
    gap = margin
    chip_w = (inner_w - gap * (count - 1)) // count
    top = margin + normal.get_linesize() + margin
    for i, stat in enumerate(data.stats):
        chip = pygame.Rect(margin + i * (chip_w + gap), top, chip_w, chip_h)
        pygame.draw.rect(surface, palette.muted, chip, width=1, border_radius=max(3, margin // 2))
        caption = stat.label.upper()
        if stat.short_label and small.size(caption)[0] > chip_w - margin:
            caption = stat.short_label.upper()
        label = small.render(fit_text(caption, small, chip_w - margin), True, palette.muted)
        surface.blit(label, label.get_rect(midtop=(chip.centerx, chip.top + margin // 2)))
        value = normal.render(fit_text(stat.value, normal, chip_w - margin), True, palette.accent)
        surface.blit(
            value, value.get_rect(midtop=(chip.centerx, chip.top + margin // 2 + small.get_linesize()))
        )

    hints = list(data.hints)
    line = HINT_SEPARATOR.join(hints)
    while hints and small.size(line)[0] > inner_w:
        hints.pop()
        line = HINT_SEPARATOR.join(hints)
    foot_h = small.get_linesize() + 2 * margin
    if line:
        footer = small.render(line, True, palette.muted)
        surface.blit(footer, footer.get_rect(midbottom=(screen.centerx, screen.bottom - margin)))
    return pygame.Rect(0, band.bottom, screen.width, max(1, screen.height - band.bottom - foot_h))


def draw_toast(
    surface: pygame.Surface, fonts: _Fonts, palette: UiPalette, area: pygame.Rect, text: str
) -> None:
    """A short message in a panel near the top of ``area`` (restart prompt, failed save…)."""
    font = fonts.normal
    margin = _margin(surface.get_rect())
    label = font.render(fit_text(text, font, max(1, area.width - 4 * margin)), True, palette.text)
    box = label.get_rect().inflate(2 * margin, margin + margin // 2)
    box.midtop = (area.centerx, area.top + margin)
    radius = max(3, margin // 2)
    pygame.draw.rect(surface, palette.panel, box, border_radius=radius)
    pygame.draw.rect(surface, palette.accent, box, width=2, border_radius=radius)
    surface.blit(label, label.get_rect(center=box.center))


def draw_overlay_panel(
    surface: pygame.Surface,
    palette: UiPalette,
    size: tuple[int, int],
    *,
    border: tuple[int, int, int] | None = None,
) -> pygame.Rect:
    """Dim the whole surface and draw a centred panel of ``size`` (clamped to the screen); return it."""
    screen = surface.get_rect()
    shade = pygame.Surface(screen.size, pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    surface.blit(shade, (0, 0))
    margin = _margin(screen)
    box = pygame.Rect(0, 0, min(size[0], screen.width - 2 * margin), min(size[1], screen.height - 2 * margin))
    box.center = screen.center
    radius = max(4, margin)
    pygame.draw.rect(surface, palette.panel, box, border_radius=radius)
    pygame.draw.rect(surface, border or palette.accent, box, width=2, border_radius=radius)
    return box


def draw_star(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    *,
    filled: bool,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    """A five-pointed star; an unfilled one is only outlined."""
    cx, cy = center
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        angle = math.pi / 2 + i * math.pi / 5
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    if filled:
        pygame.draw.polygon(surface, fill, points)
    pygame.draw.polygon(surface, fill if filled else outline, points, width=max(1, radius // 8))
