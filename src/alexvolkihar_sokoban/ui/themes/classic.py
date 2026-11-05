"""Classic theme: flat procedural tiles in the colours of the Dobble 3D "Classique" theme."""

from __future__ import annotations

from alexvolkihar_sokoban.ui.themes.palettes import CLASSIC_PALETTE, PaletteTheme


class ClassicTheme(PaletteTheme):
    def __init__(self) -> None:
        super().__init__(CLASSIC_PALETTE)
