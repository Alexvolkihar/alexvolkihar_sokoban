"""XSB/SOK reader and writer (spec 7.3).

A board line holds only ``# @ + $ * . - _ space``, run-length digits and ``|`` row separators, with at least
one of ``# @ + $ * .``. Any other line ends the current level: ``Title:``/``Author:``/``Comment:`` lines
(case-insensitive) describe the level just above them, or the pack when no board came yet; other lines,
including ``;`` comments, are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from alexvolkihar_sokoban.core.level import InvalidLevelError, Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack

TAB_SIZE = 8
METADATA_KEYS = ("title", "author", "comment")
_MARKS = frozenset("#@+$*.")
_BOARD_CHARS = frozenset("#@+$*.-_ 0123456789|")


def split_lines(text: str) -> list[str]:
    """Lines of ``text`` without a leading BOM, CRLF/CR as LF, tabs expanded, trailing spaces stripped."""
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    return [line.expandtabs(TAB_SIZE).rstrip(" ") for line in text.split("\n")]


def is_board_line(line: str) -> bool:
    return bool(line) and set(line) <= _BOARD_CHARS and not _MARKS.isdisjoint(line)


def expand_rle(line: str) -> list[str]:
    """Rows of a board line: ``4#`` repeats ``#`` four times and ``|`` starts a new row."""
    rows: list[str] = []
    row: list[str] = []
    count = ""
    for ch in line:
        if ch.isdigit():
            count += ch
        elif ch == "|":
            if count:
                raise InvalidLevelError("run-length count before '|'")
            rows.append("".join(row))
            row = []
        else:
            row.append(ch * int(count or "1"))
            count = ""
    if count:
        raise InvalidLevelError("run-length count without a character at the end of a row")
    rows.append("".join(row))
    return rows


def dedent(rows: list[str]) -> list[str]:
    """``-``/``_`` as spaces, then the indentation common to every non-empty row removed."""
    rows = [row.replace("-", " ").replace("_", " ") for row in rows]
    indents = [len(row) - len(row.lstrip(" ")) for row in rows if row.strip(" ")]
    cut = min(indents, default=0)
    return [row[cut:] for row in rows]


@dataclass
class _Block:
    line: int
    lines: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)


def parse(text: str, *, pack_id: str, pack_title: str = "") -> tuple[Pack, list[str]]:
    """Every level of an XSB/SOK text: a pack of the valid ones, and one warning per invalid one.

    Level ids are their 1-based position in the file, invalid levels included, so ids stay stable when a
    broken level is fixed.
    """
    header: dict[str, str] = {}
    blocks: list[_Block] = []
    in_board = False
    for number, line in enumerate(split_lines(text), start=1):
        if is_board_line(line):
            if not in_board:
                blocks.append(_Block(number))
                in_board = True
            blocks[-1].lines.append(line)
            continue
        in_board = False
        key, sep, value = line.strip().partition(":")
        key = key.strip().lower()
        if sep and key in METADATA_KEYS:
            target = blocks[-1].meta if blocks else header
            target.setdefault(key, value.strip())

    entries: list[LevelEntry] = []
    warnings: list[str] = []
    for index, block in enumerate(blocks, start=1):
        try:
            rows = dedent([row for line in block.lines for row in expand_rle(line)])
            level = Level.from_rows(
                rows,
                title=block.meta.get("title", ""),
                author=block.meta.get("author", ""),
                comment=block.meta.get("comment", ""),
            )
        except InvalidLevelError as exc:
            warnings.append(f"{pack_id} level {index} (line {block.line}): {exc}")
            continue
        entries.append(LevelEntry(str(index), level))
    pack = Pack(
        id=pack_id,
        title=header.get("title") or pack_title or pack_id,
        levels=tuple(entries),
        author=header.get("author", ""),
    )
    return pack, warnings


def _meta_line(key: str, value: str) -> str:
    return f"{key}: {' '.join(value.split())}"


def dump(pack: Pack) -> str:
    """Plain XSB: an optional pack header, then each level followed by its metadata lines."""
    blocks: list[str] = []
    header = [_meta_line(k, v) for k, v in (("Title", pack.title), ("Author", pack.author)) if v]
    if header:
        blocks.append("\n".join(header))
    for entry in pack.levels:
        level = entry.level
        lines = level.canonical_text().split("\n")
        meta = (("Title", level.title), ("Author", level.author), ("Comment", level.comment))
        lines += [_meta_line(k, v) for k, v in meta if v]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
