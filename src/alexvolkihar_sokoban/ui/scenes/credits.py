"""Credits screen: the original LAMA group, the remake, graphics, level packs and libraries.

The level-pack credits come from each bundled pack's ``title``, ``author``, ``license`` and ``source``, so a
new pack shows up here without touching this file. The player's own packs (generated, custom) are left out.
Up/Down, the mouse wheel, Page Up/Down and Home/End scroll; ``back`` returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from alexvolkihar_sokoban.core.pack import Pack
from alexvolkihar_sokoban.ui.context import CUSTOM_ID, GENERATED_ID, load_bundled_packs
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.main_menu import _wrap

if TYPE_CHECKING:
    from alexvolkihar_sokoban.ui.app import App

LAMA_MEMBERS = "Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN, Martin PACARY"
ORIGINAL_URL = "https://github.com/Alexvolkihar/Sokoban-LAMA"
MAX_BODY_WIDTH = 900
WHEEL_LINES = 3


@dataclass(frozen=True)
class CreditSection:
    title: str
    lines: tuple[str, ...]


def credit_sections(packs: Sequence[Pack]) -> list[CreditSection]:
    """Every credit in the current language; one section per bundled level pack (player packs skipped)."""
    sections = [
        CreditSection(
            t("Original game", "Jeu original"),
            (
                t(
                    "Sokoban-LAMA (2022), a first-year (L1) university project by "
                    f"{LAMA_MEMBERS} (groupe LAMA).",
                    f"Sokoban-LAMA (2022), projet de licence 1 de {LAMA_MEMBERS} (groupe LAMA).",
                ),
                ORIGINAL_URL,
                t(
                    "The deadlock patterns of its solver were credited to KnightofLuna on GitHub.",
                    "Les motifs de blocage de son solveur étaient crédités à KnightofLuna sur GitHub.",
                ),
            ),
        ),
        CreditSection(
            t("This remake", "Ce remake"),
            (
                t(
                    "Alexvolkihar Sokoban, remake of Sokoban-LAMA by Alexis MABANZA.",
                    "Alexvolkihar Sokoban, remake de Sokoban-LAMA par Alexis MABANZA.",
                ),
            ),
        ),
        CreditSection(
            t("Graphics", "Graphismes"),
            (
                t(
                    "Kenney theme: the sprites of the original game, from the Sokoban pack by Kenney "
                    "(www.kenney.nl), CC0 1.0 (public domain).",
                    "Thème Kenney : les sprites du jeu original, issus du pack Sokoban de Kenney "
                    "(www.kenney.nl), CC0 1.0 (domaine public).",
                ),
                t(
                    "Colour palettes of the mood themes adapted from the author's Dobble 3D project.",
                    "Palettes de couleurs des thèmes d'ambiance adaptées du projet Dobble 3D de l'auteur.",
                ),
            ),
        ),
    ]
    for pack in packs:
        if pack.id in (GENERATED_ID, CUSTOM_ID):
            continue
        lines = []
        if pack.author:
            lines.append(t("By ", "Par ") + pack.author)
        if pack.license:
            lines.append(t("Licence: ", "Licence : ") + pack.license)
        if pack.source:
            lines.append(t("Source: ", "Source : ") + pack.source)
        sections.append(CreditSection(t("Levels: ", "Niveaux : ") + pack.title, tuple(lines)))
    sections.append(
        CreditSection(
            t("Software", "Logiciels"),
            (
                t(
                    "pygame-ce (pygame Community Edition), GNU LGPL 2.1 licence.",
                    "pygame-ce (pygame Community Edition), licence GNU LGPL 2.1.",
                ),
                t("platformdirs, MIT licence.", "platformdirs, licence MIT."),
                t("Written in Python.", "Écrit en Python."),
            ),
        )
    )
    return sections


class CreditsScene(Scene):
    """Scrolling credits. ``wrapped`` holds the laid-out ``(font role, text)`` lines of the last layout."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.sections: list[CreditSection] = []
        self.scroll = 0
        self.max_scroll = 0
        self.body_rect = pygame.Rect(0, 0, 0, 0)
        self.wrapped: list[tuple[str, str]] = []
        self._offsets: list[int] = []
        self._layout_key: tuple[int, int] | None = None

    def on_enter(self, **params: object) -> None:
        context = self.app.context
        if context is not None:
            packs = context.all_packs()
        else:
            packs, _ = load_bundled_packs()
        self.sections = credit_sections(packs)
        self._layout_key = None

    def text_lines(self) -> list[str]:
        """Every section title and credit line, unwrapped."""
        return [text for s in self.sections for text in (s.title, *s.lines)]

    # -- input -----------------------------------------------------------------------------------------

    def handle_action(self, action: Action) -> None:
        if action is Action.BACK:
            self.app.pop()
        elif action is Action.UP:
            self._scroll_by(-self._step())
        elif action is Action.DOWN:
            self._scroll_by(self._step())

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * WHEEL_LINES * self._step())
        elif event.type == pygame.KEYDOWN:
            self._layout(self.app.screen.get_size())
            page = max(self._step(), self.body_rect.height - self._step())
            if event.key == pygame.K_PAGEDOWN:
                self._scroll_by(page)
            elif event.key == pygame.K_PAGEUP:
                self._scroll_by(-page)
            elif event.key == pygame.K_HOME:
                self.scroll = 0
            elif event.key == pygame.K_END:
                self.scroll = self.max_scroll

    def _step(self) -> int:
        return int(self.app.fonts.small.get_linesize())

    def _scroll_by(self, delta: int) -> None:
        self._layout(self.app.screen.get_size())
        self.scroll = min(max(0, self.scroll + delta), self.max_scroll)

    # -- layout and drawing ----------------------------------------------------------------------------

    def _frame(self, size: tuple[int, int]) -> tuple[int, pygame.Rect, pygame.Rect]:
        """(margin, title area, body area) for a window of ``size``."""
        fonts = self.app.fonts
        width, height = size
        margin = max(8, height // 40)
        title_rect = pygame.Rect(0, margin, width, fonts.title.get_height())
        hint_h = fonts.small.get_height()
        body_w = min(width - 4 * margin, MAX_BODY_WIDTH)
        top = title_rect.bottom + margin
        body = pygame.Rect((width - body_w) // 2, top, body_w, height - top - hint_h - 3 * margin)
        return margin, title_rect, body

    def _layout(self, size: tuple[int, int]) -> None:
        if self._layout_key == size:
            return
        fonts = self.app.fonts
        _, _, self.body_rect = self._frame(size)
        width = self.body_rect.width
        self.wrapped, self._offsets = [], []
        y = 0
        for index, section in enumerate(self.sections):
            if index:
                y += fonts.small.get_linesize()
            for line in _wrap(section.title, fonts.normal, width):
                self.wrapped.append(("normal", line))
                self._offsets.append(y)
                y += fonts.normal.get_linesize()
            for item, text in enumerate(section.lines):
                if item:
                    y += fonts.small.get_linesize() // 4  # a little air between two credits
                for line in _wrap(text, fonts.small, width):
                    self.wrapped.append(("small", line))
                    self._offsets.append(y)
                    y += fonts.small.get_linesize()
        self.max_scroll = max(0, y - self.body_rect.height)
        self.scroll = min(self.scroll, self.max_scroll)
        self._layout_key = size

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        surface.fill(theme.background)
        rect = surface.get_rect()
        self._layout(rect.size)
        margin, title_rect, body = self._frame(rect.size)

        title = fonts.title.render(t("Credits", "Crédits"), True, palette.accent)
        surface.blit(title, title.get_rect(midtop=title_rect.midtop))

        previous_clip = surface.get_clip()
        surface.set_clip(body)
        for (role, line), offset in zip(self.wrapped, self._offsets, strict=True):
            y = body.top + offset - self.scroll
            font = fonts.normal if role == "normal" else fonts.small
            if y + font.get_linesize() < body.top or y > body.bottom:
                continue
            colour = palette.accent if role == "normal" else palette.text
            surface.blit(font.render(line, True, colour), (body.left, y))
        surface.set_clip(previous_clip)
        self._draw_arrows(surface, body, palette.muted)

        hint = fonts.small.render(
            t("Arrows, wheel: scroll · Esc: back", "Flèches, molette : défiler · Échap : retour"),
            True,
            palette.muted,
        )
        surface.blit(hint, hint.get_rect(midbottom=(rect.centerx, rect.bottom - margin)))

    def _draw_arrows(self, surface: pygame.Surface, body: pygame.Rect, colour: tuple[int, int, int]) -> None:
        """Small triangles above and below the text when it is scrolled or continues further down."""
        half = 6
        x = body.centerx
        if self.scroll > 0:
            y = body.top - 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y - half)])
        if self.scroll < self.max_scroll:
            y = body.bottom + 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y + half)])


SCENE = CreditsScene
