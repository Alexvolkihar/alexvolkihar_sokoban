"""Theme lookup by id.

The four themes of the spec come first (``kenney``, ``classic``, ``neon``, ``contrast``), then the palettes
of the Dobble 3D themes, in the order of :data:`palettes.PALETTES`. Themes are created once, lazily, the
first time the registry is used.
"""

from __future__ import annotations

from alexvolkihar_sokoban.ui.themes.base import Theme
from alexvolkihar_sokoban.ui.themes.classic import ClassicTheme
from alexvolkihar_sokoban.ui.themes.contrast import ContrastTheme
from alexvolkihar_sokoban.ui.themes.kenney import KenneyTheme
from alexvolkihar_sokoban.ui.themes.neon import NeonTheme
from alexvolkihar_sokoban.ui.themes.palettes import CLASSIC_PALETTE, PALETTES, PaletteTheme

DEFAULT_THEME_ID = "kenney"

THEME_IDS: tuple[str, ...] = ("kenney", "classic", "neon", "contrast") + tuple(
    p.id for p in PALETTES if p is not CLASSIC_PALETTE
)

_themes: dict[str, Theme] = {}


def _registry() -> dict[str, Theme]:
    if not _themes:
        built: list[Theme] = [KenneyTheme(), ClassicTheme(), NeonTheme(), ContrastTheme()]
        built += [PaletteTheme(p) for p in PALETTES if p is not CLASSIC_PALETTE]
        _themes.update((t.id, t) for t in built)
    return _themes


def available_themes() -> list[Theme]:
    """Every bundled theme, in :data:`THEME_IDS` order."""
    return list(_registry().values())


def get_theme(theme_id: str) -> Theme:
    """The theme with this id; an unknown id gives the default theme."""
    themes = _registry()
    return themes.get(theme_id, themes[DEFAULT_THEME_ID])
