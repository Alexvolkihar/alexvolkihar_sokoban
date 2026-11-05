"""Immutable level description, XSB parsing, validation and canonical hash (spec 7.2)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step

WALL = "#"
PLAYER = "@"
PLAYER_ON_GOAL = "+"
BOX = "$"
BOX_ON_GOAL = "*"
GOAL = "."
FLOOR_CHARS = " -_"
XSB_CHARS = frozenset(WALL + PLAYER + PLAYER_ON_GOAL + BOX + BOX_ON_GOAL + GOAL + FLOOR_CHARS)


class InvalidLevelError(ValueError):
    """A level that cannot be played; the message is a human-readable reason."""


def _normalise_rows(rows: Sequence[str]) -> list[str]:
    """Floor characters become spaces, trailing spaces go, leading/trailing empty rows go."""
    clean = [row.replace("-", " ").replace("_", " ").rstrip(" ") for row in rows]
    while clean and not clean[0]:
        clean.pop(0)
    while clean and not clean[-1]:
        clean.pop()
    return clean


@dataclass(frozen=True)
class Level:
    width: int
    height: int
    walls: frozenset[Pos]
    goals: frozenset[Pos]
    boxes: frozenset[Pos]
    player: Pos
    floor: frozenset[Pos]
    title: str = ""
    author: str = ""
    comment: str = ""

    @classmethod
    def from_rows(cls, rows: Sequence[str], *, title: str = "", author: str = "", comment: str = "") -> Level:
        """Parse standard XSB rows (``# @ + $ * .`` and ``space - _`` as floor) and validate them.

        Raises ``InvalidLevelError`` when the level cannot be played.
        """
        grid = _normalise_rows(rows)
        walls: set[Pos] = set()
        goals: set[Pos] = set()
        boxes: set[Pos] = set()
        players: list[Pos] = []
        for r, row in enumerate(grid):
            for c, ch in enumerate(row):
                if ch not in XSB_CHARS:
                    raise InvalidLevelError(f"unknown character {ch!r} at row {r}, column {c}")
                pos = (r, c)
                if ch == WALL:
                    walls.add(pos)
                if ch in (GOAL, PLAYER_ON_GOAL, BOX_ON_GOAL):
                    goals.add(pos)
                if ch in (BOX, BOX_ON_GOAL):
                    boxes.add(pos)
                if ch in (PLAYER, PLAYER_ON_GOAL):
                    players.append(pos)
        height = len(grid)
        width = max((len(row) for row in grid), default=0)

        if len(players) != 1:
            raise InvalidLevelError(f"expected exactly one player, found {len(players)}")
        if len(boxes) != len(goals):
            raise InvalidLevelError(f"{len(boxes)} boxes but {len(goals)} goals")
        if not boxes:
            raise InvalidLevelError("a level needs at least one box")
        player = players[0]
        floor = _walkable_region(player, frozenset(walls), width, height)
        if floor is None:
            raise InvalidLevelError("the player's area is not enclosed by walls")
        if not (boxes | goals) <= floor:
            raise InvalidLevelError("every box and goal must lie on the floor of the player's area")
        if boxes == goals:
            raise InvalidLevelError("the level is already solved at the start")
        return cls(
            width=width,
            height=height,
            walls=frozenset(walls),
            goals=frozenset(goals),
            boxes=frozenset(boxes),
            player=player,
            floor=floor,
            title=title,
            author=author,
            comment=comment,
        )

    def is_wall(self, pos: Pos) -> bool:
        return pos in self.walls

    def is_floor(self, pos: Pos) -> bool:
        return pos in self.floor

    def to_rows(self, boxes: frozenset[Pos] | None = None, player: Pos | None = None) -> tuple[str, ...]:
        """XSB rows, ``width`` characters each, for the initial state or the given one.

        Cells outside the player's area are written as spaces.
        """
        box_set = self.boxes if boxes is None else boxes
        player_pos = self.player if player is None else player
        rows: list[str] = []
        for r in range(self.height):
            chars: list[str] = []
            for c in range(self.width):
                pos = (r, c)
                goal = pos in self.goals
                if pos in self.walls:
                    chars.append(WALL)
                elif pos == player_pos:
                    chars.append(PLAYER_ON_GOAL if goal else PLAYER)
                elif pos in box_set:
                    chars.append(BOX_ON_GOAL if goal else BOX)
                elif goal:
                    chars.append(GOAL)
                else:
                    chars.append(" ")
            rows.append("".join(chars))
        return tuple(rows)

    def canonical_text(self) -> str:
        """The initial state as XSB, rows right-stripped, outer empty rows dropped, joined by LF."""
        return "\n".join(_normalise_rows(self.to_rows()))

    def canonical_hash(self) -> str:
        """``"sha256:<hex>"`` of the UTF-8 canonical text: the level's identity in saves (spec 9.1)."""
        return "sha256:" + hashlib.sha256(self.canonical_text().encode("utf-8")).hexdigest()


def _walkable_region(start: Pos, walls: frozenset[Pos], width: int, height: int) -> frozenset[Pos] | None:
    """Non-wall cells reachable from ``start``, or ``None`` when the region leaves the grid."""
    seen = {start}
    todo = [start]
    while todo:
        pos = todo.pop()
        for d in Direction:
            nxt = step(pos, d)
            if nxt in seen or nxt in walls:
                continue
            if not (0 <= nxt[0] < height and 0 <= nxt[1] < width):
                return None
            seen.add(nxt)
            todo.append(nxt)
    return frozenset(seen)
