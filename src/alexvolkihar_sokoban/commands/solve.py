"""``solve PATH [--level ID] [--time-limit S] [--max-nodes N] [--mode optimal|fast]`` (spec 10).

Prints one ``key: value`` line per field (level, status, pushes, moves, nodes, time, lurd; the solution
fields only when solved). Exit code: 0 solved, 1 unsolvable, 2 unreadable file or unknown level,
3 limit reached or cancelled.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alexvolkihar_sokoban.formats import FormatError
from alexvolkihar_sokoban.formats.detect import FORMATS, load_any
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveStatus, solve

EXIT_CODES = {SolveStatus.SOLVED: 0, SolveStatus.UNSOLVABLE: 1, SolveStatus.INVALID: 2}
EXIT_LIMIT = 3


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
    defaults = SolveLimits()
    parser.add_argument("path", type=Path, metavar="PATH", help="level file (XSB/SOK, legacy or JSON)")
    parser.add_argument("--level", metavar="ID", default=None, help="level id in the file (default: first)")
    parser.add_argument(
        "--time-limit",
        type=_positive_float,
        default=defaults.time_s,
        metavar="S",
        help=f"seconds before giving up (default: {defaults.time_s:g})",
    )
    parser.add_argument(
        "--max-nodes",
        type=_positive_int,
        default=defaults.max_nodes,
        metavar="N",
        help=f"expanded states before giving up (default: {defaults.max_nodes})",
    )
    parser.add_argument(
        "--mode",
        choices=("optimal", "fast"),
        default="optimal",
        help="optimal: fewest pushes; fast: quicker, longer solutions (default: optimal)",
    )
    parser.add_argument(
        "--format", choices=FORMATS, default="auto", help="format of PATH (default: detected from the file)"
    )


def run(args: argparse.Namespace) -> int:
    prog = "alexvolkihar-sokoban solve"
    try:
        pack, warnings = load_any(args.path, fmt=args.format)
    except FormatError as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    level_id = pack.levels[0].id if args.level is None else args.level
    try:
        entry = pack.entry(level_id)
    except KeyError:
        known = ", ".join(e.id for e in pack.levels)
        print(f"{prog}: no level {level_id!r} in {args.path} (levels: {known})", file=sys.stderr)
        return 2

    limits = SolveLimits(time_s=args.time_limit, max_nodes=args.max_nodes)
    result = solve(entry.level, limits=limits, mode=args.mode)
    print(f"level: {pack.id}/{entry.id}")
    print(f"status: {result.status}")
    if result.lurd is not None:
        print(f"pushes: {result.pushes}")
        print(f"moves: {result.moves}")
    print(f"nodes: {result.nodes_expanded} expanded, {result.nodes_generated} generated")
    print(f"time: {result.elapsed_ms} ms")
    if result.lurd is not None:
        print(f"lurd: {result.lurd}")
    return EXIT_CODES.get(result.status, EXIT_LIMIT)
