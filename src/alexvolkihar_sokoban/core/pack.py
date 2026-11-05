"""Level packs: the data model shared by formats, UI, scoring and benchmarks (no I/O here)."""

from __future__ import annotations

from dataclasses import dataclass

from alexvolkihar_sokoban.core.level import Level


@dataclass(frozen=True)
class Par:
    """Reference solution from the solver (push-optimal, spec 7.5)."""

    pushes: int
    moves: int
    lurd: str
    solver: str


@dataclass(frozen=True)
class LevelEntry:
    id: str
    level: Level
    par: Par | None = None
    seed: int | None = None

    @property
    def title(self) -> str:
        """The level's own title, or its id when it has none."""
        return self.level.title or self.id


@dataclass(frozen=True)
class Pack:
    id: str
    title: str
    levels: tuple[LevelEntry, ...]
    author: str = ""
    license: str = ""
    source: str = ""
    hidden: bool = False

    def index_of(self, level_id: str) -> int:
        """Position of a level in the pack. Raises ``KeyError`` for an unknown id."""
        for i, entry in enumerate(self.levels):
            if entry.id == level_id:
                return i
        raise KeyError(level_id)

    def entry(self, level_id: str) -> LevelEntry:
        """The level with this id. Raises ``KeyError`` for an unknown id."""
        return self.levels[self.index_of(level_id)]

    def next_id(self, level_id: str) -> str | None:
        """Id of the level after ``level_id``, ``None`` after the last one. ``KeyError`` for an unknown id."""
        i = self.index_of(level_id) + 1
        return self.levels[i].id if i < len(self.levels) else None
