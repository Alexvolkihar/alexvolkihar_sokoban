"""Stand-in for a scene that is not written yet: "coming soon", Back or Enter returns."""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene


class PlaceholderScene(Scene):
    def handle_action(self, action: Action) -> None:
        if action in (Action.BACK, Action.CONFIRM):
            self.app.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.app.pop()

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        surface.fill(self.app.theme.background)
        rect = surface.get_rect()
        title = fonts.title.render(t("Coming soon", "Bientôt disponible"), True, palette.accent)
        surface.blit(title, title.get_rect(center=(rect.centerx, rect.centery - title.get_height())))
        name = fonts.normal.render(self.name.replace("_", " "), True, palette.text)
        surface.blit(name, name.get_rect(center=rect.center))
        hint = fonts.small.render(t("Esc or Enter: back", "Échap ou Entrée : retour"), True, palette.muted)
        surface.blit(hint, hint.get_rect(midbottom=(rect.centerx, rect.bottom - hint.get_height())))


SCENE = PlaceholderScene
