"""Key rebinding (spec 7.9): one row per action, then "Reset all" and "Back" (row id ``close``).

``confirm`` (or a click) on an action waits for the next key, which becomes that action's only binding;
Escape cancels the wait, so Escape itself cannot be captured. While waiting, actions are ignored and the key
is read from the raw event. ``Delete`` restores the selected action's default keys.

A key already used by another movement action is swapped: that action gets this action's previous keys in
place of it, so no key is lost and no two directions share one. A clash with any other action only warns
(Escape is shared by pause and back on purpose).
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from alexvolkihar_sokoban.persistence.settings import ACTIONS, DEFAULT_KEYBINDINGS
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action, InputMapper, describe_binding
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.themes import ScrollList, draw_row_bar, fit_text

MOVEMENT = ("up", "down", "left", "right")
RESET_ALL = "reset_all"
CLOSE = "close"

_LABELS: dict[str, Callable[[], str]] = {
    "up": lambda: t("Up", "Haut"),
    "down": lambda: t("Down", "Bas"),
    "left": lambda: t("Left", "Gauche"),
    "right": lambda: t("Right", "Droite"),
    "undo": lambda: t("Undo", "Annuler"),
    "redo": lambda: t("Redo", "Rétablir"),
    "restart": lambda: t("Restart", "Recommencer"),
    "hint": lambda: t("Hint", "Indice"),
    "pause": lambda: t("Pause", "Pause"),
    "confirm": lambda: t("Confirm", "Valider"),
    "back": lambda: t("Back (menus)", "Retour (menus)"),
}


def action_label(action: str) -> str:
    label = _LABELS.get(action)
    return label() if label is not None else action


class KeybindingsScene(Scene):
    rows: list[str]
    scroll: ScrollList
    list_rect: pygame.Rect
    capturing: str | None
    message: str

    def on_enter(self, **params: object) -> None:
        self.rows = [*ACTIONS, RESET_ALL, CLOSE]
        self.scroll = ScrollList(len(self.rows))
        self.list_rect = pygame.Rect(0, 0, 0, 0)
        self.capturing = None
        self.message = ""
        self._skip_event = False
        self._held_key: int | None = None  # the key that started the capture, ignored until released

    def row_text(self, row: str) -> tuple[str, str]:
        """``(label, keys)`` of a row; ``row`` is an action name, ``"reset_all"`` or ``"close"``."""
        if row == RESET_ALL:
            return t("Reset all", "Tout réinitialiser"), ""
        if row == CLOSE:
            return t("Back", "Retour"), ""
        bindings = self.app.settings.keybindings.get(row, ())
        return action_label(row), ", ".join(describe_binding(b) for b in bindings)

    def _activate(self, index: int) -> None:
        row = self.rows[index]
        if row == CLOSE:
            self.app.pop()
        elif row == RESET_ALL:
            self.app.settings.keybindings = dict(DEFAULT_KEYBINDINGS)
            self.message = t("Every key is back to its default.", "Toutes les touches sont par défaut.")
            self._apply()
        else:
            self.capturing = row
            self.message = ""

    # -- input -------------------------------------------------------------------------------------------

    def handle_action(self, action: Action) -> None:
        if self.capturing is not None:
            return
        if action is Action.UP:
            self.scroll.move(-1)
        elif action is Action.DOWN:
            self.scroll.move(1)
        elif action is Action.CONFIRM:
            self._activate(self.scroll.selected)
            self._skip_event = self.capturing is not None
        elif action is Action.BACK:
            self.app.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._skip_event:  # the key press that started the capture
            self._skip_event = False
            self._held_key = getattr(event, "key", None)
            return
        if self.capturing is not None:
            self._capture(event)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE:
            row = self.rows[self.scroll.selected]
            if row in ACTIONS:
                self.app.settings.keybindings[row] = DEFAULT_KEYBINDINGS[row]
                self.message = t(
                    f"Default keys restored for {action_label(row)}.",
                    f"Touches par défaut rétablies pour {action_label(row)}.",
                )
                self._apply()
            return
        index = self.scroll.handle_event(event)
        if index is not None:
            self._activate(index)

    def _capture(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP and event.key == self._held_key:
            self._held_key = None
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.capturing = None
            return
        if event.key == self._held_key:  # key repeat of the key that started the capture
            return
        binding = self.app.input.binding_from_event(event)
        if binding is None:  # a lone modifier: wait for the real key
            return
        action = self.capturing
        assert action is not None
        self.capturing = None
        self._held_key = None
        self._bind(action, binding, event)

    def _bind(self, action: str, binding: str, event: pygame.event.Event) -> None:
        bindings = self.app.settings.keybindings
        previous = bindings.get(action, DEFAULT_KEYBINDINGS[action])
        others = [a.value for a in self.app.input.actions_for(event) if a.value != action]
        key = describe_binding(binding)
        swapped: list[str] = []
        shared: list[str] = []
        for other in others:
            if action in MOVEMENT and other in MOVEMENT:
                bindings[other] = _swap_in(bindings[other], event, previous) or DEFAULT_KEYBINDINGS[other]
                swapped.append(action_label(other))
            else:
                shared.append(action_label(other))
        bindings[action] = (binding,)
        if swapped:
            names = ", ".join(swapped)
            self.message = t(f"{key} was used by {names}: swapped.", f"{key} servait à {names} : échangées.")
        elif shared:
            names = ", ".join(shared)
            self.message = t(f"{key} is also used by {names}.", f"{key} sert aussi à {names}.")
        else:
            self.message = ""
        self._apply()

    def _apply(self) -> None:
        self.app.input.set_bindings(self.app.settings.keybindings)
        if self.app.context is not None:
            self.app.context.save_settings()

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        surface.fill(self.app.theme.background)
        screen = surface.get_rect()
        margin = max(12, screen.height // 40)

        title = fonts.title.render(t("Key bindings", "Touches"), True, palette.accent)
        title_rect = title.get_rect(midtop=(screen.centerx, margin))
        surface.blit(title, title_rect)
        hint = fonts.small.render(
            t(
                "Enter: change · Delete: default keys · Esc: back",
                "Entrée : changer · Suppr : touches par défaut · Échap : retour",
            ),
            True,
            palette.muted,
        )
        hint_rect = hint.get_rect(midbottom=(screen.centerx, screen.bottom - margin))
        surface.blit(hint, hint_rect)
        message_h = fonts.small.get_height()
        if self.message:
            text = fit_text(fonts.small, self.message, screen.width - 2 * margin)
            msg = fonts.small.render(text, True, palette.bad)
            surface.blit(msg, msg.get_rect(midbottom=(screen.centerx, hint_rect.top - margin // 2)))

        width = min(screen.width - 2 * margin, 760)
        arrow_room = 12  # the scroll arrows sit just outside the list
        top = title_rect.bottom + margin // 2 + arrow_room
        bottom = hint_rect.top - message_h - margin // 2 - arrow_room
        self.list_rect = pygame.Rect(screen.centerx - width // 2, top, width, bottom - top)
        self._draw_rows(surface)

    def _draw_rows(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        font = self.app.fonts.normal
        row_h = font.get_height() + 10
        for index, rect in self.scroll.layout(self.list_rect, row_h):
            row = self.rows[index]
            bar = rect.inflate(0, -4)
            selected = index == self.scroll.selected
            if selected:
                draw_row_bar(surface, bar, palette)
            label, keys = self.row_text(row)
            colour = palette.accent if selected else palette.text
            keys_colour = palette.text
            if self.capturing is not None and selected:
                keys = t("Press a key… (Esc: cancel)", "Appuyez sur une touche… (Échap : annuler)")
                keys_colour = palette.accent
            pad = 12
            label_w = bar.width * 2 // 5
            text = font.render(fit_text(font, label, label_w - pad), True, colour)
            surface.blit(text, text.get_rect(midleft=(bar.left + pad, bar.centery)))
            if keys:
                small = self.app.fonts.small
                keys_text = small.render(fit_text(small, keys, bar.width - label_w - pad), True, keys_colour)
                surface.blit(keys_text, keys_text.get_rect(midleft=(bar.left + label_w, bar.centery)))
        self.scroll.draw_arrows(surface, self.list_rect, palette.muted)


def _swap_in(
    bindings: tuple[str, ...], event: pygame.event.Event, replacement: tuple[str, ...]
) -> tuple[str, ...]:
    """``bindings`` with each binding that ``event`` triggers replaced by ``replacement`` (no duplicates)."""
    out: list[str] = []
    for binding in bindings:
        if InputMapper({"up": (binding,)}).actions_for(event):
            out.extend(r for r in replacement if r not in out and r not in bindings)
        elif binding not in out:
            out.append(binding)
    return tuple(out)


SCENE = KeybindingsScene
