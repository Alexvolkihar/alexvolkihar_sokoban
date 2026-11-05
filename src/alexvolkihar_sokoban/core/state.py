"""Mutable play state over an immutable ``Level``: moves, pushes, undo/redo (spec 7.2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step
from alexvolkihar_sokoban.core.level import Level


class MoveOutcome(Enum):
    MOVED = "moved"
    PUSHED = "pushed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Step:
    direction: Direction
    pushed: bool


def _char(s: Step) -> str:
    return s.direction.char.upper() if s.pushed else s.direction.char


class GameState:
    """Player position, box set and history of one attempt at a level.

    ``moves`` and ``pushes`` count the steps of the current history: undo decreases them.
    """

    def __init__(self, level: Level) -> None:
        self.level = level
        self.player: Pos = level.player
        self.boxes: frozenset[Pos] = level.boxes
        self._history: list[Step] = []
        self._redo: list[Step] = []  # last element = next step to redo

    @property
    def moves(self) -> int:
        return len(self._history)

    @property
    def pushes(self) -> int:
        return sum(1 for s in self._history if s.pushed)

    @property
    def is_solved(self) -> bool:
        return self.boxes == self.level.goals

    @property
    def history(self) -> tuple[Step, ...]:
        return tuple(self._history)

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def lurd(self) -> str:
        return "".join(_char(s) for s in self._history)

    @property
    def redo_lurd(self) -> str:
        """Steps that redo would replay, next one first."""
        return "".join(_char(s) for s in reversed(self._redo))

    def _apply(self, d: Direction) -> Step | None:
        target = step(self.player, d)
        if not self.level.is_floor(target):
            return None
        if target in self.boxes:
            beyond = step(target, d)
            if not self.level.is_floor(beyond) or beyond in self.boxes:
                return None
            self.boxes = (self.boxes - {target}) | {beyond}
            self.player = target
            return Step(d, True)
        self.player = target
        return Step(d, False)

    def move(self, d: Direction) -> MoveOutcome:
        """Walk or push one cell. A blocked move changes nothing; any other move clears the redo stack."""
        done = self._apply(d)
        if done is None:
            return MoveOutcome.BLOCKED
        self._history.append(done)
        self._redo.clear()
        return MoveOutcome.PUSHED if done.pushed else MoveOutcome.MOVED

    def undo(self) -> Step | None:
        if not self._history:
            return None
        last = self._history.pop()
        d = last.direction
        previous = (self.player[0] - d.dr, self.player[1] - d.dc)
        if last.pushed:
            self.boxes = (self.boxes - {step(self.player, d)}) | {self.player}
        self.player = previous
        self._redo.append(last)
        return last

    def redo(self) -> Step | None:
        if not self._redo:
            return None
        nxt = self._redo.pop()
        done = self._apply(nxt.direction)
        if done != nxt:  # cannot happen: the state is the one the step was undone from
            raise RuntimeError("redo stack out of sync with the state")
        self._history.append(nxt)
        return nxt

    def restart(self) -> None:
        self.player = self.level.player
        self.boxes = self.level.boxes
        self._history.clear()
        self._redo.clear()

    def signature(self) -> tuple[Pos, frozenset[Pos]]:
        return (self.player, self.boxes)
