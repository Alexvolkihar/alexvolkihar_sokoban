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
