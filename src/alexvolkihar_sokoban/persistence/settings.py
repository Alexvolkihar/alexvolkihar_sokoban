"""User settings (spec 9.3). Loading and saving the file is ``persistence.store``'s job."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast, get_args

Language = Literal["fr", "en"]
Animation = Literal["off", "normal", "fast"]

SETTINGS_FORMAT = "alexvolkihar-sokoban/settings"
SETTINGS_VERSION = 1

MIN_WINDOW = (640, 480)

ACTIONS: tuple[str, ...] = (
    "up",
    "down",
    "left",
    "right",
    "undo",
    "redo",
    "restart",
    "hint",
    "pause",
    "confirm",
    "back",
)

DEFAULT_KEYBINDINGS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "up": ("key:up", "scan:26"),
        "down": ("key:down", "scan:22"),
        "left": ("key:left", "scan:4"),
        "right": ("key:right", "scan:7"),
        "undo": ("key:u", "key:backspace", "ctrl+key:z"),
        "redo": ("key:y", "ctrl+key:y"),
        "restart": ("key:r",),
        "hint": ("key:h",),
        "pause": ("key:escape", "key:p"),
        "confirm": ("key:return", "key:space"),
        "back": ("key:escape",),
    }
)

# "[ctrl+]key:<pygame key name>" or "[ctrl+]scan:<SDL scancode>" (spec 7.9).
BINDING_PATTERN = re.compile(r"(ctrl\+)?(key:\S.*|scan:\d+)")


def _default_keybindings() -> dict[str, tuple[str, ...]]:
    return dict(DEFAULT_KEYBINDINGS)


@dataclass
class Settings:
    language: Language = "en"
    theme: str = "kenney"
    fullscreen: bool = False
    window: tuple[int, int] = (1024, 768)
    animation: Animation = "normal"
    show_timer: bool = True
    keybindings: dict[str, tuple[str, ...]] = field(default_factory=_default_keybindings)

    def to_dict(self) -> dict[str, object]:
        """JSON-ready fields, without ``format``/``version`` (the store adds them)."""
        return {
            "language": self.language,
            "theme": self.theme,
            "fullscreen": self.fullscreen,
            "window": [self.window[0], self.window[1]],
            "animation": self.animation,
            "show_timer": self.show_timer,
            "keybindings": {action: list(keys) for action, keys in self.keybindings.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Settings:
        """Tolerant reader: unknown keys are ignored and each invalid field falls back to its default."""
        s = cls()
        language = data.get("language")
        if language in get_args(Language):
            s.language = cast(Language, language)
        theme = data.get("theme")
        if isinstance(theme, str) and theme:
            s.theme = theme
        fullscreen = data.get("fullscreen")
        if isinstance(fullscreen, bool):
            s.fullscreen = fullscreen
        window = _window(data.get("window"))
        if window is not None:
            s.window = window
        animation = data.get("animation")
        if animation in get_args(Animation):
            s.animation = cast(Animation, animation)
        show_timer = data.get("show_timer")
        if isinstance(show_timer, bool):
            s.show_timer = show_timer
        bindings = data.get("keybindings")
        if isinstance(bindings, Mapping):
            for action in ACTIONS:
                keys = _bindings(bindings.get(action))
                if keys is not None:
                    s.keybindings[action] = keys
        return s


def _window(value: object) -> tuple[int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    w, h = value
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (w, h)):
        return None
    if w < MIN_WINDOW[0] or h < MIN_WINDOW[1]:
        return None
    return (w, h)


def _bindings(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list | tuple) or not value:
        return None
    if not all(isinstance(v, str) and BINDING_PATTERN.fullmatch(v) for v in value):
        return None
    return tuple(cast(list[str], list(value)))


def default_language(locale_name: str | None) -> Language:
    """French when the system locale starts with ``fr``, English otherwise."""
    if locale_name and locale_name.lower().startswith("fr"):
        return "fr"
    return "en"
