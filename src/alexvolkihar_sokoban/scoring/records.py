"""Per-level records and the player's progress (spec 7.5, file format spec 9.4).

Records are keyed by the level's canonical hash (spec 9.1); ``pack_id``/``level_id`` are kept for display.
Loading and saving the file is ``persistence.store``'s job: ``to_dict``/``from_dict`` exclude
``format``/``version``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.scoring.stars import beats_par_moves, compute_stars

PROGRESS_FORMAT = "alexvolkihar-sokoban/progress"
PROGRESS_VERSION = 1

_log = logging.getLogger(__name__)
_LEVEL_HASH = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class RunResult:
    """A completed run of a level, as the game scene reports it."""

    moves: int
    pushes: int
    elapsed_ms: int
    lurd: str
    assisted: bool
    finished_at: str


@dataclass(frozen=True)
class BestSolution:
    moves: int
    pushes: int
    lurd: str


@dataclass(frozen=True)
class LevelRecord:
    pack_id: str
    level_id: str
    completed: bool = False
    stars: int = 0
    plays: int = 0
    first_completed_at: str | None = None
    best_moves: BestSolution | None = None
    best_pushes: BestSolution | None = None
    best_time_ms: int | None = None


@dataclass(frozen=True)
class RecordUpdate:
    """What ``Progress.record_run`` changed, for the victory screen."""

    record: LevelRecord
    stars_earned: int
    new_best_moves: bool
    new_best_pushes: bool
    new_best_time: bool
    beats_par_moves: bool


@dataclass(frozen=True)
class LastPlayed:
    pack_id: str
    level_id: str
    level_hash: str


def _better_moves(new: BestSolution, old: BestSolution | None) -> bool:
    """Fewer moves wins; on equal moves, fewer pushes wins. An exact tie keeps the old solution."""
    return old is None or (new.moves, new.pushes) < (old.moves, old.pushes)


def _better_pushes(new: BestSolution, old: BestSolution | None) -> bool:
    """Fewer pushes wins; on equal pushes, fewer moves wins. An exact tie keeps the old solution."""
    return old is None or (new.pushes, new.moves) < (old.pushes, old.moves)


class Progress:
    """Mutable collection of level records plus the last level played."""

    def __init__(
        self, levels: dict[str, LevelRecord] | None = None, last_played: LastPlayed | None = None
    ) -> None:
        self.levels: dict[str, LevelRecord] = dict(levels) if levels else {}
        self.last_played: LastPlayed | None = last_played

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Progress):
            return NotImplemented
        return self.levels == other.levels and self.last_played == other.last_played

    __hash__ = None  # type: ignore[assignment]  # mutable

    def __repr__(self) -> str:
        return f"Progress(levels={self.levels!r}, last_played={self.last_played!r})"

    def get(self, level_hash: str) -> LevelRecord | None:
        return self.levels.get(level_hash)

    def record_run(
        self, level_hash: str, pack_id: str, level_id: str, run: RunResult, par: Par | None
    ) -> RecordUpdate:
        """Store a completed run. An assisted run only marks the level completed and counts the play."""
        old = self.levels.get(level_hash) or LevelRecord(pack_id=pack_id, level_id=level_id)
        record = replace(
            old,
            pack_id=pack_id,
            level_id=level_id,
            completed=True,
            plays=old.plays + 1,
            first_completed_at=old.first_completed_at or run.finished_at,
        )
        if run.assisted:
            self.levels[level_hash] = record
            return RecordUpdate(record, 0, False, False, False, False)

        stars = compute_stars(run.moves, run.pushes, par)
        solution = BestSolution(moves=run.moves, pushes=run.pushes, lurd=run.lurd)
        new_moves = _better_moves(solution, old.best_moves)
        new_pushes = _better_pushes(solution, old.best_pushes)
        new_time = old.best_time_ms is None or run.elapsed_ms < old.best_time_ms
        record = replace(
            record,
            stars=max(old.stars, stars),
            best_moves=solution if new_moves else old.best_moves,
            best_pushes=solution if new_pushes else old.best_pushes,
            best_time_ms=run.elapsed_ms if new_time else old.best_time_ms,
        )
        self.levels[level_hash] = record
        return RecordUpdate(record, stars, new_moves, new_pushes, new_time, beats_par_moves(run.moves, par))

    def set_last_played(self, lp: LastPlayed) -> None:
        self.last_played = lp

    def completed_count(self, level_hashes: Iterable[str]) -> int:
        """How many distinct levels among ``level_hashes`` are completed (assisted or not)."""
        return sum(1 for h in set(level_hashes) if (rec := self.levels.get(h)) is not None and rec.completed)

    def reset(self) -> None:
        self.levels.clear()
        self.last_played = None

    def to_dict(self) -> dict[str, object]:
        """Plain JSON data (spec 9.4), without ``format``/``version``."""
        lp = self.last_played
        return {
            "levels": {h: _record_to_dict(rec) for h, rec in self.levels.items()},
            "last_played": None
            if lp is None
            else {"pack_id": lp.pack_id, "level_id": lp.level_id, "level_hash": lp.level_hash},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Progress:
        """Lenient load: unusable records are skipped and invalid fields fall back to their defaults."""
        levels: dict[str, LevelRecord] = {}
        raw_levels = data.get("levels")
        if isinstance(raw_levels, Mapping):
            for key, raw in raw_levels.items():
                record = _record_from(raw) if isinstance(key, str) and _LEVEL_HASH.fullmatch(key) else None
                if record is None:
                    _log.warning("progress: skipped an unusable level record")
                    continue
                levels[key] = record
        return cls(levels, _last_played_from(data.get("last_played")))


def _solution_to_dict(sol: BestSolution | None) -> dict[str, object] | None:
    return None if sol is None else {"moves": sol.moves, "pushes": sol.pushes, "lurd": sol.lurd}


def _record_to_dict(rec: LevelRecord) -> dict[str, object]:
    return {
        "pack_id": rec.pack_id,
        "level_id": rec.level_id,
        "completed": rec.completed,
        "stars": rec.stars,
        "plays": rec.plays,
        "first_completed_at": rec.first_completed_at,
        "best_moves": _solution_to_dict(rec.best_moves),
        "best_pushes": _solution_to_dict(rec.best_pushes),
        "best_time_ms": rec.best_time_ms,
    }


def _count(value: object) -> int | None:
    """A non-negative int (bools excluded), else ``None``."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _solution_from(raw: object) -> BestSolution | None:
    if not isinstance(raw, Mapping):
        return None
    moves, pushes, lurd = _count(raw.get("moves")), _count(raw.get("pushes")), raw.get("lurd")
    if moves is None or pushes is None or not isinstance(lurd, str):
        return None
    return BestSolution(moves=moves, pushes=pushes, lurd=lurd)


def _record_from(raw: object) -> LevelRecord | None:
    if not isinstance(raw, Mapping):
        return None
    pack_id, level_id = raw.get("pack_id"), raw.get("level_id")
    if not isinstance(pack_id, str) or not isinstance(level_id, str):
        return None
    completed = raw.get("completed")
    stars = _count(raw.get("stars"))
    first = raw.get("first_completed_at")
    return LevelRecord(
        pack_id=pack_id,
        level_id=level_id,
        completed=completed if isinstance(completed, bool) else False,
        stars=stars if stars is not None and stars <= 3 else 0,
        plays=_count(raw.get("plays")) or 0,
        first_completed_at=first if isinstance(first, str) else None,
        best_moves=_solution_from(raw.get("best_moves")),
        best_pushes=_solution_from(raw.get("best_pushes")),
        best_time_ms=_count(raw.get("best_time_ms")),
    )


def _last_played_from(raw: object) -> LastPlayed | None:
    if not isinstance(raw, Mapping):
        return None
    pack_id, level_id, level_hash = raw.get("pack_id"), raw.get("level_id"), raw.get("level_hash")
    if not (isinstance(pack_id, str) and isinstance(level_id, str) and isinstance(level_hash, str)):
        return None
    return LastPlayed(pack_id=pack_id, level_id=level_id, level_hash=level_hash)
