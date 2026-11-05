"""``generate [--preset medium] [--seed N] [--out FILE]``: a random level validated by the solver (spec 7.8).

Without ``--out`` the level is printed as XSB on stdout; with it, the file format follows the extension
(``.json`` keeps the par and the seed). A summary line (id, pushes, moves, attempts) goes to stderr. Exit
code: 0 done, 1 no level within the preset's attempts, 2 unwritable file or unknown extension,
130 interrupted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alexvolkihar_sokoban.core.pack import Pack
from alexvolkihar_sokoban.formats import FormatError, xsb
from alexvolkihar_sokoban.formats.detect import save_any
from alexvolkihar_sokoban.generator.api import GenerationFailed, generate
from alexvolkihar_sokoban.generator.presets import DEFAULT_PRESET, PRESETS

PROG = "alexvolkihar-sokoban generate"


def _seed(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0: {text}")
    return value


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--preset",
        choices=tuple(PRESETS),
        default=DEFAULT_PRESET,
        help=f"difficulty (default: {DEFAULT_PRESET})",
    )
    parser.add_argument(
        "--seed", type=_seed, default=None, metavar="N", help="seed of a reproducible level (default: random)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="FILE",
        help="write .json, .xsb, .sok or .txt (default: XSB on stdout)",
    )


def run(args: argparse.Namespace) -> int:
    try:
        result = generate(args.preset, args.seed)
    except GenerationFailed as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    entry = result.entry
    pack = Pack(id="generated", title=entry.id, levels=(entry,))
    if args.out is None:
        sys.stdout.write(xsb.dump(pack))
    else:
        try:
            save_any(pack, args.out)
        except FormatError as exc:
            print(f"{PROG}: {exc}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"{PROG}: cannot write {args.out}: {exc.strerror or exc}", file=sys.stderr)
            return 2
    par = entry.par
    summary = f"{entry.id}: {par.pushes} pushes, {par.moves} moves" if par is not None else entry.id
    print(f"{summary} ({result.attempts} attempt(s))", file=sys.stderr)
    return 0
