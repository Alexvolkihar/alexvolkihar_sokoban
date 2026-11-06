"""Keyboard bindings → actions (spec 7.9).

A binding is ``["ctrl+"] ("key:" <pygame key name> | "scan:" <SDL scancode>)``. ``key:`` follows the
keyboard layout, ``scan:`` the physical position (WASD bound by scancode is ZQSD on AZERTY). A binding with
``ctrl+`` fires only while Ctrl is held, one without it only while Ctrl is not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import pygame

from alexvolkihar_sokoban.persistence.settings import BINDING_PATTERN
from alexvolkihar_sokoban.ui.i18n import get_language


class Action(StrEnum):
    """One member per ``persistence.settings.ACTIONS`` value, in the same order."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UNDO = "undo"
    REDO = "redo"
    RESTART = "restart"
    HINT = "hint"
    PAUSE = "pause"
    CONFIRM = "confirm"
    BACK = "back"


# US-layout names of the SDL scancodes worth naming (letters, digits and the usual named keys).
_SCAN_NAMES: dict[int, str] = {
    **{4 + i: chr(ord("A") + i) for i in range(26)},
    **{30 + i: str((i + 1) % 10) for i in range(10)},
    40: "Return",
    41: "Escape",
    42: "Backspace",
    43: "Tab",
    44: "Space",
    79: "Right",
    80: "Left",
    81: "Down",
    82: "Up",
}

# French names of the keys the game binds by default (and Delete, used by the key bindings scene); other
# keys keep pygame's English name.
_FRENCH_KEY_NAMES = {
    "Return": "Entrée",
    "Escape": "Échap",
    "Backspace": "Retour arrière",
    "Space": "Espace",
    "Delete": "Suppr",
    "Right": "Droite",
    "Left": "Gauche",
    "Down": "Bas",
    "Up": "Haut",
}

_MODIFIER_KEYS = frozenset(
    {
        pygame.K_LCTRL,
        pygame.K_RCTRL,
        pygame.K_LSHIFT,
        pygame.K_RSHIFT,
        pygame.K_LALT,
        pygame.K_RALT,
        pygame.K_LMETA,
        pygame.K_RMETA,
        pygame.K_LGUI,
        pygame.K_RGUI,
        pygame.K_CAPSLOCK,
        pygame.K_NUMLOCK,
        pygame.K_MODE,
    }
)


@dataclass(frozen=True)
class _Binding:
    ctrl: bool
    scan: bool  # True: ``code`` is a scancode, False: a pygame key code
    code: int


def _parse(binding: str) -> _Binding | None:
    """The parsed binding, or ``None`` when it is malformed or names an unknown key."""
    if not BINDING_PATTERN.fullmatch(binding):
        return None
    ctrl = binding.startswith("ctrl+")
    body = binding.removeprefix("ctrl+")
    kind, _, value = body.partition(":")
    if kind == "scan":
        return _Binding(ctrl, True, int(value))
    try:
        code = pygame.key.key_code(value)
    except ValueError:
        return None
    return _Binding(ctrl, False, code)


def _ctrl_held(event: pygame.event.Event) -> bool:
    return bool(getattr(event, "mod", 0) & pygame.KMOD_CTRL)


class InputMapper:
    def __init__(self, bindings: Mapping[str, Sequence[str]]) -> None:
        self._bindings: dict[Action, list[_Binding]] = {}
        self.set_bindings(bindings)

    def set_bindings(self, bindings: Mapping[str, Sequence[str]]) -> None:
        """Replace every binding. Unknown actions and malformed or unknown keys are ignored."""
        parsed: dict[Action, list[_Binding]] = {}
        for action in Action:
            found = (_parse(b) for b in bindings.get(action.value, ()))
            parsed[action] = [b for b in found if b is not None]
        self._bindings = parsed

    def actions_for(self, event: pygame.event.Event) -> list[Action]:
        """Actions a ``KEYDOWN`` event triggers, in ``ACTIONS`` order; empty for any other event."""
        if event.type != pygame.KEYDOWN:
            return []
        ctrl = _ctrl_held(event)
        key = getattr(event, "key", None)
        scancode = getattr(event, "scancode", None)
        return [
            action
            for action, bindings in self._bindings.items()
            if any(b.ctrl == ctrl and b.code == (scancode if b.scan else key) for b in bindings)
        ]

    def binding_from_event(self, event: pygame.event.Event) -> str | None:
        """The binding string for a key press (to rebind an action), ``None`` for a lone modifier key."""
        if event.type != pygame.KEYDOWN or event.key in _MODIFIER_KEYS:
            return None
        prefix = "ctrl+" if _ctrl_held(event) else ""
        name = pygame.key.name(event.key) if event.key != pygame.K_UNKNOWN else ""
        if name and _parse("key:" + name) == _Binding(False, False, event.key):
            return f"{prefix}key:{name}"
        return f"{prefix}scan:{event.scancode}"


def describe_binding(binding: str) -> str:
    """Human-readable form of a binding: ``"scan:26"`` → ``"W"``, ``"ctrl+key:z"`` → ``"Ctrl+Z"``.

    Common key names follow the UI language (``"Escape"`` / ``"Échap"``).
    """
    prefix = "Ctrl+" if binding.startswith("ctrl+") else ""
    kind, _, value = binding.removeprefix("ctrl+").partition(":")
    if kind == "scan":
        code = int(value) if value.isdigit() else -1
        text = _SCAN_NAMES.get(code, f"Scan {value}")
    elif len(value) == 1:
        text = value.upper()
    else:
        text = value.title()
    if get_language() == "fr":
        text = _FRENCH_KEY_NAMES.get(text, text)
    return prefix + text
