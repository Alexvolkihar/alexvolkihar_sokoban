"""Runs the solver off the UI thread (spec 7.9: hints and the solver replay).

One job at a time: ``start`` cancels the running job first. The UI thread calls ``poll()`` each frame; a job
delivers its ``(tag, result)`` once, unless it was cancelled, in which case its result is dropped. The tag
lets the caller check that the result still matches what it asked about (hints use the state signature).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.api import Mode, SolveLimits, SolveResult, SolveStatus, solve

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    tag: object
    stop: threading.Event = field(default_factory=threading.Event)
    progress: tuple[int, int] | None = None
    result: SolveResult | None = None
    thread: threading.Thread | None = None


class SolverWorker:
    """A background solver; every method is called from the UI thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: _Job | None = None
        self._last: _Job | None = None  # the most recent job started, cancelled or not (for ``join``)

    @property
    def busy(self) -> bool:
        """``True`` while a job runs or holds a result not polled yet."""
        return self._job is not None

    @property
    def progress(self) -> tuple[int, int] | None:
        """``(nodes_expanded, elapsed_ms)`` last reported by the running job, if any."""
        with self._lock:
            return None if self._job is None else self._job.progress

    def start(
        self,
        level: Level,
        boxes: frozenset[Pos],
        player: Pos,
        limits: SolveLimits,
        mode: Mode = "optimal",
        tag: object = None,
    ) -> None:
        """Solve from ``boxes``/``player`` in a daemon thread, cancelling the running job first."""
        self.cancel()
        job = _Job(tag)
        job.thread = threading.Thread(
            target=self._run,
            args=(job, level, boxes, player, limits, mode),
            name="solver-worker",
            daemon=True,  # never keeps the game open: the solver also stops at its time limit
        )
        with self._lock:
            self._job = job
        self._last = job
        job.thread.start()

    def cancel(self) -> None:
        """Ask the running job to stop and forget it: its result will never be delivered."""
        with self._lock:
            job, self._job = self._job, None
        if job is not None:
            job.stop.set()

    def poll(self) -> tuple[object, SolveResult] | None:
        """The finished job's ``(tag, result)``, once; ``None`` while it runs or when there is none."""
        with self._lock:
            job = self._job
            if job is None or job.result is None:
                return None
            self._job = None
            return job.tag, job.result

    def join(self, timeout: float | None = None) -> bool:
        """Wait for the thread of the last job started; ``True`` when no thread runs any more."""
        job = self._last
        if job is None or job.thread is None:
            return True
        job.thread.join(timeout)
        return not job.thread.is_alive()

    def _run(
        self, job: _Job, level: Level, boxes: frozenset[Pos], player: Pos, limits: SolveLimits, mode: Mode
    ) -> None:
        def on_progress(expanded: int, elapsed_ms: int) -> None:
            with self._lock:
                job.progress = (expanded, elapsed_ms)

        try:
            result = solve(
                level,
                boxes=boxes,
                player=player,
                limits=limits,
                mode=mode,
                should_stop=job.stop.is_set,
                on_progress=on_progress,
            )
        except Exception:  # a solver bug must not kill the game: report it as "no answer"
            logger.exception("solver failed")
            result = SolveResult(SolveStatus.INVALID, None, None, None, 0, 0, 0)
        with self._lock:
            job.result = result
            job.progress = None
