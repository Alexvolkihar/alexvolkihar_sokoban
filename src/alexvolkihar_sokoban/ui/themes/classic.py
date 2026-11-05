"""Classic theme: flat procedural tiles, "classic" palette adapted from the author's Dobble 3D project."""

from __future__ import annotations

from alexvolkihar_sokoban.ui.themes.palettes import CLASSIC_PALETTE, PaletteTheme


class ClassicTheme(PaletteTheme):
    def __init__(self) -> None:
        super().__init__(CLASSIC_PALETTE)
