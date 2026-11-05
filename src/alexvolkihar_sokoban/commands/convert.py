"""``convert IN OUT [--format auto|xsb|legacy|json]``: convert levels between XSB, legacy and JSON (spec 7.3).

The output format comes from OUT's extension: ``.json`` for a JSON pack, ``.xsb``/``.sok``/``.txt`` for XSB.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alexvolkihar_sokoban.formats import FormatError
from alexvolkihar_sokoban.formats.detect import FORMATS, load_any, save_any


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, metavar="IN", help="level file to read")
    parser.add_argument("output", type=Path, metavar="OUT", help="file to write (.json, .xsb, .sok or .txt)")
    parser.add_argument(
        "--format",
        choices=FORMATS,
        default="auto",
        help="format of IN (default: detected from the file)",
    )


def run(args: argparse.Namespace) -> int:
    try:
        pack, warnings = load_any(args.input, fmt=args.format)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        save_any(pack, args.output)
    except FormatError as exc:
        print(f"alexvolkihar-sokoban convert: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(
            f"alexvolkihar-sokoban convert: cannot write {args.output}: {exc.strerror or exc}",
            file=sys.stderr,
        )
        return 1
    print(f"{args.output}: {len(pack.levels)} level(s)")
    return 0
