"""Positions and directions. Coordinates are ``(row, col)``, row 0 at the top, col 0 at the left."""

from __future__ import annotations

from enum import Enum

Pos = tuple[int, int]

_CHARS = {"u": "UP", "d": "DOWN", "l": "LEFT", "r": "RIGHT"}


class Direction(Enum):
    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def dr(self) -> int:
        row_delta: int = self.value[0]
        return row_delta

    @property
    def dc(self) -> int:
        col_delta: int = self.value[1]
        return col_delta

    @property
    def char(self) -> str:
        """Lower-case LURD letter: ``u``, ``d``, ``l`` or ``r``."""
        return self.name[0].lower()

    @classmethod
    def from_char(cls, c: str) -> Direction:
        """Direction of a LURD letter, case-insensitive. Raises ``ValueError`` for anything else."""
        name = _CHARS.get(c.lower()) if len(c) == 1 else None
        if name is None:
            raise ValueError(f"not a direction letter: {c!r}")
        return cls[name]


def step(pos: Pos, d: Direction) -> Pos:
    """The neighbouring cell of ``pos`` in direction ``d``."""
    return (pos[0] + d.dr, pos[1] + d.dc)
