"""Mood palettes adapted from the author's Dobble 3D project, drawn as procedural Sokoban tiles.

Only colours are reused, under neutral names that describe each palette's mood. Each palette keeps the
``ambiance`` tokens (sky gradient stops, felt, rim, card, card back, accents) and its particle
preset, which becomes a small motif on the floor tiles. :class:`PaletteTheme` assigns the board roles from
those tokens, choosing for goals, boxes and the player the colours that stand out the most, so every
palette stays legible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from alexvolkihar_sokoban.ui.themes._draw import (
    bevel,
    bricks,
    check_mark,
    contrast_ratio,
    disc,
    first_distinct,
    hex_rgb,
    ink_on,
    inset_rect,
    lighten,
    mix,
    new_tile,
    px,
    readable_on,
    ring,
    star,
)
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, TileKind, UiPalette

Motif = Literal["none", "candles", "snow", "halftone", "sparkles", "stars", "petals", "leaves", "bubbles"]


@dataclass(frozen=True)
class Palette:
    """The ambiance tokens of one palette (``#rrggbb`` strings)."""

    id: str
    name: str
    sky: tuple[str, ...]
    felt: str
    felt_2: str
    rim: str
    rim_2: str
    card: str
    card_edge: str
    back_a: str
    back_b: str
    accent: str
    accent_2: str
    brand: str
    motif: Motif
    dark: bool


def _p(
    id: str,
    name: str,
    sky: str,
    felt: tuple[str, str],
    rim: tuple[str, str],
    card: tuple[str, str],
    back: tuple[str, str],
    accent: tuple[str, str],
    brand: str,
    motif: Motif,
    dark: bool,
) -> Palette:
    return Palette(
        id=id,
        name=name,
        sky=tuple(sky.split()),
        felt=felt[0],
        felt_2=felt[1],
        rim=rim[0],
        rim_2=rim[1],
        card=card[0],
        card_edge=card[1],
        back_a=back[0],
        back_b=back[1],
        accent=accent[0],
        accent_2=accent[1],
        brand=brand,
        motif=motif,
        dark=dark,
    )


# fmt: off
CLASSIC_PALETTE = _p(
    "classic", "Classic", "#8fc3d4 #bcdcd6 #f0e4c8 #f2cfa2", ("#357660", "#245644"), ("#9a6439", "#6e4226"),
    ("#fbf6ea", "#d6c39b"), ("#2f5a4b", "#284d40"), ("#24614f", "#e2862b"), "#1f4f41", "none", False,
)

PALETTES: tuple[Palette, ...] = (
    CLASSIC_PALETTE,
    _p("meadow", "Meadow", "#8fd6e8 #c4ecef #f6f1d9 #f2dfb4", ("#6cb45d", "#4f9442"),
       ("#b98552", "#87592f"), ("#fffbf0", "#dcc9a2"), ("#4fb7a8", "#3fa294"), ("#237a45", "#8a5a2b"),
       "#1f5a3a", "petals", False),
    _p("arcade", "Arcade", "#0b0420 #24093f #5a0f5e #b8136f", ("#2a1a5e", "#170e38"),
       ("#ffc81e", "#a8790a"), ("#f7f6fb", "#c9c4dc"), ("#ff2f92", "#c4126c"), ("#ffd23f", "#19e3ff"),
       "#ffd23f", "stars", True),
    _p("storybook", "Storybook", "#0b1340 #2a2470 #6b3f8f #c76b9a", ("#2f4fa8", "#1f3577"),
       ("#d4af37", "#8f7420"), ("#fbf7f0", "#d8c8a8"), ("#6a4fb3", "#5a41a0"), ("#f2c94c", "#ff8fc7"),
       "#fbe3a1", "sparkles", True),
    _p("frost-keep", "Frost Keep", "#9fb0bd #c7d1d8 #8e9aa3", ("#6b6f73", "#4c5054"),
       ("#2c2f33", "#17191b"), ("#efe7d6", "#b7aa8e"), ("#2a2c30", "#1f2124"), ("#7d1a1a", "#2a5878"),
       "#2a2c30", "snow", False),
    _p("candlelight", "Candlelight", "#0d1424 #1c1f3d #3a2a3f", ("#5a3820", "#3f2614"),
       ("#c9a227", "#7d6216"), ("#f3e6c4", "#b89a5c"), ("#6b1f2a", "#561821"), ("#c9a227", "#b33a3a"),
       "#e8c86a", "candles", True),
    _p("runestone", "Runestone", "#010a13 #0a1428 #0a323c", ("#1f6f78", "#12474f"),
       ("#c8aa6e", "#785a28"), ("#f5f1e6", "#c8aa6e"), ("#005a82", "#0a323c"), ("#c8aa6e", "#0ac8b9"),
       "#f0e6d2", "sparkles", True),
    _p("comic", "Comic", "#ffe36b #f6c531 #e9a21a", ("#1f2a44", "#141b2e"),
       ("#e23636", "#9b1515"), ("#fbf6ea", "#d6c39b"), ("#e23636", "#b81f1f"), ("#b3141b", "#1f2a44"),
       "#b3141b", "halftone", False),
    _p("autumn", "Autumn", "#f6b26b #f9d3a0 #fbe8c8 #e9a46a", ("#22324f", "#152238"),
       ("#a7b0ba", "#6c7682"), ("#fbf7ef", "#d6c4a0"), ("#f57c00", "#d96a00"), ("#b4400a", "#1f3a5f"),
       "#1e2a44", "leaves", False),
    _p("high-seas", "High Seas", "#7cc4f2 #b3def7 #e9f6f2 #3aa8c4 #1f7fa3", ("#c99c45", "#9c7428"),
       ("#c8202e", "#8f1420"), ("#fbf8f0", "#d7c7a3"), ("#2c2c33", "#1d1d22"), ("#0f5f8f", "#b3122b"),
       "#13294b", "bubbles", False),
    _p("afterglow", "Afterglow", "#0b0420 #24093f #5a0f5e #b8136f", ("#2a1a5e", "#170e38"),
       ("#f99e1a", "#a3600c"), ("#f7f6fb", "#c9c4dc"), ("#405275", "#2b3a57"), ("#f99e1a", "#19e3ff"),
       "#fff4e2", "stars", True),
    _p("picnic", "Picnic", "#5fb6f0 #a6dcf5 #c9ef9b #8fd16a", ("#69b84a", "#4f9a36"),
       ("#e3350d", "#9e2207"), ("#fbf6ea", "#d6c39b"), ("#e3350d", "#c72b08"), ("#1b5aa0", "#ffcb05"),
       "#1a5596", "none", False),
    _p("pixel", "Pixel", "#a9c41a #bccf3a #9bbc0f", ("#306230", "#0f380f"),
       ("#c4c0b8", "#8b8780"), ("#f6f4ea", "#b9b6a8"), ("#306230", "#0f380f"), ("#2b5a2b", "#9a2257"),
       "#0f380f", "none", False),
    _p("deep-space", "Deep Space", "#03040b #0b1026 #1b1533", ("#2b4a6b", "#172b42"),
       ("#9aa3ad", "#5d646d"), ("#f4f2ec", "#b9b4a8"), ("#e2722b", "#c55f1f"), ("#ffe81f", "#4cc3ff"),
       "#ffe81f", "stars", True),
    _p("ember", "Ember", "#140b26 #2a1745 #5e2346 #a8442f", ("#8a5a32", "#613d20"),
       ("#b3261e", "#6e1510"), ("#f8f4ec", "#cdbb98"), ("#d6241f", "#1f47b8"), ("#ffb020", "#5aa9ff"),
       "#ffcf6b", "candles", True),
    _p("brickyard", "Brickyard", "#8cb8ff #b5d2ff #e6f0ff #7cc95a #4c9f36", ("#43b047", "#2e8a33"),
       ("#c84c0c", "#8a3108"), ("#fffaf0", "#d9c49a"), ("#e52521", "#c41a17"), ("#b81a17", "#0b4fb3"),
       "#a8120f", "none", False),
    _p("woodland", "Woodland", "#9fd3e6 #cfe9e4 #efe9cc #9cc28a", ("#4c7d48", "#355a33"),
       ("#b58a2a", "#7a5b17"), ("#f8f4e8", "#cdbf9c"), ("#1e4f8f", "#173e72"), ("#0b6e78", "#7d5a0e"),
       "#1d3b2a", "leaves", False),
)
# fmt: on

# UI tokens adapted from the same project: ink, small text, paper, danger — light and dark variants.
_LIGHT_UI = {"text": "#2b2820", "muted": "#746a56", "panel": "#fbf6ea", "bad": "#a8371f", "good": "#24614f"}
_DARK_UI = {"text": "#f3ead3", "muted": "#ab9b7e", "panel": "#231c33", "bad": "#ff8a70", "good": "#7fd18b"}

_MOTIF_COLOURS: dict[str, RGB] = {
    "candles": (255, 190, 90),
    "snow": (255, 255, 255),
    "halftone": (0, 0, 0),
    "sparkles": (255, 240, 170),
    "stars": (255, 255, 230),
    "petals": (255, 170, 200),
    "leaves": (150, 210, 110),
    "bubbles": (200, 240, 255),
}


class PaletteTheme(CachedTheme):
    """A procedural theme drawn from one :class:`Palette`."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.source = palette
        self.id = palette.id
        self.name = palette.name

        ui = _DARK_UI if palette.dark else _LIGHT_UI
        text = hex_rgb(ui["text"])
        sky = [hex_rgb(c) for c in palette.sky]
        self.background = max(sky, key=lambda c: contrast_ratio(c, text))
        panel = hex_rgb(ui["panel"])
        self.palette = UiPalette(
            text=text,
            muted=hex_rgb(ui["muted"]),
            accent=readable_on(panel, hex_rgb(palette.accent), 3.0),
            panel=panel,
            good=hex_rgb(ui["good"]),
            bad=hex_rgb(ui["bad"]),
        )

        c = {name: hex_rgb(getattr(palette, name)) for name in _TOKENS}
        self.floor = c["felt"]
        self.floor_line = mix(c["felt"], c["felt_2"], 0.6)
        self.wall = c["rim"]
        self.wall_light = lighten(c["rim"], 0.28)
        self.wall_shadow = c["rim_2"]
        self.wall_mortar = mix(c["rim"], c["rim_2"], 0.75)
        # Board roles, in each palette's order of preference: the theme's own accents first, as long as
        # they stand out enough from what they are drawn over or next to.
        goal_options = [c[k] for k in ("accent", "accent_2", "brand", "card", "back_a", "card_edge")]
        self.goal = first_distinct(
            [g for g in goal_options if contrast_ratio(g, self.floor) >= 1.8] or goal_options,
            [self.floor],
            220,
        )
        self.box = first_distinct(
            [c[k] for k in ("back_a", "back_b", "accent_2", "accent", "brand", "card_edge", "rim_2")],
            [self.floor, self.wall, self.goal],
            170,
        )
        self.box_line = ink_on(self.box)
        self.done = self.goal
        self.done_line = ink_on(self.done)
        self.player = first_distinct(
            [c[k] for k in ("card", "accent_2", "accent", "back_a", "brand")],
            [self.floor, self.box],
            170,
        )
        self.player_line = ink_on(self.player)
        self.motif = palette.motif
        motif_colour = _MOTIF_COLOURS.get(palette.motif, self.floor)
        self.motif_colour = mix(self.floor, motif_colour, 0.45)

    # --- tiles -----------------------------------------------------------------------------------------

    def _draw(self, kind: TileKind, size: int) -> pygame.Surface:
        if kind is TileKind.OUTSIDE:
            return new_tile(size)
        if kind is TileKind.WALL:
            return self._wall(size)
        surface = self._floor(size)
        if kind is TileKind.GOAL:
            self._goal(surface, size, 0.28)
        elif kind is TileKind.PLAYER_ON_GOAL:
            self._goal(surface, size, 0.38)
        if kind is TileKind.BOX:
            self._crate(surface, size, self.box, self.box_line, done=False)
        elif kind is TileKind.BOX_ON_GOAL:
            self._crate(surface, size, self.done, self.done_line, done=True)
        elif kind in (TileKind.PLAYER, TileKind.PLAYER_ON_GOAL):
            self._pawn(surface, size)
        return surface

    def _floor(self, size: int) -> pygame.Surface:
        surface = new_tile(size, self.floor)
        if size >= 12:
            pygame.draw.rect(surface, self.floor_line, (0, 0, size, size), width=1)
        if size >= 20:
            self._motif(surface, size)
        return surface

    def _wall(self, size: int) -> pygame.Surface:
        surface = new_tile(size, self.wall)
        rect = surface.get_rect()
        if size >= 12:
            bricks(surface, rect, self.wall_mortar, rows=4 if size >= 32 else 3, width=px(size, 0.04))
        bevel(surface, rect, self.wall_light, self.wall_shadow, px(size, 0.07))
        return surface

    def _goal(self, surface: pygame.Surface, size: int, radius: float) -> None:
        ring(surface, mix(self.goal, ink_on(self.goal), 0.6), size, radius + 0.03, 0.15)
        ring(surface, self.goal, size, radius, 0.09)
        disc(surface, self.goal, size, 0.08)

    def _crate(self, surface: pygame.Surface, size: int, fill: RGB, line: RGB, *, done: bool) -> None:
        rect = inset_rect(size, 0.1)
        radius = px(size, 0.06)
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        border = px(size, 0.07)
        pygame.draw.rect(surface, mix(fill, line, 0.55), rect, width=border, border_radius=radius)
        inner = rect.inflate(-4 * border, -4 * border)
        if inner.width < 2:
            return
        if done:
            check_mark(surface, line, inner, px(size, 0.11))
        else:
            planks = mix(fill, line, 0.4)
            pygame.draw.line(surface, planks, inner.topleft, (inner.right - 1, inner.bottom - 1), border)
            pygame.draw.line(surface, planks, (inner.right - 1, inner.top), inner.bottomleft, border)
            pygame.draw.rect(
                surface,
                lighten(fill, 0.3),
                (rect.left + border, rect.top + border, rect.width - 2 * border, max(1, border // 2)),
            )

    def _pawn(self, surface: pygame.Surface, size: int) -> None:
        outline = px(size, 0.05)
        body = pygame.Rect(0, 0, round(size * 0.56), round(size * 0.4))
        body.midbottom = (size // 2, round(size * 0.88))
        head_center = (size // 2, round(size * 0.36))
        head_radius = px(size, 0.18)
        pygame.draw.ellipse(surface, self.player_line, body.inflate(2 * outline, 2 * outline))
        pygame.draw.circle(surface, self.player_line, head_center, head_radius + outline)
        pygame.draw.ellipse(surface, self.player, body)
        pygame.draw.circle(surface, self.player, head_center, head_radius)
        if size >= 16:
            eye = max(1, size // 24)
            for dx in (-1, 1):
                pos = (size // 2 + dx * round(size * 0.065), head_center[1])
                pygame.draw.circle(surface, self.player_line, pos, eye)

    def _motif(self, surface: pygame.Surface, size: int) -> None:
        colour = self.motif_colour
        spots = ((0.16, 0.16), (0.84, 0.84), (0.84, 0.16))
        r = size * 0.06
        for fx, fy in spots[: 2 if self.motif in ("petals", "leaves") else 3]:
            x, y = size * fx, size * fy
            if self.motif == "snow":
                pygame.draw.circle(surface, colour, (x, y), max(1, r * 0.7))
            elif self.motif == "halftone":
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        pygame.draw.circle(surface, colour, (x + dx * r, y + dy * r), max(1, r * 0.5))
            elif self.motif in ("sparkles", "stars"):
                star(surface, colour, (x, y), r * (1.3 if self.motif == "sparkles" else 0.9))
            elif self.motif == "candles":
                pygame.draw.ellipse(surface, colour, (x - r * 0.5, y - r, r, r * 2))
            elif self.motif in ("petals", "leaves"):
                pygame.draw.ellipse(surface, colour, (x - r * 1.3, y - r * 0.6, r * 2.6, r * 1.2))
            elif self.motif == "bubbles":
                pygame.draw.circle(surface, colour, (x, y), max(2, r), width=1)


_TOKENS = (
    "felt",
    "felt_2",
    "rim",
    "rim_2",
    "card",
    "card_edge",
    "back_a",
    "back_b",
    "accent",
    "accent_2",
    "brand",
)
