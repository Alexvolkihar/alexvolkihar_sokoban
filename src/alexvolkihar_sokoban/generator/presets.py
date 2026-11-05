"""Generator difficulty presets (spec 7.8)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from alexvolkihar_sokoban.solver.api import SolveLimits


@dataclass(frozen=True)
class Preset:
    """A ``width × height`` rectangle (walls included) holding ``boxes`` boxes.

    ``pull_steps`` bounds the reverse play (pulls in a row); a level is accepted when the solver, within
    ``limits``, needs at least ``min_pushes`` pushes; the generator gives up after ``max_attempts`` rejected
    candidates.
    """

    id: str
    width: int
    height: int
    boxes: int
    min_pushes: int
    pull_steps: int
    limits: SolveLimits
    max_attempts: int


PRESETS: Mapping[str, Preset] = MappingProxyType(
    {
        "easy": Preset("easy", 7, 7, 2, 6, 60, SolveLimits(time_s=2.0, max_nodes=200_000), 50),
        "medium": Preset("medium", 8, 8, 3, 12, 120, SolveLimits(time_s=4.0, max_nodes=400_000), 50),
        "hard": Preset("hard", 10, 9, 4, 20, 200, SolveLimits(time_s=8.0, max_nodes=800_000), 50),
    }
)
DEFAULT_PRESET = "medium"
