"""Settings (spec 7.9): language, animation, timer, fullscreen, key bindings, reset progress.

Every change applies at once and is saved. Left/Right change a value backwards/forwards, confirm moves it
forwards. Reset progress asks for a second confirm; moving away or ``back`` cancels it.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from alexvolkihar_sokoban.persistence.settings import Animation, Language
from alexvolkihar_sokoban.ui.i18n import set_language, t
from alexvolkihar_sokoban.ui.input import Action, describe_binding
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList

LANGUAGES: tuple[Language, ...] = ("en", "fr")
ANIMATIONS: tuple[Animation, ...] = ("off", "normal", "fast")

_LANGUAGE_NAMES = {"en": "English", "fr": "Français"}
_ANIMATION_NAMES: dict[str, Callable[[], str]] = {
    "off": lambda: t("Off", "Désactivée"),
    "normal": lambda: t("Normal", "Normale"),
    "fast": lambda: t("Fast", "Rapide"),
}

LANGUAGE, ANIMATION, TIMER, FULLSCREEN, KEYS, RESET, BACK = range(7)


def _on_off(value: bool) -> str:
    if value:
        return t("On", "Oui")
    return t("Off", "Non")


class SettingsScene(Scene):
    menu: MenuList
    reset_armed: bool
    status: str

    def on_enter(self, **params: object) -> None:
        self.reset_armed = False
        self.status = ""
        settings = self.app.settings
        self.menu = MenuList(
            [
                MenuItem(
                    lambda: t(
                        f"Language: {_LANGUAGE_NAMES[settings.language]}",
                        f"Langue : {_LANGUAGE_NAMES[settings.language]}",
                    ),
                    lambda: self._cycle_language(1),
                ),
                MenuItem(
                    lambda: t(
                        f"Animation: {_ANIMATION_NAMES[settings.animation]()}",
                        f"Animation : {_ANIMATION_NAMES[settings.animation]()}",
                    ),
                    lambda: self._cycle_animation(1),
                ),
                MenuItem(
                    lambda: t(
                        f"Show timer: {_on_off(settings.show_timer)}",
                        f"Afficher le chrono : {_on_off(settings.show_timer)}",
                    ),
                    self._toggle_timer,
                ),
                MenuItem(
                    lambda: t(
                        f"Fullscreen: {_on_off(settings.fullscreen)}",
                        f"Plein écran : {_on_off(settings.fullscreen)}",
                    ),
                    self._toggle_fullscreen,
                ),
                MenuItem(lambda: t("Key bindings…", "Touches…"), self._open_keybindings),
                MenuItem(self._reset_label, self._reset_progress, enabled=self.app.context is not None),
                MenuItem(lambda: t("Back", "Retour"), self.app.pop),
            ]
        )

    # -- changes -----------------------------------------------------------------------------------------

    def _save(self) -> None:
        self.status = ""
        if self.app.context is not None:
            self.app.context.save_settings()

    def _cycle_language(self, step: int) -> None:
        settings = self.app.settings
        settings.language = LANGUAGES[(LANGUAGES.index(settings.language) + step) % len(LANGUAGES)]
        set_language(settings.language)
        self._save()

    def _cycle_animation(self, step: int) -> None:
        settings = self.app.settings
        settings.animation = ANIMATIONS[(ANIMATIONS.index(settings.animation) + step) % len(ANIMATIONS)]
        self._save()

    def _toggle_timer(self) -> None:
        self.app.settings.show_timer = not self.app.settings.show_timer
        self._save()

    def _toggle_fullscreen(self) -> None:
        self.app.settings.fullscreen = not self.app.settings.fullscreen
        self.app.apply_display_settings()
        self._save()

    def _open_keybindings(self) -> None:
        self.app.push("keybindings")

    def _reset_label(self) -> str:
        if not self.reset_armed:
            return t("Reset progress", "Effacer la progression")
        confirm = self.app.settings.keybindings.get("confirm", ())
        key = describe_binding(confirm[0]) if confirm else "Enter"
        return t(f"Press {key} again to erase all progress", f"Appuyez encore sur {key} pour tout effacer")

    def _reset_progress(self) -> None:
        context = self.app.context
        if context is None:
            return
        if not self.reset_armed:
            self.reset_armed = True
            self.status = ""
            return
        self.reset_armed = False
        context.progress.reset()
        context.save_progress()
        self.status = t("Progress reset.", "Progression effacée.")

    # -- input -------------------------------------------------------------------------------------------

    def _step_value(self, step: int) -> bool:
        """Left/Right on a setting with a value: change it; ``True`` when used."""
        selected = self.menu.selected
        if selected == LANGUAGE:
            self._cycle_language(step)
        elif selected == ANIMATION:
            self._cycle_animation(step)
        elif selected == TIMER:
            self._toggle_timer()
        elif selected == FULLSCREEN:
            self._toggle_fullscreen()
        else:
            return False
        return True

    def handle_action(self, action: Action) -> None:
        if action is Action.BACK:
            if self.reset_armed:
                self.reset_armed = False
            else:
                self.app.pop()
            return
        if action is Action.LEFT or action is Action.RIGHT:
            self._step_value(-1 if action is Action.LEFT else 1)
            return
        if action is Action.UP or action is Action.DOWN:
            self.reset_armed = False
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.menu.handle_event(event)
        if self.menu.selected != RESET:
            self.reset_armed = False

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        surface.fill(self.app.theme.background)
        screen = surface.get_rect()
        margin = max(12, screen.height // 40)

        title = fonts.title.render(t("Settings", "Paramètres"), True, palette.accent)
        title_rect = title.get_rect(midtop=(screen.centerx, margin * 2))
        surface.blit(title, title_rect)
        hint = fonts.small.render(
            t(
                "Arrows: choose and change · Enter: confirm · Esc: back",
                "Flèches : choisir et modifier · Entrée : valider · Échap : retour",
            ),
            True,
            palette.muted,
        )
        hint_rect = hint.get_rect(midbottom=(screen.centerx, screen.bottom - margin))
        surface.blit(hint, hint_rect)

        status_h = fonts.small.get_height() + margin
        top = title_rect.bottom + margin
        menu_rect = pygame.Rect(screen.left, top, screen.width, hint_rect.top - status_h - margin - top)
        self.menu.draw(surface, menu_rect, fonts.normal, palette)
        if self.status:
            status = fonts.small.render(self.status, True, palette.good)
            surface.blit(status, status.get_rect(midtop=(screen.centerx, menu_rect.bottom + margin // 2)))


SCENE = SettingsScene
