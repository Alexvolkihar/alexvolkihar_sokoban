"""Main menu (spec 7.9): Continue, Level select, Random level, Benchmark, Themes, Settings, Credits, Quit.

Continue resumes the saved session, or opens the last played level. Warnings collected by the app context
(damaged or too-new save files, broken level files, failed saves) are shown in a box over the menu until the
player dismisses them with confirm, back or a click.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList, wrap_text

TITLE = "Alexvolkihar Sokoban"

# Decorative strip under the subtitle: a box being pushed onto a goal.
_STRIP = (
    TileKind.WALL,
    TileKind.FLOOR,
    TileKind.PLAYER,
    TileKind.BOX,
    TileKind.FLOOR,
    TileKind.GOAL,
    TileKind.BOX_ON_GOAL,
    TileKind.WALL,
)


class MainMenuScene(Scene):
    messages: list[str]
    message_rect: pygame.Rect | None

    def on_enter(self, **params: object) -> None:
        app = self.app
        self.messages = []
        self.message_rect = None
        self._wrapped: tuple[tuple[tuple[str, ...], int], list[str]] = (((), 0), [])

        def opener(name: str) -> MenuItem:
            def open_scene() -> None:
                app.push(name)

            return MenuItem(_LABELS[name], open_scene)

        self.menu = MenuList(
            [
                MenuItem(lambda: t("Continue", "Continuer"), self._continue, enabled=False),
                opener("level_select"),
                opener("generate"),
                opener("benchmark"),
                opener("themes"),
                opener("settings"),
                opener("credits"),
                MenuItem(lambda: t("Quit", "Quitter"), app.quit),
            ]
        )
        self._refresh()
        if self.menu.items[0].enabled:
            self.menu.selected = 0

    def on_resume(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Enable Continue when there is something to continue; collect the context's new warnings."""
        context = self.app.context
        cont = self.menu.items[0]
        cont.enabled = context is not None and context.continue_target() is not None
        if not cont.enabled and self.menu.selected == 0:
            self.menu.selected = 1
        if context is not None:
            self.messages.extend(context.pop_warnings())

    def _continue(self) -> None:
        context = self.app.context
        target = context.continue_target() if context is not None else None
        if target is None:
            self._refresh()
            return
        self.app.push("game", pack=target.pack, level_id=target.level_id, resume=target.session)

    def handle_action(self, action: Action) -> None:
        if self.messages:
            if action in (Action.CONFIRM, Action.BACK):
                self.messages.clear()
            return
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.messages:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.messages.clear()
            return
        self.menu.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        surface.fill(theme.background)
        rect = surface.get_rect()
        margin = max(8, rect.height // 40)

        title = fonts.title.render(TITLE, True, palette.accent)
        title_rect = title.get_rect(midtop=(rect.centerx, margin * 2))
        surface.blit(title, title_rect)
        subtitle = fonts.normal.render(
            t("remake of Sokoban-LAMA", "remake de Sokoban-LAMA"), True, palette.muted
        )
        sub_rect = subtitle.get_rect(midtop=(rect.centerx, title_rect.bottom + margin // 2))
        surface.blit(subtitle, sub_rect)

        tile = max(12, min(40, rect.height // 20))
        strip_w = tile * len(_STRIP)
        x0 = rect.centerx - strip_w // 2
        y0 = sub_rect.bottom + margin
        for i, kind in enumerate(_STRIP):
            surface.blit(theme.tile(kind, tile), (x0 + i * tile, y0))

        hint = fonts.small.render(
            t("Arrows: choose · Enter: confirm", "Flèches : choisir · Entrée : valider"), True, palette.muted
        )
        hint_rect = hint.get_rect(midbottom=(rect.centerx, rect.bottom - margin))
        surface.blit(hint, hint_rect)

        top = y0 + tile + margin
        menu_rect = pygame.Rect(rect.left, top, rect.width, hint_rect.top - margin - top)
        self.menu.draw(surface, menu_rect, fonts.normal, palette)
        self.message_rect = None
        if self.messages:
            self._draw_messages(surface)

    def _draw_messages(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        screen = surface.get_rect()
        shade = pygame.Surface(screen.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))

        margin = max(12, screen.width // 40)
        pad = max(10, fonts.small.get_height() // 2)
        box_w = min(screen.width - 2 * margin, 900)
        text_w = box_w - 2 * pad
        line_h = fonts.small.get_linesize()
        title = fonts.normal.render(t("Warning", "Attention"), True, palette.bad)
        hint = fonts.small.render(t("Enter: OK", "Entrée : OK"), True, palette.muted)
        fixed_h = title.get_height() + hint.get_height() + 4 * pad
        max_lines = max(1, (screen.height - 2 * margin - fixed_h) // line_h)

        key = (tuple(self.messages), text_w)
        if self._wrapped[0] != key:
            wrapped = [line for m in self.messages for line in wrap_text(f"• {m}", fonts.small, text_w)]
            self._wrapped = (key, wrapped)
        lines = list(self._wrapped[1])
        if len(lines) > max_lines:
            hidden = len(lines) - (max_lines - 1)
            lines = lines[: max_lines - 1] + [
                t(f"… and {hidden} more lines", f"… et {hidden} lignes de plus")
            ]

        box = pygame.Rect(0, 0, box_w, fixed_h + line_h * len(lines))
        box.center = screen.center
        radius = max(4, pad // 2)
        pygame.draw.rect(surface, palette.panel, box, border_radius=radius)
        pygame.draw.rect(surface, palette.bad, box, width=2, border_radius=radius)
        y = box.top + pad
        surface.blit(title, title.get_rect(midtop=(box.centerx, y)))
        y += title.get_height() + pad
        for line in lines:
            surface.blit(fonts.small.render(line, True, palette.text), (box.left + pad, y))
            y += line_h
        surface.blit(hint, hint.get_rect(midbottom=(box.centerx, box.bottom - pad)))
        self.message_rect = box


_LABELS = {
    "level_select": lambda: t("Level select", "Choix du niveau"),
    "generate": lambda: t("Random level", "Niveau aléatoire"),
    "benchmark": lambda: t("Benchmark", "Benchmark"),
    "themes": lambda: t("Themes", "Thèmes"),
    "settings": lambda: t("Settings", "Paramètres"),
    "credits": lambda: t("Credits", "Crédits"),
}

SCENE = MainMenuScene
