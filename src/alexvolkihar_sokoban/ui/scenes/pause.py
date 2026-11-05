"""Pause overlay (spec 7.9): Resume, Restart, Watch solution, Level select, Main menu.

Pushed by the game scene with ``game=<GameScene>``; ``pause`` or ``back`` resumes.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.hud import draw_overlay_panel
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.game import GameScene, leave_game
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList


class PauseScene(Scene):
    is_overlay = True
    game: GameScene

    def on_enter(self, **params: object) -> None:
        game = params.get("game")
        if not isinstance(game, GameScene):
            raise TypeError("pause scene needs game: GameScene")
        self.game = game
        self.menu = MenuList(
            [
                MenuItem(lambda: t("Resume", "Reprendre"), self._resume),
                MenuItem(lambda: t("Restart", "Recommencer"), self._restart),
                MenuItem(lambda: t("Watch solution", "Voir la solution"), self._watch),
                MenuItem(lambda: t("Level select", "Choix du niveau"), self._level_select),
                MenuItem(lambda: t("Main menu", "Menu principal"), self._main_menu),
            ]
        )

    def _resume(self) -> None:
        self.app.pop()

    def _restart(self) -> None:
        self.app.pop()
        self.game.restart()

    def _watch(self) -> None:
        """Open the solver replay; it marks the run assisted through ``on_watch`` as soon as it opens."""
        game = self.game
        self.app.pop()
        self.app.push("replay", pack=game.pack, level_id=game.entry.id, on_watch=game.mark_assisted)

    def _level_select(self) -> None:
        leave_game(self.app, "level_select", pack_id=self.game.pack.id)

    def _main_menu(self) -> None:
        leave_game(self.app, "main_menu")

    def handle_action(self, action: Action) -> None:
        if action in (Action.PAUSE, Action.BACK):
            self._resume()
            return
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.menu.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        line = fonts.normal.get_linesize()
        width = max(fonts.normal.size(item.text)[0] for item in self.menu.items) + 6 * line
        width = max(width, fonts.title.size(_title())[0] + 2 * line)
        height = fonts.title.get_linesize() + len(self.menu.items) * line * 9 // 5 + line
        box = draw_overlay_panel(surface, palette, (width, height))
        title = fonts.title.render(_title(), True, palette.accent)
        title_rect = title.get_rect(midtop=(box.centerx, box.top + line // 2))
        surface.blit(title, title_rect)
        menu_rect = pygame.Rect(
            box.left, title_rect.bottom, box.width, box.bottom - title_rect.bottom - line // 2
        )
        self.menu.draw(surface, menu_rect, fonts.normal, palette)


def _title() -> str:
    return t("Paused", "Pause")


SCENE = PauseScene
