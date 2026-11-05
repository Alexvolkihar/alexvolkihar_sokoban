"""Game scene, basic version: move, undo/redo, restart, back; on a win it returns to the previous scene.

Plan Task 13 owns this module and adds the HUD, pause, victory, saves and the rest.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.core.state import GameState
from alexvolkihar_sokoban.ui.board_renderer import BoardLayout, BoardRenderer
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene

_MOVES = {
    Action.UP: Direction.UP,
    Action.DOWN: Direction.DOWN,
    Action.LEFT: Direction.LEFT,
    Action.RIGHT: Direction.RIGHT,
}


class GameScene(Scene):
    pack: Pack
    entry: LevelEntry
    state: GameState

    def on_enter(self, **params: object) -> None:
        pack = params["pack"]
        level_id = params["level_id"]
        if not isinstance(pack, Pack) or not isinstance(level_id, str):
            raise TypeError("game scene needs pack: Pack and level_id: str")
        self.pack = pack
        self.entry = pack.entry(level_id)
        self.state = GameState(self.entry.level)
        self.renderer = BoardRenderer(self.app.theme)
        self.board_layout: BoardLayout | None = None

    def handle_action(self, action: Action) -> None:
        direction = _MOVES.get(action)
        if direction is not None:
            self.state.move(direction)
            if self.state.is_solved:
                self.app.pop()
        elif action is Action.UNDO:
            self.state.undo()
        elif action is Action.REDO:
            self.state.redo()
        elif action is Action.RESTART:
            self.state.restart()
        elif action is Action.BACK:
            self.app.pop()

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        palette = theme.palette
        font = self.app.fonts.normal
        surface.fill(theme.background)
        rect = surface.get_rect()
        margin = 8
        hud_h = font.get_height() + 2 * margin
        title = font.render(f"{self.pack.title} — {self.entry.title}", True, palette.text)
        surface.blit(title, (margin, margin))
        moves, pushes = self.state.moves, self.state.pushes
        text = t(f"Moves {moves}  Pushes {pushes}", f"Pas {moves}  Poussées {pushes}")
        counts = font.render(text, True, palette.accent)
        surface.blit(counts, counts.get_rect(topright=(rect.right - margin, margin)))
        self.renderer.theme = theme
        area = pygame.Rect(margin, hud_h, rect.width - 2 * margin, rect.height - hud_h - margin)
        self.board_layout = self.renderer.draw(
            surface, self.state.level, self.state.player, self.state.boxes, area
        )


SCENE = GameScene
