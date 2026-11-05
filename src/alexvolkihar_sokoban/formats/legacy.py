"""The original Sokoban-LAMA level format: one level per file; `X` wall, `*` box, `.` goal, `@` player.

It has no symbol for a box or the player on a goal.
"""

from __future__ import annotations

from alexvolkihar_sokoban.core.level import InvalidLevelError, Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.formats import FormatError
from alexvolkihar_sokoban.formats.xsb import dedent, split_lines

_TO_XSB = str.maketrans({"X": "#", "*": "$"})


def parse(text: str, *, pack_id: str) -> Pack:
    """A one-level pack (level id ``"1"``). Raises ``FormatError`` when the level is missing or invalid."""
    rows = dedent([line.translate(_TO_XSB) for line in split_lines(text)])
    if not any(rows):
        raise FormatError("no level in the file")
    try:
        level = Level.from_rows(rows)
    except InvalidLevelError as exc:
        raise FormatError(str(exc)) from exc
    return Pack(id=pack_id, title=pack_id, levels=(LevelEntry("1", level),))
