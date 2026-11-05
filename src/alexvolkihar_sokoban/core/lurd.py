"""LURD notation: ``l u r d`` for walking steps, ``L U R D`` for pushes (spec 7.2)."""

from __future__ import annotations

from collections.abc import Iterable

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.state import GameState, MoveOutcome, Step


class LurdError(ValueError):
    """An illegal, blocked or mismatched step in a LURD string."""


def step_char(step: Step) -> str:
    return step.direction.char.upper() if step.pushed else step.direction.char


def encode(steps: Iterable[Step]) -> str:
    return "".join(step_char(s) for s in steps)


def _play(state: GameState, text: str, strict_case: bool) -> None:
    index = 0
    for ch in text:
        if ch.isspace():
            continue
        try:
            d = Direction.from_char(ch)
        except ValueError:
            raise LurdError(f"not a LURD character: {ch!r} at step {index}") from None
        outcome = state.move(d)
        if outcome is MoveOutcome.BLOCKED:
            raise LurdError(f"step {index} ({ch!r}) is blocked")
        if strict_case and (outcome is MoveOutcome.PUSHED) != ch.isupper():
            expected = "a push" if ch.isupper() else "a walk"
            raise LurdError(f"step {index} ({ch!r}) should be {expected}")
        index += 1


def replay(level: Level, text: str, *, strict_case: bool = True) -> GameState:
    """Play ``text`` from the level's start; whitespace is ignored.

    Raises ``LurdError`` on an unknown character or a blocked step, and, when ``strict_case`` is true, on a
    lower-case step that pushes or an upper-case step that does not.
    """
    state = GameState(level)
    _play(state, text, strict_case)
    return state


def restore(level: Level, lurd: str, redo_lurd: str) -> GameState:
    """Rebuild a saved state: ``lurd`` is the history, ``redo_lurd`` the redo stack (next redo first)."""
    state = replay(level, lurd)
    before = state.moves
    _play(state, redo_lurd, strict_case=True)
    for _ in range(state.moves - before):
        state.undo()
    return state
