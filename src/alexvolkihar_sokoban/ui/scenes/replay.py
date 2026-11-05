"""Watch the solver (spec 7.9): play a level's solution from its start position.

The solution is the level's par (stored in the pack); without a par, or when the par does not replay to a
solved state, the solver runs in a ``SolverWorker`` (30 s / 3,000,000 nodes) while "Solving…" and its
progress are shown. Controls: ``confirm`` play/pause (from the start again once at the end),
``left``/``right`` one step back/forward (pausing), ``up``/``down`` speed (1, 2, 4 or 8 steps per second),
``restart`` back to the start, ``back``/``pause`` return to the game.

Pushed with ``pack``, ``level_id`` and ``on_watch``: entering the scene calls ``on_watch()`` once, so the
calling game run becomes assisted (spec 7.5).
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.lurd import LurdError, replay
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.core.state import GameState
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.ui.board_renderer import BoardRenderer
from alexvolkihar_sokoban.ui.hud import HudData, HudStat, draw_hud, draw_toast
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action, describe_binding
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.game import format_count, pack_title
from alexvolkihar_sokoban.ui.solver_worker import SolverWorker

REPLAY_LIMITS = SolveLimits(time_s=30.0, max_nodes=3_000_000)
SPEEDS = (1, 2, 4, 8)  # steps per second
DEFAULT_SPEED = 4


def _failure_text(status: SolveStatus) -> str:
    if status is SolveStatus.UNSOLVABLE:
        return t("This level has no solution", "Ce niveau n'a pas de solution")
    if status in (SolveStatus.LIMIT_TIME, SolveStatus.LIMIT_NODES):
        return t(
            "No solution found within the solver's limits",
            "Aucune solution trouvée dans les limites du solveur",
        )
    return t("This level cannot be solved here", "Ce niveau ne peut pas être résolu ici")


def _directions(entry: LevelEntry, lurd: str) -> list[Direction] | None:
    """The steps of ``lurd`` when it solves the level from its start, else ``None``."""
    try:
        if not replay(entry.level, lurd).is_solved:
            return None
    except LurdError:
        return None
    return [Direction.from_char(ch) for ch in lurd if not ch.isspace()]


class ReplayScene(Scene):
    pack: Pack
    entry: LevelEntry
    state: GameState

    def on_enter(self, **params: object) -> None:
        pack = params.get("pack")
        level_id = params.get("level_id")
        on_watch = params.get("on_watch")
        if not isinstance(pack, Pack) or not isinstance(level_id, str):
            raise TypeError("replay scene needs pack: Pack and level_id: str")
        self.pack = pack
        self.entry = pack.entry(level_id)
        self.state = GameState(self.entry.level)
        self.renderer = BoardRenderer(self.app.theme)
        self.worker = SolverWorker()
        self.steps: list[Direction] = []
        self.total_pushes = 0
        self.speed = DEFAULT_SPEED
        self.playing = False
        self.solving = False
        self._failure: str | None = None
        self._since_step_ms = 0
        if callable(on_watch):
            on_watch()
        par = self.entry.par
        steps = None if par is None else _directions(self.entry, par.lurd)
        if steps is not None:
            self._ready(steps)
        else:
            self.solving = True
            level = self.entry.level
            self.worker.start(level, level.boxes, level.player, REPLAY_LIMITS)

    # -- public state ------------------------------------------------------------------------------------

    @property
    def position(self) -> int:
        """Steps played so far."""
        return self.state.moves

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def message(self) -> str | None:
        """ "Solving…" with the progress, or why there is nothing to play."""
        if self.solving:
            text = t("Solving…", "Résolution…")
            progress = self.worker.progress
            if progress is not None and progress[0] > 0:
                seconds = progress[1] // 1000
                text += f" {format_count(progress[0])} positions · {seconds} s"
            return text
        return self._failure

    # -- playback ----------------------------------------------------------------------------------------

    def _ready(self, steps: list[Direction]) -> None:
        self.steps = steps
        self.total_pushes = replay(self.entry.level, "".join(d.char for d in steps), strict_case=False).pushes
        self.solving = False
        self.playing = bool(steps)

    def _solved(self, result: SolveResult) -> None:
        self.solving = False
        steps = None
        if result.status is SolveStatus.SOLVED and result.lurd is not None:
            steps = _directions(self.entry, result.lurd)
        if steps is None:
            self._failure = _failure_text(result.status)
        else:
            self._ready(steps)

    def _forward(self) -> bool:
        if self.position >= self.total:
            return False
        self.state.move(self.steps[self.position])
        return True

    def _rewind(self) -> None:
        self.state.restart()
        self._since_step_ms = 0

    def _toggle(self) -> None:
        if not self.steps:
            return
        if self.playing:
            self.playing = False
            return
        if self.position >= self.total:
            self._rewind()
        self.playing = True
        self._since_step_ms = 0

    def _change_speed(self, delta: int) -> None:
        index = SPEEDS.index(self.speed) + delta
        self.speed = SPEEDS[max(0, min(len(SPEEDS) - 1, index))]

    # -- scene hooks -------------------------------------------------------------------------------------

    def on_exit(self) -> None:
        self.worker.cancel()

    def handle_action(self, action: Action) -> None:
        if action in (Action.BACK, Action.PAUSE):
            self.app.pop()
            return
        handlers: dict[Action, Callable[[], object]] = {
            Action.CONFIRM: self._toggle,
            Action.RIGHT: self._step_forward,
            Action.LEFT: self._step_back,
            Action.UP: lambda: self._change_speed(1),
            Action.DOWN: lambda: self._change_speed(-1),
            Action.RESTART: self._restart,
        }
        handler = handlers.get(action)
        if handler is not None:
            handler()

    def _step_forward(self) -> None:
        self.playing = False
        self._forward()

    def _step_back(self) -> None:
        self.playing = False
        self.state.undo()

    def _restart(self) -> None:
        self._rewind()

    def update(self, dt_ms: int) -> None:
        if self.solving:
            got = self.worker.poll()
            if got is not None:
                self._solved(got[1])
            return
        if not self.playing:
            return
        self._since_step_ms += dt_ms
        interval = 1000 // self.speed
        while self._since_step_ms >= interval:
            self._since_step_ms -= interval
            if not self._forward():
                break
        if self.position >= self.total:
            self.playing = False
            self._since_step_ms = 0

    # -- drawing -----------------------------------------------------------------------------------------

    def _status(self) -> str:
        if self.solving or not self.steps:
            return "—"
        if self.playing:
            return t("Playing", "Lecture")
        if self.position >= self.total:
            return t("Solved", "Résolu")
        return t("Paused", "En pause")

    def _key_hints(self) -> list[str]:
        bindings = self.app.settings.keybindings

        def key(action: str) -> str:
            keys = bindings.get(action, ())
            return describe_binding(keys[0]) if keys else "?"

        return [
            f"{key('confirm')} " + t("play/pause", "lecture/pause"),
            f"{key('left')}/{key('right')} " + t("step", "pas à pas"),
            f"{key('up')}/{key('down')} " + t("speed", "vitesse"),
            f"{key('back')} " + t("back", "retour"),
        ]

    def draw(self, surface: pygame.Surface) -> None:
        app = self.app
        theme = app.theme
        surface.fill(theme.background)
        ready = bool(self.steps)
        stats = [
            HudStat(t("Step", "Pas"), f"{self.position}/{self.total}" if ready else "—"),
            HudStat(t("Pushes", "Poussées"), f"{self.state.pushes}/{self.total_pushes}" if ready else "—"),
            HudStat(t("Speed", "Vitesse"), f"{self.speed}/s"),
            HudStat(t("State", "État"), self._status()),
        ]
        title = f"Solution — {pack_title(self.pack)} — {self.entry.title}"  # the same word in French
        area = draw_hud(surface, app.fonts, theme.palette, HudData(title, stats, self._key_hints()))
        pad = max(4, min(area.width, area.height) // 40)
        board = area.inflate(-2 * pad, -2 * pad)
        if board.width < 1 or board.height < 1:
            board = area
        self.renderer.theme = theme
        self.renderer.draw(surface, self.state.level, self.state.player, self.state.boxes, board)
        message = self.message
        if message is not None:
            draw_toast(surface, app.fonts, theme.palette, area, message)


SCENE = ReplayScene
