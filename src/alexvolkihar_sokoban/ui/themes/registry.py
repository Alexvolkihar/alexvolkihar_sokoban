"""Theme lookup by id (stub; plan Task 8 registers the real themes)."""

from __future__ import annotations

from alexvolkihar_sokoban.ui.themes.base import Theme
from alexvolkihar_sokoban.ui.themes.fallback import FallbackTheme

DEFAULT_THEME_ID = "kenney"

_FALLBACK = FallbackTheme()


def available_themes() -> list[Theme]:
    return [_FALLBACK]


def get_theme(theme_id: str) -> Theme:
    """The theme with this id; an unknown id gives the default theme."""
    return _FALLBACK
