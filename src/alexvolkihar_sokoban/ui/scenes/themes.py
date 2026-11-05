"""Theme selector (spec 7.9): a scrolling list of every theme and a live preview of a sample board.

Moving the highlight (keys, mouse hover or wheel) only changes the preview; ``confirm`` or a click applies
the theme to the whole game and saves the settings. ``back`` returns.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.ui.board_renderer import BoardLayout, BoardRenderer
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.themes.base import Theme, TileKind, UiPalette
from alexvolkihar_sokoban.ui.themes.registry import available_themes

# 7×7 sample: one goal, one box, one box on a goal and the player (plus an inner wall).
SAMPLE_LEVEL = Level.from_rows(
    [
        "#######",
        "#     #",
        "# .$  #",
        "#  @ ##",
        "#  *  #",
        "#     #",
        "#######",
    ]
)

_FRENCH_NAMES = {
    "classic": "Classique",
    "neon": "Néon",
    "contrast": "Contraste élevé",
    "meadow": "Prairie",
    "storybook": "Livre de contes",
    "frost-keep": "Donjon de givre",
    "candlelight": "Chandelle",
    "runestone": "Pierre runique",
    "comic": "Bande dessinée",
    "autumn": "Automne",
    "high-seas": "Haute mer",
    "afterglow": "Crépuscule",
    "picnic": "Pique-nique",
    "deep-space": "Espace lointain",
    "ember": "Braise",
    "brickyard": "Briqueterie",
    "woodland": "Sous-bois",
}

_NOTES = {
    "kenney": lambda: t("Original sprites by Kenney (CC0)", "Sprites d'origine de Kenney (CC0)"),
    "contrast": lambda: t(
        "Colour-blind safe, shapes tell the states apart",
        "Adapté au daltonisme : les formes distinguent les états",
    ),
}

_SWATCH = (TileKind.WALL, TileKind.BOX, TileKind.GOAL)


def theme_label(theme: Theme) -> str:
    """The theme's name in the current language (themes carry an English ``name`` only)."""
    return t(theme.name, _FRENCH_NAMES.get(theme.id, theme.name))


class ScrollList:
    """Selection and scrolling of a list of ``count`` rows; the scene draws the rows itself.

    ``layout`` places the rows that fit in a rect, scrolled so the selected row is visible, and keeps their
    rects for the mouse (``item_rects`` = ``[(index, rect), ...]``).
    """

    def __init__(self, count: int, selected: int = 0) -> None:
        self.count = count
        self.selected = min(max(0, selected), max(0, count - 1))
        self.first = 0
        self.item_rects: list[tuple[int, pygame.Rect]] = []

    def move(self, delta: int, *, wrap: bool = True) -> None:
        if self.count == 0:
            return
        if wrap:
            self.selected = (self.selected + delta) % self.count
        else:
            self.selected = min(max(0, self.selected + delta), self.count - 1)

    def layout(self, rect: pygame.Rect, row_h: int) -> list[tuple[int, pygame.Rect]]:
        row_h = max(1, row_h)
        shown = min(self.count, max(1, rect.height // row_h))
        if self.selected < self.first:
            self.first = self.selected
        elif self.selected >= self.first + shown:
            self.first = self.selected - shown + 1
        self.first = max(0, min(self.first, self.count - shown))
        self.item_rects = [
            (index, pygame.Rect(rect.x, rect.y + k * row_h, rect.width, row_h))
            for k, index in enumerate(range(self.first, self.first + shown))
        ]
        return self.item_rects

    @property
    def more_above(self) -> bool:
        return self.first > 0

    @property
    def more_below(self) -> bool:
        return self.first + len(self.item_rects) < self.count

    def index_at(self, pos: tuple[int, int]) -> int | None:
        for index, rect in self.item_rects:
            if rect.collidepoint(pos):
                return index
        return None

    def handle_event(self, event: pygame.event.Event) -> int | None:
        """Hover selects, the wheel moves the selection; returns the index of a left-clicked row."""
        if event.type == pygame.MOUSEWHEEL:
            self.move(-event.y, wrap=False)
            return None
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            return None
        index = self.index_at(event.pos)
        if index is None:
            return None
        self.selected = index
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return index
        return None

    def draw_arrows(self, surface: pygame.Surface, rect: pygame.Rect, colour: tuple[int, int, int]) -> None:
        """Small triangles above and below ``rect`` when rows are hidden on that side."""
        half = 6
        x = rect.centerx
        if self.more_above:
            y = rect.top - 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y - half)])
        if self.more_below:
            y = rect.bottom + 4
            pygame.draw.polygon(surface, colour, [(x - half, y), (x + half, y), (x, y + half)])


def fit_text(font: pygame.font.Font, text: str, width: int) -> str:
    """``text`` cut with an ellipsis so that it is at most ``width`` pixels wide."""
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…"


def draw_row_bar(surface: pygame.Surface, rect: pygame.Rect, palette: UiPalette) -> None:
    """The highlight behind the selected row."""
    radius = max(2, rect.height // 4)
    pygame.draw.rect(surface, palette.panel, rect, border_radius=radius)
    pygame.draw.rect(surface, palette.accent, rect, width=2, border_radius=radius)


class ThemesScene(Scene):
    themes: list[Theme]
    scroll: ScrollList
    list_rect: pygame.Rect
    preview_rect: pygame.Rect | None
    preview_layout: BoardLayout | None

    def on_enter(self, **params: object) -> None:
        self.themes = available_themes()
        ids = [theme.id for theme in self.themes]
        current = ids.index(self.app.theme.id) if self.app.theme.id in ids else 0
        self.scroll = ScrollList(len(self.themes), current)
        self.list_rect = pygame.Rect(0, 0, 0, 0)
        self.preview_rect = None
        self.preview_layout = None

    @property
    def highlighted(self) -> Theme:
        return self.themes[self.scroll.selected]

    def _apply(self) -> None:
        self.app.set_theme(self.highlighted.id)
        if self.app.context is not None:
            self.app.context.save_settings()

    def handle_action(self, action: Action) -> None:
        if action is Action.UP:
            self.scroll.move(-1)
        elif action is Action.DOWN:
            self.scroll.move(1)
        elif action is Action.CONFIRM:
            self._apply()
        elif action is Action.BACK:
            self.app.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.scroll.handle_event(event) is not None:
            self._apply()

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        surface.fill(self.app.theme.background)
        screen = surface.get_rect()
        margin = max(12, screen.height // 40)

        title = fonts.title.render(t("Themes", "Thèmes"), True, palette.accent)
        title_rect = title.get_rect(midtop=(screen.centerx, margin))
        surface.blit(title, title_rect)
        hint = fonts.small.render(
            t(
                "Up/Down: choose · Enter: apply · Esc: back",
                "Haut/Bas : choisir · Entrée : appliquer · Échap : retour",
            ),
            True,
            palette.muted,
        )
        hint_rect = hint.get_rect(midbottom=(screen.centerx, screen.bottom - margin))
        surface.blit(hint, hint_rect)

        body = pygame.Rect(
            margin, title_rect.bottom + margin, screen.width - 2 * margin, hint_rect.top - title_rect.bottom
        )
        body.height -= 2 * margin
        list_w = min(380, max(220, body.width * 2 // 5))
        self.list_rect = pygame.Rect(body.left, body.top, list_w, body.height)
        self._draw_list(surface)

        right = pygame.Rect(
            self.list_rect.right + margin, body.top, body.right - self.list_rect.right - margin, 0
        )
        right.height = body.height
        side = min(right.width, right.height)
        self.preview_rect = pygame.Rect(0, 0, side, side)
        self.preview_rect.center = right.center
        self._draw_preview(surface, self.preview_rect)

    def _draw_list(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        font = self._list_font()
        row_h = font.get_height() + 12
        swatch = row_h - 12
        check_w = row_h
        for index, row in self.scroll.layout(self.list_rect, row_h):
            theme = self.themes[index]
            bar = row.inflate(0, -4)
            if index == self.scroll.selected:
                draw_row_bar(surface, bar, palette)
            x = bar.left + 8
            y = bar.centery - swatch // 2
            pygame.draw.rect(surface, theme.background, (x - 2, y - 2, swatch * 3 + 4, swatch + 4))
            for k, kind in enumerate(_SWATCH):
                surface.blit(theme.tile(kind, swatch), (x + k * swatch, y))
            x += 3 * swatch + 10
            colour = palette.accent if index == self.scroll.selected else palette.text
            name = fit_text(font, theme_label(theme), bar.right - check_w - x)
            text = font.render(name, True, colour)
            surface.blit(text, text.get_rect(midleft=(x, bar.centery)))
            if theme.id == self.app.theme.id:
                _draw_check(
                    surface, pygame.Rect(bar.right - check_w, bar.top, check_w, bar.height), palette.good
                )
        self.scroll.draw_arrows(surface, self.list_rect, palette.muted)

    def _list_font(self) -> pygame.font.Font:
        """The normal font when every name fits the list, else the small one (narrow windows, French)."""
        font = self.app.fonts.normal
        row_h = font.get_height() + 12
        room = self.list_rect.width - 8 - 3 * (row_h - 12) - 10 - row_h
        if max(font.size(theme_label(theme))[0] for theme in self.themes) <= room:
            return font
        return self.app.fonts.small

    def _draw_preview(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        theme = self.highlighted
        fonts = self.app.fonts
        pygame.draw.rect(surface, theme.background, rect)
        pygame.draw.rect(surface, self.app.theme.palette.accent, rect, width=2)
        pad = max(10, rect.width // 24)
        y = rect.top + pad
        name = fonts.normal.render(
            fit_text(fonts.normal, theme_label(theme), rect.width - 2 * pad), True, theme.palette.text
        )
        surface.blit(name, name.get_rect(midtop=(rect.centerx, y)))
        y += name.get_height() + pad // 2
        note = _NOTES.get(theme.id)
        if note is not None:
            text = fonts.small.render(
                fit_text(fonts.small, note(), rect.width - 2 * pad), True, theme.palette.muted
            )
            surface.blit(text, text.get_rect(midtop=(rect.centerx, y)))
        y += fonts.small.get_height() + pad // 2

        sample = fonts.small.render(
            t("Moves 12 · Pushes 3", "Coups 12 · Poussées 3"), True, theme.palette.text
        )
        strip = pygame.Rect(rect.left + pad, 0, rect.width - 2 * pad, sample.get_height() + pad)
        strip.bottom = rect.bottom - pad
        pygame.draw.rect(surface, theme.palette.panel, strip, border_radius=max(2, pad // 3))
        surface.blit(sample, sample.get_rect(midleft=(strip.left + pad, strip.centery)))
        chip = sample.get_height() // 2 + 2
        cx = strip.right - pad - chip
        if strip.left + 2 * pad + sample.get_width() < cx - 3 * (chip + 6):  # colour dots only if room
            for colour in (theme.palette.bad, theme.palette.good, theme.palette.accent):
                pygame.draw.circle(surface, colour, (cx, strip.centery), chip // 2 + 2)
                cx -= chip + 6

        area = pygame.Rect(rect.left + pad, y, rect.width - 2 * pad, strip.top - pad - y)
        level = SAMPLE_LEVEL
        self.preview_layout = BoardRenderer(theme).draw(surface, level, level.player, level.boxes, area)


def _draw_check(surface: pygame.Surface, rect: pygame.Rect, colour: tuple[int, int, int]) -> None:
    """A check mark (the default font has no ✓ glyph)."""
    s = min(rect.width, rect.height) * 3 // 5
    cx, cy = rect.center
    points = [(cx - s // 2, cy), (cx - s // 6, cy + s // 3), (cx + s // 2, cy - s // 3)]
    pygame.draw.lines(surface, colour, False, points, width=max(2, s // 6))


SCENE = ThemesScene
