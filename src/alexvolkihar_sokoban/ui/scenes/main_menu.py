"""Main menu (spec 7.9): Continue, Level select, Random level, Benchmark, Themes, Settings, Credits, Quit."""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList

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
    def on_enter(self, **params: object) -> None:
        app = self.app

        def opener(name: str) -> MenuItem:
            def open_scene() -> None:
                app.push(name)

            return MenuItem(_LABELS[name], open_scene)

        self.menu = MenuList(
            [
                # Plan Task 10 enables Continue (saved session or last played level) and sets its action.
                MenuItem(lambda: t("Continue", "Continuer"), lambda: None, enabled=False),
                opener("level_select"),
                opener("generate"),
                opener("benchmark"),
                opener("themes"),
                opener("settings"),
                opener("credits"),
                MenuItem(lambda: t("Quit", "Quitter"), app.quit),
            ]
        )

    def handle_action(self, action: Action) -> None:
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
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


_LABELS = {
    "level_select": lambda: t("Level select", "Choix du niveau"),
    "generate": lambda: t("Random level", "Niveau aléatoire"),
    "benchmark": lambda: t("Benchmark", "Benchmark"),
    "themes": lambda: t("Themes", "Thèmes"),
    "settings": lambda: t("Settings", "Paramètres"),
    "credits": lambda: t("Credits", "Crédits"),
}

SCENE = MainMenuScene
