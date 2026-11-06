"""Game scene (spec 7.9): play a level with HUD, undo/redo, double-press restart, pause, victory and saves.

Rules:

- Moves are applied to ``state`` at once; ``settings.animation`` only tweens the drawing (player and pushed
  box) over 120 ms ("normal") or 60 ms ("fast"). While a tween runs, at most two more moves are queued.
- The timer counts while the scene is on top, not paused, the window has focus and the level is unsolved.
- Restart needs a second ``restart`` action within 1.5 s; the first one shows a prompt.
- The session (LURD history + redo stack, spec 7.6) is saved on pause, on leaving the scene (which includes
  closing the window) and every 10 s of play. A game without moves saves nothing and deletes this level's
  session, so merely opening another level never discards a saved game.
- On a win: ``Progress.record_run``, progress saved, this level's session deleted, ``victory`` pushed.
- Hint (``hint`` action): the solver runs in a ``SolverWorker`` from the current state (3 s / 500,000 nodes,
  ``optimal``, then ``fast`` once if a limit was hit). An answer is shown only while the state is still the
  one it was asked for (``GameState.signature()``): the walk to the next push, the box, and an arrow where
  the box goes, until the next move; a move, undo, redo or restart cancels a pending hint. Any hint marks
  the run assisted.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pygame

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step
from alexvolkihar_sokoban.core.lurd import LurdError, restore
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.core.state import GameState, MoveOutcome
from alexvolkihar_sokoban.persistence.session import SavedSession
from alexvolkihar_sokoban.scoring.records import LastPlayed, Progress, RunResult
from alexvolkihar_sokoban.solver.api import Mode, SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui.board_renderer import BoardLayout, BoardRenderer
from alexvolkihar_sokoban.ui.hud import HudData, draw_hud, draw_toast, hud_stats, key_hints
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.solver_worker import SolverWorker
from alexvolkihar_sokoban.ui.themes.base import TileKind

if TYPE_CHECKING:
    from alexvolkihar_sokoban.ui.app import App

logger = logging.getLogger(__name__)

_MOVES = {
    Action.UP: Direction.UP,
    Action.DOWN: Direction.DOWN,
    Action.LEFT: Direction.LEFT,
    Action.RIGHT: Direction.RIGHT,
}
# Actions that end a running tween (and drop the queued moves) before they apply.
_COMMANDS = frozenset({Action.PAUSE, Action.BACK, Action.UNDO, Action.REDO, Action.RESTART, Action.HINT})
ANIMATION_MS = {"off": 0, "normal": 120, "fast": 60}
MAX_QUEUED_MOVES = 2
RESTART_WINDOW_MS = 1_500
AUTOSAVE_MS = 10_000
SAVE_FAILED_MS = 3_000
_NOWHERE: Pos = (-1, -1)  # a player position off the board, to draw a board without the player
HINT_LIMITS = SolveLimits(time_s=3.0, max_nodes=500_000)
HINT_MESSAGE_MS = 4_000


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def pack_title(pack: Pack) -> str:
    """The pack's title; the First steps, generated and custom packs are translated by id."""
    if pack.id == "first-steps":
        return t("First steps", "Premiers pas")
    if pack.id == "generated":
        return t("Generated", "Niveaux générés")
    if pack.id == "custom":
        return t("Custom", "Mes niveaux")
    return pack.title


def leave_game(app: App, target: str, *, pack_id: str | None = None) -> None:
    """Close the scenes above ``target`` (``"main_menu"`` or ``"level_select"``), opening it if needed.

    Each closed game scene saves its session on the way out. When ``target`` is not on the stack, the stack
    is unwound to the main menu (created if missing) and ``target`` is pushed on it.
    """
    if target in (s.name for s in app.stack):
        while app.top is not None and app.top.name != target:
            app.pop()
        return
    while len(app.stack) > 1 and app.top is not None and app.top.name != "main_menu":
        app.pop()
    if app.top is None or app.top.name != "main_menu":
        app.replace("main_menu")
    if target != "main_menu":
        params: dict[str, object] = {} if pack_id is None else {"pack_id": pack_id}
        app.push(target, **params)


@dataclass(frozen=True)
class Hint:
    """A solver answer for ``signature``: the walk then the box to push (``highlight``), and an arrow on the
    cell the box is pushed to, pointing the push's way (drawn there, it leaves the box itself visible)."""

    signature: tuple[Pos, frozenset[Pos]]
    highlight: tuple[Pos, ...]
    arrow: tuple[Pos, Direction]


def next_push(player: Pos, lurd: str) -> tuple[tuple[Pos, ...], tuple[Pos, Direction]] | None:
    """The walk of ``lurd`` up to its first push then the pushed box, and ``(box destination, direction)``.

    ``None`` when ``lurd`` has no push or is not LURD.
    """
    cells: list[Pos] = []
    pos = player
    for ch in lurd:
        try:
            d = Direction.from_char(ch)
        except ValueError:
            return None
        if ch.isupper():
            box = step(pos, d)
            return (*cells, box), (step(box, d), d)
        pos = step(pos, d)
        cells.append(pos)
    return None


def format_count(n: int) -> str:
    """``12,345`` in English, ``12 345`` (narrow no-break space) in French."""
    return t(f"{n:,}", f"{n:,}".replace(",", "\u202f"))


@dataclass
class _Tween:
    """The drawing of the last move, sliding from one cell to the next."""

    player_from: Pos
    player_to: Pos
    box_from: Pos | None
    box_to: Pos | None
    duration: int
    elapsed: int = 0

    @property
    def fraction(self) -> float:
        return min(1.0, self.elapsed / self.duration)


class GameScene(Scene):
    pack: Pack
    entry: LevelEntry
    state: GameState
    elapsed_ms: int
    assisted: bool
    paused: bool

    def on_enter(self, **params: object) -> None:
        pack = params.get("pack")
        level_id = params.get("level_id")
        resume = params.get("resume")
        if not isinstance(pack, Pack) or not isinstance(level_id, str):
            raise TypeError("game scene needs pack: Pack and level_id: str")
        if resume is not None and not isinstance(resume, SavedSession):
            raise TypeError("resume must be a SavedSession or None")
        self.pack = pack
        self.entry = pack.entry(level_id)
        self.level_hash = self.entry.level.canonical_hash()
        self.state, self.elapsed_ms, self.assisted = self._start(resume)
        self.paused = False
        self.focused = True
        self.won = False
        self.renderer = BoardRenderer(self.app.theme)
        self.board_layout: BoardLayout | None = None
        self._clock_ms = 0  # time spent on top, paused or not: drives the prompts
        self._since_save_ms = 0
        self._restart_until: int | None = None
        self._message: str | None = None
        self._message_until = 0
        self._tween: _Tween | None = None
        self._queue: deque[Direction] = deque()
        self.worker = SolverWorker()
        self._hint: Hint | None = None
        self._hint_mode: Mode | None = None  # the mode of the pending hint search, if any
        self._remember_last_played()

    def _start(self, resume: SavedSession | None) -> tuple[GameState, int, bool]:
        """The resumed state when ``resume`` belongs to this level and replays cleanly, else a fresh one."""
        level = self.entry.level
        if resume is not None and resume.level_hash == self.level_hash:
            try:
                return restore(level, resume.lurd, resume.redo_lurd), resume.elapsed_ms, resume.assisted
            except LurdError as exc:
                logger.warning("saved game not resumed: %s", exc)
        return GameState(level), 0, False

    def _remember_last_played(self) -> None:
        context = self.app.context
        if context is None:
            return
        context.progress.set_last_played(LastPlayed(self.pack.id, self.entry.id, self.level_hash))
        if not context.save_progress():
            self._show(t("Could not save the progress.", "Impossible d'enregistrer la progression."))

    # -- public API --------------------------------------------------------------------------------------

    @property
    def animating(self) -> bool:
        return self._tween is not None

    @property
    def hint(self) -> Hint | None:
        """The hint on show: only while the state is the one it was computed for."""
        hint = self._hint
        if hint is not None and hint.signature == self.state.signature():
            return hint
        return None

    @property
    def hint_pending(self) -> bool:
        """``True`` while the solver looks for a hint."""
        return self._hint_mode is not None

    @property
    def message(self) -> str | None:
        """The prompt or warning shown over the board, if any (the hint search progress first)."""
        if self._hint_mode is not None:
            text = t("Looking for a hint…", "Recherche d'un indice…")
            progress = self.worker.progress
            if progress is not None and progress[0] > 0:
                text += f" {format_count(progress[0])} positions"  # the same word in French
            return text
        if self._message is not None and self._clock_ms < self._message_until:
            return self._message
        return None

    def mark_assisted(self) -> None:
        """The player got help (hint, solver replay): this run earns no stars and no records."""
        self.assisted = True

    def request_hint(self) -> None:
        """Look for the next push from the current state; the run becomes assisted at once."""
        self.mark_assisted()
        if self._hint_mode is not None or self.hint is not None:
            return  # already looking, or already shown
        self._disarm_restart()
        self._message = None
        self._start_hint("optimal")

    def _start_hint(self, mode: Mode) -> None:
        state = self.state
        self._hint = None
        self._hint_mode = mode
        self.worker.start(state.level, state.boxes, state.player, HINT_LIMITS, mode, tag=state.signature())

    def _drop_hint(self) -> None:
        """The state changed: hide the hint and stop looking for one."""
        self._hint = None
        if self._hint_mode is not None:
            self._hint_mode = None
            self.worker.cancel()

    def _poll_hint(self) -> None:
        got = self.worker.poll()
        if got is None:
            return
        tag, result = got
        mode, self._hint_mode = self._hint_mode, None
        if mode is None or tag != self.state.signature():
            return  # asked about another position: never drawn on this one
        self._use_hint(result, mode)

    def _use_hint(self, result: SolveResult, mode: Mode) -> None:
        status = result.status
        if status is SolveStatus.SOLVED:
            found = next_push(self.state.player, result.lurd or "")
            if found is not None:
                self._hint = Hint(self.state.signature(), found[0], found[1])
        elif status is SolveStatus.UNSOLVABLE:
            self._show(t("Dead end — undo some moves", "Impasse — annulez quelques coups"), HINT_MESSAGE_MS)
        elif status in (SolveStatus.LIMIT_TIME, SolveStatus.LIMIT_NODES):
            if mode == "optimal":
                self._start_hint("fast")  # a quick, maybe longer answer beats none
            else:
                self._show(t("No hint found in time", "Pas d'indice trouvé à temps"), HINT_MESSAGE_MS)
        elif status is SolveStatus.INVALID:
            self._show(t("No hint available", "Aucun indice disponible"), HINT_MESSAGE_MS)

    def restart(self) -> None:
        """Back to the start position, timer included (the assisted flag stays: the help was seen)."""
        self._drop_hint()
        self._tween = None
        self._queue.clear()
        self.state.restart()
        self.elapsed_ms = 0
        self._since_save_ms = 0
        self._disarm_restart()

    def save_session(self) -> None:
        """Save the game in progress for Continue; without moves, drop this level's saved game instead."""
        context = self.app.context
        self._since_save_ms = 0
        if context is None or self.won:
            return
        if self.state.moves == 0:
            if context.session is not None and context.session.level_hash == self.level_hash:
                context.save_session(None)
            return
        session = SavedSession(
            pack_id=self.pack.id,
            level_id=self.entry.id,
            level_hash=self.level_hash,
            lurd=self.state.lurd,
            redo_lurd=self.state.redo_lurd,
            elapsed_ms=self.elapsed_ms,
            assisted=self.assisted,
            saved_at=utc_now(),
        )
        if not context.save_session(session):
            self._show(
                t("Could not save the game in progress.", "Impossible d'enregistrer la partie en cours.")
            )

    # -- scene hooks -------------------------------------------------------------------------------------

    def on_exit(self) -> None:
        self._drop_hint()
        self.save_session()

    def on_resume(self) -> None:
        self.paused = False
        self.focused = True  # the key or click that closed the overlay came through this window

    def handle_action(self, action: Action) -> None:
        if self.won:
            return
        direction = _MOVES.get(action)
        if direction is not None:
            self._disarm_restart()
            self._input_move(direction)
            return
        if action not in _COMMANDS:
            return
        if self._finish_tween():
            return  # that move won the level
        self._queue.clear()
        if action in (Action.PAUSE, Action.BACK):
            self._disarm_restart()
            self._open_pause()
        elif action is Action.HINT:
            self.request_hint()
        elif action is Action.UNDO:
            self._disarm_restart()
            if self.state.undo() is not None:
                self._drop_hint()
        elif action is Action.REDO:
            self._disarm_restart()
            if self.state.redo() is not None:
                self._drop_hint()
            if self.state.is_solved:
                self._win()
        elif action is Action.RESTART:
            self._restart_pressed()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.WINDOWFOCUSLOST:
            self.focused = False
        elif event.type == pygame.WINDOWFOCUSGAINED:
            self.focused = True
        elif event.type == pygame.ACTIVEEVENT and getattr(event, "state", 0) & pygame.APPINPUTFOCUS:
            self.focused = bool(getattr(event, "gain", 1))

    def update(self, dt_ms: int) -> None:
        self._clock_ms += dt_ms
        self._poll_hint()
        if self._restart_until is not None and self._clock_ms >= self._restart_until:
            self._restart_until = None
        if not self.won and not self.paused and self.focused:
            self.elapsed_ms += dt_ms
            self._since_save_ms += dt_ms
            if self._since_save_ms >= AUTOSAVE_MS:
                self.save_session()
        tween = self._tween
        if tween is not None:
            tween.elapsed += dt_ms
            if tween.elapsed >= tween.duration:
                self._tween = None
                self._after_tween()

    # -- moves -------------------------------------------------------------------------------------------

    def _input_move(self, direction: Direction) -> None:
        if self._tween is not None:
            if len(self._queue) < MAX_QUEUED_MOVES:
                self._queue.append(direction)
            return
        self._move(direction)

    def _move(self, direction: Direction) -> None:
        before = self.state.player
        outcome = self.state.move(direction)
        if outcome is MoveOutcome.BLOCKED:
            return
        self._drop_hint()
        duration = ANIMATION_MS.get(self.app.settings.animation, 0)
        if duration <= 0:
            if self.state.is_solved:
                self._win()
            return
        box_from = box_to = None
        if outcome is MoveOutcome.PUSHED:
            box_from = step(before, direction)
            box_to = step(box_from, direction)
        self._tween = _Tween(before, self.state.player, box_from, box_to, duration)

    def _after_tween(self) -> None:
        """A tween ended: show the win, or play the next queued move."""
        if self.state.is_solved:
            self._win()
            return
        while self._queue and self._tween is None and not self.won:
            self._move(self._queue.popleft())

    def _finish_tween(self) -> bool:
        """Drop the running tween (its move is already played); ``True`` when that move won the level."""
        if self._tween is None:
            return False
        self._tween = None
        if self.state.is_solved:
            self._win()
            return True
        return False

    # -- restart, pause, win -----------------------------------------------------------------------------

    def _show(self, text: str, duration_ms: int = SAVE_FAILED_MS) -> None:
        self._message = text
        self._message_until = self._clock_ms + duration_ms

    def _disarm_restart(self) -> None:
        if self._restart_until is not None:
            self._restart_until = None
            self._message = None

    def _restart_pressed(self) -> None:
        if self._restart_until is not None:
            self.restart()
            return
        if self.state.moves == 0:
            return  # nothing to restart
        self._restart_until = self._clock_ms + RESTART_WINDOW_MS
        self._show(t("Press R again to restart", "Appuyez encore sur R pour recommencer"), RESTART_WINDOW_MS)

    def _open_pause(self) -> None:
        self.paused = True
        self.save_session()
        self.app.push("pause", game=self)

    def _win(self) -> None:
        self.won = True
        self._drop_hint()
        self._tween = None
        self._queue.clear()
        self._disarm_restart()
        run = RunResult(
            moves=self.state.moves,
            pushes=self.state.pushes,
            elapsed_ms=self.elapsed_ms,
            lurd=self.state.lurd,
            assisted=self.assisted,
            finished_at=utc_now(),
        )
        context = self.app.context
        progress = context.progress if context is not None else Progress()
        update = progress.record_run(self.level_hash, self.pack.id, self.entry.id, run, self.entry.par)
        if context is not None:
            context.save_progress()
            if context.session is not None and context.session.level_hash == self.level_hash:
                context.save_session(None)
        self.app.push(
            "victory", pack=self.pack, level_id=self.entry.id, update=update, run=run, par=self.entry.par
        )

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        app = self.app
        theme = app.theme
        palette = theme.palette
        surface.fill(theme.background)
        show_time = app.settings.show_timer
        data = HudData(
            title=f"{pack_title(self.pack)} — {self.entry.title}",
            stats=hud_stats(
                moves=self.state.moves,
                pushes=self.state.pushes,
                elapsed_ms=self.elapsed_ms if show_time else None,
                par=self.entry.par,
            ),
            hints=key_hints(app.settings.keybindings),
        )
        area = draw_hud(surface, app.fonts, palette, data)
        pad = max(4, min(area.width, area.height) // 40)
        board = area.inflate(-2 * pad, -2 * pad)
        if board.width < 1 or board.height < 1:
            board = area
        self.renderer.theme = theme
        if self._tween is None:
            hint = self.hint
            self.board_layout = self.renderer.draw(
                surface,
                self.state.level,
                self.state.player,
                self.state.boxes,
                board,
                highlight=() if hint is None else hint.highlight,
                arrow=None if hint is None else hint.arrow,
            )
        else:
            self.board_layout = self._draw_tween(surface, board, self._tween)
        message = self.message
        if message is not None:
            draw_toast(surface, app.fonts, palette, area, message)

    def _draw_tween(self, surface: pygame.Surface, area: pygame.Rect, tween: _Tween) -> BoardLayout:
        """The board without the moving pieces, then the pieces between their two cells."""
        state = self.state
        boxes = state.boxes if tween.box_to is None else state.boxes - {tween.box_to}
        layout = self.renderer.draw(surface, state.level, _NOWHERE, boxes, area)
        tile = layout.tile
        frac = tween.fraction
        old_clip = surface.get_clip()
        surface.set_clip(area.clip(old_clip))
        try:
            if tween.box_from is not None and tween.box_to is not None:
                kind = TileKind.BOX_ON_GOAL if tween.box_to in state.level.goals else TileKind.BOX
                rect = _between(layout, tween.box_from, tween.box_to, frac)
                surface.blit(self.app.theme.tile(kind, tile), rect)
            rect = _between(layout, tween.player_from, tween.player_to, frac)
            surface.blit(self.app.theme.tile(TileKind.PLAYER, tile), rect)
        finally:
            surface.set_clip(old_clip)
        return layout


def _between(layout: BoardLayout, start: Pos, end: Pos, frac: float) -> pygame.Rect:
    a, b = layout.cell_rect(start), layout.cell_rect(end)
    x = round(a.x + (b.x - a.x) * frac)
    y = round(a.y + (b.y - a.y) * frac)
    return pygame.Rect(x, y, a.width, a.height)


SCENE = GameScene
