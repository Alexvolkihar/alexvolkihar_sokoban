"""``annotate PACK.json [--time-limit S] [--max-nodes N] [--force]`` (spec 8, 10).

Solves the levels of a JSON pack and stores each solution as the level's ``par``, rewriting the file in place.
Levels that already have a par are skipped unless ``--force``; a level the solver cannot solve within the
limits keeps its par (``null`` when it had none). The file must be a JSON pack whose every level is valid:
rewriting it must never drop a level. Ctrl+C writes the levels finished so far and exits with code 130.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path

from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.formats import FormatError, jsonfmt
from alexvolkihar_sokoban.formats.detect import save_any
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveLimits, SolveResult, SolveStatus, solve

PROG = "alexvolkihar-sokoban annotate"
DEFAULT_TIME_S = 60.0
DEFAULT_MAX_NODES = 5_000_000
EXIT_INTERRUPTED = 130

LevelCallback = Callable[[LevelEntry, SolveResult], None]


def _with_result(entry: LevelEntry, result: SolveResult) -> LevelEntry:
    """``entry`` with the solver's solution as its par; unchanged when the solver found none."""
    if result.status is not SolveStatus.SOLVED or result.lurd is None:
        return entry
    assert result.pushes is not None and result.moves is not None
    par = Par(pushes=result.pushes, moves=result.moves, lurd=result.lurd, solver=SOLVER_ID)
    return dataclasses.replace(entry, par=par)


def _apply(pack: Pack, results: dict[str, SolveResult]) -> Pack:
    levels = tuple(_with_result(e, results[e.id]) if e.id in results else e for e in pack.levels)
    return dataclasses.replace(pack, levels=levels)


def annotate_pack(
    pack: Pack,
    limits: SolveLimits,
    *,
    only_missing: bool = True,
    on_level: LevelCallback | None = None,
) -> Pack:
    """``pack`` with a par for every level the solver solves (push-optimal mode, ``limits`` per level).

    Levels with a par are skipped when ``only_missing``. ``on_level`` is called after each solved attempt.
    """
    results: dict[str, SolveResult] = {}
    for entry in pack.levels:
        if only_missing and entry.par is not None:
            continue
        result = solve(entry.level, limits=limits, mode="optimal")
        results[entry.id] = result
        if on_level is not None:
            on_level(entry, result)
    return _apply(pack, results)


def _positive_float(text: str) -> float:
    value = float(text)
    if not value > 0:
        raise argparse.ArgumentTypeError(f"must be > 0: {text}")
    return value


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1: {text}")
    return value


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, metavar="PACK.json", help="JSON level pack, rewritten in place")
    parser.add_argument(
        "--time-limit",
        type=_positive_float,
        default=DEFAULT_TIME_S,
        metavar="S",
        help=f"seconds per level before giving up (default: {DEFAULT_TIME_S:g})",
    )
    parser.add_argument(
        "--max-nodes",
        type=_positive_int,
        default=DEFAULT_MAX_NODES,
        metavar="N",
        help=f"expanded states per level before giving up (default: {DEFAULT_MAX_NODES})",
    )
    parser.add_argument("--force", action="store_true", help="also recompute levels that already have a par")


def _load(path: Path) -> Pack:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise FormatError(f"cannot read the file ({exc})", path=path) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FormatError(f"invalid JSON: {exc.msg}", path=path, line=exc.lineno) from exc
    if not isinstance(data, dict) or data.get("format") != jsonfmt.PACK_FORMAT:
        raise FormatError(f"not a level pack (format {jsonfmt.PACK_FORMAT!r} expected)", path=path)
    try:
        return jsonfmt.pack_from_dict(data)
    except FormatError as exc:
        raise FormatError(exc.reason, path=path) from exc


def _describe(entry: LevelEntry, result: SolveResult) -> str:
    if result.status is SolveStatus.SOLVED:
        return f"{entry.id}: solved, {result.pushes} pushes, {result.moves} moves, {result.elapsed_ms} ms"
    kept = "par kept" if entry.par is not None else "no par"
    return f"{entry.id}: {result.status}, {result.nodes_expanded} nodes, {result.elapsed_ms} ms ({kept})"


def _save(pack: Pack, path: Path) -> bool:
    try:
        save_any(pack, path)
    except OSError as exc:
        print(f"{PROG}: cannot write {path}: {exc}", file=sys.stderr)
        return False
    return True


def run(args: argparse.Namespace) -> int:
    path: Path = args.path
    try:
        pack = _load(path)
    except FormatError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 2
    limits = SolveLimits(time_s=args.time_limit, max_nodes=args.max_nodes)
    results: dict[str, SolveResult] = {}

    def report(entry: LevelEntry, result: SolveResult) -> None:
        results[entry.id] = result
        print(_describe(entry, result), flush=True)

    try:
        annotated = annotate_pack(pack, limits, only_missing=not args.force, on_level=report)
    except KeyboardInterrupt:
        print(f"{PROG}: interrupted, saving the {len(results)} level(s) done", file=sys.stderr)
        _save(_apply(pack, results), path)
        return EXIT_INTERRUPTED
    if not _save(annotated, path):
        return 2
    with_par = sum(entry.par is not None for entry in annotated.levels)
    print(f"{pack.id}: {with_par} of {len(annotated.levels)} levels have a par")
    return 0
