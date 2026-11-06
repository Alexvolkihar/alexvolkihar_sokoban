"""Small reusable UI pieces drawn with the theme palette."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.themes.base import UiPalette


@dataclass
class MenuItem:
    """A menu entry. A callable label is re-read on every draw, so it follows the current language."""

    label: str | Callable[[], str]
    on_select: Callable[[], None]
    enabled: bool = True

    @property
    def text(self) -> str:
        if callable(self.label):
            return self.label()
        return self.label


class MenuList:
    """Vertical menu: up/down move (wrapping, skipping disabled items), confirm selects, mouse works too."""

    def __init__(self, items: list[MenuItem]) -> None:
        self.items = items
        self.selected = next((i for i, item in enumerate(items) if item.enabled), 0)
        self.item_rects: list[pygame.Rect] = []  # screen rects of the items at the last draw

    def _move(self, delta: int) -> None:
        n = len(self.items)
        for k in range(1, n + 1):
            i = (self.selected + delta * k) % n
            if self.items[i].enabled:
                self.selected = i
                return

    def _activate(self, index: int) -> bool:
        if not (0 <= index < len(self.items)) or not self.items[index].enabled:
            return False
        self.selected = index
        self.items[index].on_select()
        return True

    def handle_action(self, action: Action) -> bool:
        """Apply ``action``; ``True`` when the menu used it."""
        if not self.items:
            return False
        if action is Action.UP:
            self._move(-1)
            return True
        if action is Action.DOWN:
            self._move(1)
            return True
        if action is Action.CONFIRM:
            return self._activate(self.selected)
        return False

    def _index_at(self, pos: tuple[int, int]) -> int | None:
        for i, rect in enumerate(self.item_rects):
            if rect.collidepoint(pos) and i < len(self.items) and self.items[i].enabled:
                return i
        return None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Mouse hover selects, left click activates; ``True`` when the menu used the event."""
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            return False
        index = self._index_at(event.pos)
        if index is None:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.selected = index
            return True
        if event.button != 1:
            return False
        return self._activate(index)

    def draw(
        self, surface: pygame.Surface, rect: pygame.Rect, font: pygame.font.Font, palette: UiPalette
    ) -> None:
        """Draw the items centred in ``rect``; the selected one on a highlighted bar."""
        self.item_rects = []
        if not self.items:
            return
        pad = max(4, font.get_height() // 3)
        row_h = min(font.get_height() + 2 * pad, max(1, rect.height // len(self.items)))
        widest = max(font.size(item.text)[0] for item in self.items)
        bar_w = min(rect.width, widest + 6 * pad)
        top = rect.top + (rect.height - row_h * len(self.items)) // 2
        for i, item in enumerate(self.items):
            bar = pygame.Rect(0, 0, bar_w, row_h)
            bar.midtop = (rect.centerx, top + i * row_h)
            self.item_rects.append(bar)
            colour = palette.text
            if not item.enabled:
                colour = palette.muted
            elif i == self.selected:
                colour = palette.accent
                pygame.draw.rect(surface, palette.panel, bar, border_radius=max(2, row_h // 4))
                pygame.draw.rect(surface, palette.accent, bar, width=2, border_radius=max(2, row_h // 4))
            label = font.render(item.text, True, colour)
            surface.blit(label, label.get_rect(center=bar.center))


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


def wrap_text(text: str, font: pygame.font.Font, width: int) -> list[str]:
    """Split ``text`` into lines no wider than ``width``; a word too long for one line is cut."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if font.size(candidate)[0] <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while font.size(current)[0] > width and len(current) > 1:
            lo, hi = 1, len(current) - 1  # longest prefix that fits, by bisection
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.size(current[:mid])[0] <= width:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(current[:lo])
            current = current[lo:]
    if current:
        lines.append(current)
    return lines


def draw_row_bar(surface: pygame.Surface, rect: pygame.Rect, palette: UiPalette) -> None:
    """The highlight behind the selected row."""
    radius = max(2, rect.height // 4)
    pygame.draw.rect(surface, palette.panel, rect, border_radius=radius)
    pygame.draw.rect(surface, palette.accent, rect, width=2, border_radius=radius)


class ScrollList:
    """Selection and scrolling of a list of ``count`` rows; the scene draws the rows itself.

    ``layout`` places the rows that fit in a rect, scrolled so the selected row is visible, and keeps their
    rects for the mouse (``item_rects`` = ``[(index, rect), ...]``).
    """

    def __init__(self, count: int, selected: int = 0) -> None:
        self.count = count
        self.selected = min(max(0, selected), max(0, count - 1))
        self.first = 0
        self.item_rects: list[tuple[int, pygame.Rect]] = []

    def move(self, delta: int, *, wrap: bool = True) -> None:
        if self.count == 0:
            return
        if wrap:
            self.selected = (self.selected + delta) % self.count
        else:
            self.selected = min(max(0, self.selected + delta), self.count - 1)

    def layout(self, rect: pygame.Rect, row_h: int) -> list[tuple[int, pygame.Rect]]:
        row_h = max(1, row_h)
        shown = min(self.count, max(1, rect.height // row_h))
        if self.selected < self.first:
            self.first = self.selected
        elif self.selected >= self.first + shown:
            self.first = self.selected - shown + 1
        self.first = max(0, min(self.first, self.count - shown))
        self.item_rects = [
            (index, pygame.Rect(rect.x, rect.y + k * row_h, rect.width, row_h))
            for k, index in enumerate(range(self.first, self.first + shown))
        ]
        return self.item_rects

    @property
    def more_above(self) -> bool:
        return self.first > 0

    @property
    def more_below(self) -> bool:
        return self.first + len(self.item_rects) < self.count

    def index_at(self, pos: tuple[int, int]) -> int | None:
        for index, rect in self.item_rects:
            if rect.collidepoint(pos):
                return index
        return None

    def handle_event(self, event: pygame.event.Event) -> int | None:
        """Hover selects, the wheel moves the selection; returns the index of a left-clicked row."""
        if event.type == pygame.MOUSEWHEEL:
            self.move(-event.y, wrap=False)
            return None
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            return None
        index = self.index_at(event.pos)
        if index is None:
            return None
        self.selected = index
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return index
        return None

    def draw_arrows(self, surface: pygame.Surface, rect: pygame.Rect, colour: tuple[int, int, int]) -> None:
        """Small triangles above and below ``rect`` when rows are hidden on that side."""
        half = 6
        x = rect.centerx
        if self.more_above:
            y = rect.top - 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y - half)])
        if self.more_below:
            y = rect.bottom + 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y + half)])
