"""``generate``: seeded, solver-validated random levels (spec 7.8).

Every attempt carves a room, puts the boxes on random goals, plays backwards, then asks the solver for a
push-optimal solution; the first level needing at least ``min_pushes`` pushes is accepted with its par. The
same preset and seed give the same level as long as no attempt depends on the solver's time limit.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Par
from alexvolkihar_sokoban.generator.carve import carve_room
from alexvolkihar_sokoban.generator.presets import PRESETS, Preset
from alexvolkihar_sokoban.generator.reverse import reverse_play
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveResult, SolveStatus, solve

SolveFn = Callable[..., SolveResult]
SEED_LIMIT = 2**31
"""Seeds drawn when none is given are in ``range(SEED_LIMIT)``."""


class GenerationFailed(RuntimeError):
    """No candidate passed the solver within the preset's ``max_attempts``."""


class GenerationCancelled(GenerationFailed):
    """``should_stop`` asked to stop (or the solver was cancelled) before a level was accepted."""


@dataclass(frozen=True)
class GeneratedLevel:
    entry: LevelEntry
    attempts: int
    """Candidates tried, the accepted one included."""


def preset_of(preset: Preset | str) -> Preset:
    """The preset itself, or the named one. Raises ``ValueError`` for an unknown name."""
    if isinstance(preset, Preset):
        return preset
    try:
        return PRESETS[preset]
    except KeyError:
        raise ValueError(f"unknown preset {preset!r} (known: {', '.join(PRESETS)})") from None


def _rows(
    height: int, width: int, floor: frozenset[Pos], goals: frozenset[Pos], boxes: frozenset[Pos], player: Pos
) -> list[str]:
    """XSB rows; only walls touching the floor (corners included) are drawn, the rest is outside."""
    rows = []
    for r in range(height):
        chars = []
        for c in range(width):
            pos = (r, c)
            if pos in floor:
                if pos in boxes:
                    chars.append("*" if pos in goals else "$")
                elif pos == player:
                    chars.append("+" if pos in goals else "@")
                else:
                    chars.append("." if pos in goals else " ")
            elif any((r + dr, c + dc) in floor for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
                chars.append("#")
            else:
                chars.append(" ")
        rows.append("".join(chars))
    return rows


def _can_leave(pos: Pos, floor: frozenset[Pos]) -> bool:
    """A box on ``pos`` can be pulled off it: two floor cells in a row next to it."""
    return any(step(pos, d) in floor and step(step(pos, d), d) in floor for d in Direction)


def _candidate(rng: random.Random, preset: Preset) -> Level | None:
    """One random level, or ``None`` when this attempt cannot give a playable start."""
    floor = carve_room(rng, preset.width, preset.height)
    cells = sorted(floor)
    exits = [pos for pos in cells if _can_leave(pos, floor)]
    if len(exits) < preset.boxes or len(cells) <= preset.boxes:
        return None
    goals = frozenset(rng.sample(exits, preset.boxes))
    start = rng.choice([pos for pos in cells if pos not in goals])
    boxes, player = reverse_play(rng, floor, goals, start, preset.pull_steps)
    if boxes == goals:
        return None
    return Level.from_rows(_rows(preset.height, preset.width, floor, goals, boxes, player))


def generate(
    preset: Preset | str,
    seed: int | None = None,
    *,
    solve_fn: SolveFn = solve,
    should_stop: Callable[[], bool] | None = None,
) -> GeneratedLevel:
    """A level of ``preset`` from ``seed`` (a random seed when ``None``, recorded in the entry).

    The entry id is ``"<preset id>-<seed>"`` and its par comes from the solver. Raises ``ValueError`` for
    an unknown preset name, ``GenerationCancelled`` when ``should_stop`` returns true (checked before each
    attempt and passed to the solver), ``GenerationFailed`` after ``max_attempts`` rejected candidates.
    """
    chosen = preset_of(preset)
    if seed is None:
        seed = random.SystemRandom().randrange(SEED_LIMIT)
    rng = random.Random(seed)
    for attempt in range(1, chosen.max_attempts + 1):
        if should_stop is not None and should_stop():
            raise GenerationCancelled("generation cancelled")
        level = _candidate(rng, chosen)
        if level is None:
            continue
        result = solve_fn(level, limits=chosen.limits, mode="optimal", should_stop=should_stop)
        if result.status is SolveStatus.CANCELLED:
            raise GenerationCancelled("generation cancelled")
        if (
            result.status is SolveStatus.SOLVED
            and result.lurd is not None
            and result.pushes is not None
            and result.moves is not None
            and result.pushes >= chosen.min_pushes
        ):
            par = Par(pushes=result.pushes, moves=result.moves, lurd=result.lurd, solver=SOLVER_ID)
            entry = LevelEntry(id=f"{chosen.id}-{seed}", level=level, par=par, seed=seed)
            return GeneratedLevel(entry=entry, attempts=attempt)
    raise GenerationFailed(
        f"no {chosen.id} level with {chosen.min_pushes}+ pushes after {chosen.max_attempts} attempts"
    )
