"""Level select (spec 7.9): packs on the left, a grid of level tiles on the right.

Each tile shows the level's thumbnail, its id/title, a check mark once completed, 0-3 stars and the best
moves/pushes. The pack list shows "X / N" completed per pack and the grid header "completed X / N".

Keyboard: arrows move in the grid (Right goes on to the next row); Left on the first column or Tab moves
to the pack list, where Up/Down change the pack and Right, Tab or confirm go back to the grid; confirm opens
the level; back returns.
F5 re-reads the Custom levels folder. Mouse: hover/click a tile, click a pack, the wheel scrolls the grid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pygame

from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.scoring.records import LevelRecord
from alexvolkihar_sokoban.ui.context import CUSTOM_EXTENSIONS, CUSTOM_ID, GENERATED_ID
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.main_menu import _wrap
from alexvolkihar_sokoban.ui.thumbnails import render_thumbnail

Focus = Literal["packs", "grid"]

_NO_PACK = Pack("", "", ())
_TILE_TARGET_W = 180  # wished tile width; the grid fits as many whole columns as it can
_MAX_STARS = 3
_GUTTER = 14  # right edge of the pack list and of the grid, where the scroll marks go


@dataclass(frozen=True)
class _Layout:
    margin: int
    pad: int
    title_y: int
    packs: pygame.Rect  # the pack list
    pack_row_h: int
    header: pygame.Rect  # pack title and "completed X / N" above the grid
    grid: pygame.Rect
    columns: int
    cell_w: int
    cell_h: int
    rows_visible: int
    hint_y: int  # bottom of the key hint line

    @property
    def packs_visible(self) -> int:
        return max(1, self.packs.height // self.pack_row_h)


class LevelSelectScene(Scene):
    packs: list[Pack]
    focus: Focus

    def on_enter(self, **params: object) -> None:
        self.packs = []
        self.pack_index = 0
        self.selected = 0
        self.scroll = 0  # first visible grid row
        self.pack_scroll = 0  # first visible pack row
        self.focus = "grid"
        self._hashes: dict[tuple[str, str], str] = {}
        self._screen_size: tuple[int, int] | None = None
        self._load_packs()
        pack_id = params.get("pack_id")
        if isinstance(pack_id, str) and any(p.id == pack_id for p in self.packs):
            self._select_pack(next(i for i, p in enumerate(self.packs) if p.id == pack_id))
            self._follow_last_played(same_pack_only=True)
        elif not self._follow_last_played(same_pack_only=False):
            self._select_pack(0)
        self._settle_focus()

    def on_resume(self) -> None:
        """Back from a game: packs may have changed (generated level, reload); follow the last level."""
        current = self.pack.id
        self._load_packs()
        index = next((i for i, p in enumerate(self.packs) if p.id == current), None)
        if index is None:
            self._select_pack(min(self.pack_index, max(0, len(self.packs) - 1)))
        else:
            self.pack_index = index
            self.selected = min(self.selected, max(0, len(self.pack.levels) - 1))
        self._follow_last_played(same_pack_only=True)
        self.focus = "grid"
        self._settle_focus()

    # -- data ------------------------------------------------------------------------------------------

    def _load_packs(self) -> None:
        context = self.app.context
        self.packs = list(context.packs) if context is not None else []
        self._hashes.clear()

    @property
    def pack(self) -> Pack:
        """The pack shown in the grid (an empty pack when there is none at all)."""
        if not self.packs:
            return _NO_PACK
        return self.packs[self.pack_index]

    def _hash(self, pack: Pack, entry: LevelEntry) -> str:
        key = (pack.id, entry.id)
        cached = self._hashes.get(key)
        if cached is None:
            cached = self._hashes[key] = entry.level.canonical_hash()
        return cached

    def record(self, entry: LevelEntry, pack: Pack | None = None) -> LevelRecord | None:
        """The player's record for ``entry`` (of ``pack``, default the current one), by level hash."""
        context = self.app.context
        if context is None:
            return None
        return context.progress.get(self._hash(pack or self.pack, entry))

    def completed(self, pack: Pack) -> tuple[int, int]:
        """``(completed levels, levels)`` of ``pack``."""
        context = self.app.context
        if context is None:
            return 0, len(pack.levels)
        done = context.progress.completed_count(self._hash(pack, e) for e in pack.levels)
        return done, len(pack.levels)

    def pack_status(self, pack: Pack) -> str:
        done, total = self.completed(pack)
        return t(f"completed {done} / {total}", f"terminés {done} / {total}")

    def pack_title(self, pack: Pack) -> str:
        """The Generated and Custom packs get a translated title; bundled packs keep their own."""
        if pack.id == GENERATED_ID:
            return t("Generated", "Niveaux générés")
        if pack.id == CUSTOM_ID:
            return t("Custom", "Mes niveaux")
        return pack.title

    def best_text(self, entry: LevelEntry) -> str:
        """The best line of a tile (fewest moves, fewest pushes); empty before a non-assisted win."""
        rec = self.record(entry)
        if rec is None or rec.best_moves is None or rec.best_pushes is None:
            return ""
        moves, pushes = rec.best_moves.moves, rec.best_pushes.pushes
        return t(f"best {moves} moves · {pushes} pushes", f"record {moves} pas · {pushes} poussées")

    def _best_short(self, entry: LevelEntry) -> str:
        """``best_text`` for narrow tiles: "best 18/5" (moves/pushes)."""
        rec = self.record(entry)
        if rec is None or rec.best_moves is None or rec.best_pushes is None:
            return ""
        moves, pushes = rec.best_moves.moves, rec.best_pushes.pushes
        return t(f"best {moves}/{pushes}", f"record {moves}/{pushes}")

    def empty_hint(self) -> str:
        """What to say in place of the grid when the current pack has no level."""
        context = self.app.context
        if context is None:
            return t("No levels available.", "Aucun niveau disponible.")
        if self.pack.id == CUSTOM_ID:
            exts = ", ".join(CUSTOM_EXTENSIONS)
            folder = context.levels_dir
            return t(
                f"No custom levels yet. Drop {exts} files into {folder} then press F5.",
                f"Pas encore de niveaux à vous. Déposez des fichiers {exts} dans {folder} "
                "puis appuyez sur F5.",
            )
        if self.pack.id == GENERATED_ID:
            return t(
                "No generated levels yet: create one with Random level in the main menu.",
                "Aucun niveau généré pour l'instant : créez-en un avec Niveau aléatoire "
                "dans le menu principal.",
            )
        return t("This pack has no levels.", "Ce pack ne contient aucun niveau.")

    # -- selection -------------------------------------------------------------------------------------

    def _select_pack(self, index: int) -> None:
        if not self.packs:
            return
        self.pack_index = max(0, min(len(self.packs) - 1, index))
        self.selected = 0
        self.scroll = 0
        self._ensure_pack_visible()

    def _follow_last_played(self, *, same_pack_only: bool) -> bool:
        """Select the last played level when it is shown; ``True`` when it was found."""
        context = self.app.context
        last = context.progress.last_played if context is not None else None
        if last is None:
            return False
        for p_index, pack in enumerate(self.packs):
            if pack.id != last.pack_id or (same_pack_only and p_index != self.pack_index):
                continue
            for index, entry in enumerate(pack.levels):
                if entry.id == last.level_id:
                    if p_index != self.pack_index:
                        self._select_pack(p_index)
                    self.selected = index
                    self._ensure_visible()
                    return True
        return False

    def _settle_focus(self) -> None:
        """The grid can only have the focus when it has a level."""
        if not self.pack.levels:
            self.focus = "packs"

    def _ensure_visible(self) -> None:
        lay = self._layout()
        row = self.selected // lay.columns
        if row < self.scroll:
            self.scroll = row
        elif row >= self.scroll + lay.rows_visible:
            self.scroll = row - lay.rows_visible + 1
        self._clamp_scroll(lay)

    def _clamp_scroll(self, lay: _Layout) -> None:
        rows = -(-len(self.pack.levels) // lay.columns)
        self.scroll = max(0, min(self.scroll, rows - lay.rows_visible))

    def _ensure_pack_visible(self) -> None:
        shown = self._layout().packs_visible
        if self.pack_index < self.pack_scroll:
            self.pack_scroll = self.pack_index
        elif self.pack_index >= self.pack_scroll + shown:
            self.pack_scroll = self.pack_index - shown + 1
        self.pack_scroll = max(0, min(self.pack_scroll, len(self.packs) - shown))

    def _open(self, index: int) -> None:
        levels = self.pack.levels
        if not (0 <= index < len(levels)):
            return
        self.selected = index
        self.app.push("game", pack=self.pack, level_id=levels[index].id)

    # -- input -----------------------------------------------------------------------------------------

    def handle_action(self, action: Action) -> None:
        if action is Action.BACK:
            self.app.pop()
        elif self.focus == "packs":
            self._pack_action(action)
        else:
            self._grid_action(action)

    def _pack_action(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            step = -1 if action is Action.UP else 1
            target = self.pack_index + step
            if 0 <= target < len(self.packs):
                self._select_pack(target)
        elif action in (Action.RIGHT, Action.CONFIRM) and self.pack.levels:
            self.focus = "grid"

    def _grid_action(self, action: Action) -> None:
        count = len(self.pack.levels)
        cols = self.columns
        sel = self.selected
        if action is Action.LEFT:
            if sel % cols == 0:
                self.focus = "packs"
                return
            sel -= 1
        elif action is Action.RIGHT:  # wraps to the next row, like reading
            sel = min(count - 1, sel + 1)
        elif action is Action.UP:
            if sel >= cols:
                sel -= cols
        elif action is Action.DOWN:
            if sel // cols < (count - 1) // cols:
                sel = min(count - 1, sel + cols)
        elif action is Action.CONFIRM:
            self._open(sel)
            return
        self.selected = sel
        self._ensure_visible()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                if self.focus == "grid":
                    self.focus = "packs"
                elif self.pack.levels:
                    self.focus = "grid"
            elif event.key == pygame.K_F5:
                self._reload_custom()
        elif event.type == pygame.MOUSEMOTION:
            index = self._tile_at(event.pos)
            if index is not None:
                self.selected = index
                self.focus = "grid"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            index = self._tile_at(event.pos)
            if index is not None:
                self.focus = "grid"
                self._open(index)
                return
            p_index = self._pack_at(event.pos)
            if p_index is not None and p_index != self.pack_index:
                self._select_pack(p_index)
                self.focus = "packs"
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y
            self._clamp_scroll(self._layout())

    def _reload_custom(self) -> None:
        context = self.app.context
        if context is None:
            return
        current = self.pack.id
        context.reload_custom()
        self._load_packs()
        self.pack_index = next((i for i, p in enumerate(self.packs) if p.id == current), 0)
        self.selected = min(self.selected, max(0, len(self.pack.levels) - 1))
        self._ensure_visible()
        self._settle_focus()

    # -- geometry --------------------------------------------------------------------------------------

    def _layout(self) -> _Layout:
        screen = self.app.screen.get_rect()
        fonts = self.app.fonts
        margin = max(10, screen.height // 48)
        pad = max(4, fonts.small.get_height() // 4)
        title_h = fonts.normal.get_height()
        hint_h = fonts.small.get_height()
        top = margin + title_h + margin
        bottom = screen.bottom - margin - hint_h - margin // 2
        left_w = max(190, min(300, screen.width * 27 // 100))
        packs = pygame.Rect(margin, top, left_w, max(1, bottom - top))
        pack_row_h = fonts.normal.get_height() + 2 * pad
        grid_x = packs.right + margin
        header = pygame.Rect(grid_x, top, max(1, screen.right - margin - grid_x), fonts.normal.get_height())
        grid_top = header.bottom + margin // 2
        grid = pygame.Rect(grid_x, grid_top, header.width, max(1, bottom - grid_top))
        tiles_w = max(1, grid.width - _GUTTER)
        columns = max(1, tiles_w // _TILE_TARGET_W)
        cell_w = tiles_w // columns
        # As many whole rows as fit near the wished tile height, then stretched to fill the grid height.
        line = fonts.small.get_linesize()
        text_h = 5 * pad + 3 * line
        wished = text_h + (cell_w - 4 * pad) * 3 // 5
        rows_visible = max(1, min(round(grid.height / wished), grid.height // (text_h + 4 * line)))
        cell_h = grid.height // rows_visible
        return _Layout(
            margin=margin,
            pad=pad,
            title_y=margin,
            packs=packs,
            pack_row_h=pack_row_h,
            header=header,
            grid=grid,
            columns=columns,
            cell_w=cell_w,
            cell_h=cell_h,
            rows_visible=rows_visible,
            hint_y=screen.bottom - margin // 2,
        )

    @property
    def columns(self) -> int:
        return self._layout().columns

    @property
    def grid_rect(self) -> pygame.Rect:
        return self._layout().grid

    def tile_rect(self, index: int) -> pygame.Rect | None:
        """Screen rect of level ``index``'s tile, ``None`` when it is not on screen."""
        return self._tile_rect(self._layout(), index)

    def _tile_rect(self, lay: _Layout, index: int) -> pygame.Rect | None:
        if not (0 <= index < len(self.pack.levels)):
            return None
        row, col = divmod(index, lay.columns)
        if not (self.scroll <= row < self.scroll + lay.rows_visible):
            return None
        gap = lay.pad
        return pygame.Rect(
            lay.grid.x + col * lay.cell_w + gap // 2,
            lay.grid.y + (row - self.scroll) * lay.cell_h + gap // 2,
            lay.cell_w - gap,
            lay.cell_h - gap,
        )

    def pack_rect(self, index: int) -> pygame.Rect | None:
        """Screen rect of pack ``index``'s row, ``None`` when it is scrolled out of the list."""
        return self._pack_rect(self._layout(), index)

    def _pack_rect(self, lay: _Layout, index: int) -> pygame.Rect | None:
        if not (0 <= index < len(self.packs)):
            return None
        shown = index - self.pack_scroll
        if not (0 <= shown < lay.packs_visible):
            return None
        y = lay.packs.y + shown * lay.pack_row_h
        return pygame.Rect(lay.packs.x, y, lay.packs.width - _GUTTER, lay.pack_row_h)

    def _tile_at(self, pos: tuple[int, int]) -> int | None:
        lay = self._layout()
        for index in range(len(self.pack.levels)):
            rect = self._tile_rect(lay, index)
            if rect is not None and rect.collidepoint(pos):
                return index
        return None

    def _pack_at(self, pos: tuple[int, int]) -> int | None:
        lay = self._layout()
        for index in range(len(self.packs)):
            rect = self._pack_rect(lay, index)
            if rect is not None and rect.collidepoint(pos):
                return index
        return None

    # -- drawing ---------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if surface.get_size() != self._screen_size:  # first frame or window resized
            self._screen_size = surface.get_size()
            self._ensure_visible()
            self._ensure_pack_visible()
        lay = self._layout()
        self._clamp_scroll(lay)
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        surface.fill(theme.background)

        title = fonts.normal.render(t("Level select", "Choix du niveau"), True, palette.accent)
        surface.blit(title, (lay.margin, lay.title_y))
        self._draw_packs(surface, lay)
        self._draw_header(surface, lay)
        if self.pack.levels:
            self._draw_grid(surface, lay)
        else:
            self._draw_empty(surface, lay)

        hint = fonts.small.render(
            _fit(fonts.small, self._hint_text(), surface.get_width()), True, palette.muted
        )
        surface.blit(hint, hint.get_rect(midbottom=(surface.get_rect().centerx, lay.hint_y)))

    def _hint_text(self) -> str:
        if self.focus == "packs":
            text = t(
                "Up/Down: pack · Right/Enter: levels · Esc: back",
                "Haut/Bas : pack · Droite/Entrée : niveaux · Échap : retour",
            )
        else:
            text = t(
                "Arrows: choose · Enter: play · Tab: packs · Esc: back",
                "Flèches : choisir · Entrée : jouer · Tab : packs · Échap : retour",
            )
        if self.pack.id == CUSTOM_ID:
            text += t(" · F5: reload", " · F5 : recharger")
        return text

    def _draw_packs(self, surface: pygame.Surface, lay: _Layout) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        radius = max(2, lay.pack_row_h // 4)
        # One font for every row: the normal one when every title fits beside its count, else the small one.
        count_w = fonts.small.size("000 / 000")[0]
        room = lay.packs.width - _GUTTER - count_w - 6 * lay.pad
        font = fonts.normal
        if any(fonts.normal.size(self.pack_title(p))[0] > room for p in self.packs):
            font = fonts.small
        for index, pack in enumerate(self.packs):
            row = self._pack_rect(lay, index)
            if row is None:
                continue
            bar = row.inflate(0, -lay.pad // 2)
            current = index == self.pack_index
            if current:
                pygame.draw.rect(surface, palette.panel, bar, border_radius=radius)
                border = palette.accent if self.focus == "packs" else palette.muted
                pygame.draw.rect(surface, border, bar, width=2, border_radius=radius)
            done, total = self.completed(pack)
            count = fonts.small.render(
                f"{done} / {total}", True, palette.good if done == total > 0 else palette.muted
            )
            count_rect = count.get_rect(midright=(bar.right - 2 * lay.pad, bar.centery))
            surface.blit(count, count_rect)
            name = self.pack_title(pack)
            colour = palette.accent if current and self.focus == "packs" else palette.text
            label = font.render(_fit(font, name, count_rect.left - bar.left - 4 * lay.pad), True, colour)
            surface.blit(label, label.get_rect(midleft=(bar.left + 2 * lay.pad, bar.centery)))
        hidden_above = self.pack_scroll > 0
        hidden_below = self.pack_scroll + lay.packs_visible < len(self.packs)
        _draw_scroll_marks(surface, lay.packs, hidden_above, hidden_below, palette.muted)

    def _draw_header(self, surface: pygame.Surface, lay: _Layout) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        if not self.packs:
            return
        status = fonts.small.render(self.pack_status(self.pack), True, palette.muted)
        status_rect = status.get_rect(bottomright=lay.header.bottomright)
        surface.blit(status, status_rect)
        room = status_rect.left - lay.header.left - 2 * lay.pad
        name = fonts.normal.render(_fit(fonts.normal, self.pack_title(self.pack), room), True, palette.text)
        surface.blit(name, name.get_rect(bottomleft=lay.header.bottomleft))

    def _draw_grid(self, surface: pygame.Surface, lay: _Layout) -> None:
        palette = self.app.theme.palette
        levels = self.pack.levels
        first = self.scroll * lay.columns
        last = min(len(levels), first + lay.rows_visible * lay.columns)
        for index in range(first, last):
            rect = self._tile_rect(lay, index)
            if rect is not None:
                self._draw_tile(surface, lay, rect, levels[index], index == self.selected)
        rows = -(-len(levels) // lay.columns)
        below = self.scroll + lay.rows_visible < rows
        _draw_scroll_marks(surface, lay.grid, self.scroll > 0, below, palette.muted)

    def _draw_tile(
        self, surface: pygame.Surface, lay: _Layout, rect: pygame.Rect, entry: LevelEntry, selected: bool
    ) -> None:
        theme = self.app.theme
        palette = theme.palette
        small = self.app.fonts.small
        pad = lay.pad
        radius = max(3, pad)
        rec = self.record(entry)
        pygame.draw.rect(surface, palette.panel, rect, border_radius=radius)
        if selected:
            border = palette.accent if self.focus == "grid" else palette.muted
            pygame.draw.rect(surface, border, rect, width=3, border_radius=radius)
        elif rec is not None and rec.completed:
            pygame.draw.rect(surface, palette.good, rect, width=1, border_radius=radius)

        line = small.get_linesize()
        inner = rect.inflate(-2 * pad, -2 * pad)
        thumb_area = pygame.Rect(inner.x, inner.y, inner.width, max(1, inner.height - 3 * line - pad))
        if thumb_area.height > 4 and thumb_area.width > 4:
            thumb = render_thumbnail(entry.level, theme, thumb_area.size)
            surface.blit(thumb, thumb.get_rect(center=thumb_area.center))

        y = thumb_area.bottom + pad
        check = line - 2
        label_room = inner.width - check - pad
        label = entry.id if entry.title == entry.id else f"{entry.id} · {entry.title}"
        colour = palette.accent if selected else palette.text
        surface.blit(small.render(_fit(small, label, label_room), True, colour), (inner.x, y))
        if rec is not None and rec.completed:
            _draw_check(surface, pygame.Rect(inner.right - check, y, check, check), palette.good)

        y += line
        stars = rec.stars if rec is not None else 0
        size = line - 2
        for i in range(_MAX_STARS):
            centre = (inner.x + size // 2 + i * (size + pad // 2), y + size // 2)
            _draw_star(
                surface, centre, size // 2, filled=i < stars, fill=palette.accent, outline=palette.muted
            )

        y += line
        best = self.best_text(entry)
        if best and small.size(best)[0] > inner.width:
            best = self._best_short(entry)
        if best:
            surface.blit(small.render(_fit(small, best, inner.width), True, palette.muted), (inner.x, y))

    def _draw_empty(self, surface: pygame.Surface, lay: _Layout) -> None:
        palette = self.app.theme.palette
        small = self.app.fonts.small
        box = lay.grid.inflate(-4 * lay.pad, -4 * lay.pad)
        lines = _wrap(self.empty_hint(), small, max(10, box.width))
        line_h = small.get_linesize()
        y = box.y + max(0, (box.height - line_h * len(lines)) // 3)
        for text in lines:
            if y + line_h > box.bottom:
                break
            label = small.render(text, True, palette.text)
            surface.blit(label, label.get_rect(midtop=(box.centerx, y)))
            y += line_h


def _fit(font: pygame.font.Font, text: str, width: int) -> str:
    """``text``, cut and ended with "…" when it is wider than ``width``."""
    if font.size(text)[0] <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # longest prefix that fits with the ellipsis, by bisection
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + "…")[0] <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def _draw_star(
    surface: pygame.Surface,
    centre: tuple[int, int],
    radius: int,
    *,
    filled: bool,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    cx, cy = centre
    points = []
    for k in range(10):
        r = radius if k % 2 == 0 else radius * 0.45
        angle = -math.pi / 2 + k * math.pi / 5
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    if filled:
        pygame.draw.polygon(surface, fill, points)
    pygame.draw.polygon(surface, fill if filled else outline, points, width=1)


def _draw_check(surface: pygame.Surface, box: pygame.Rect, colour: tuple[int, int, int]) -> None:
    w, h = box.width, box.height
    points = [
        (box.x + w * 0.1, box.y + h * 0.55),
        (box.x + w * 0.4, box.y + h * 0.85),
        (box.x + w * 0.95, box.y + h * 0.15),
    ]
    pygame.draw.lines(surface, colour, False, points, width=max(2, w // 6))


def _draw_scroll_marks(
    surface: pygame.Surface, area: pygame.Rect, above: bool, below: bool, colour: tuple[int, int, int]
) -> None:
    """Small triangles in the right gutter of ``area`` when content is hidden above or below."""
    s = _GUTTER // 2 - 1
    x = area.right - _GUTTER // 2
    if above:
        pygame.draw.polygon(surface, colour, [(x - s, area.top + s), (x + s, area.top + s), (x, area.top)])
    if below:
        bottom = area.bottom
        pygame.draw.polygon(surface, colour, [(x - s, bottom - s), (x + s, bottom - s), (x, bottom)])


SCENE = LevelSelectScene
