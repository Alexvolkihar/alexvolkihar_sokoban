"""``play [PATH] [--level ID]``: open the game (main menu when no path is given).

With ``PATH``, the file is read first (an unreadable file or an unknown level exits with code 2 before any
window opens), then the game opens on that level over the main menu, so Esc returns to the menu. pygame and
the ``ui`` package are imported inside ``run`` only: the other commands never load them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alexvolkihar_sokoban.core.pack import Pack
from alexvolkihar_sokoban.formats import FormatError
from alexvolkihar_sokoban.formats.detect import load_any
from alexvolkihar_sokoban.persistence.paths import data_dir

PROG = "alexvolkihar-sokoban play"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=None, help="level file or pack to play")
    parser.add_argument(
        "--level", metavar="ID", default=None, help="level id inside the file (default: first)"
    )


def _read_level(path: Path, level_id: str | None) -> tuple[Pack, str, list[str]] | None:
    try:
        pack, warnings = load_any(path)
    except FormatError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return None
    chosen = pack.levels[0].id if level_id is None else level_id
    try:
        pack.entry(chosen)
    except KeyError:
        known = ", ".join(e.id for e in pack.levels)
        print(f"{PROG}: no level {chosen!r} in {path} (levels: {known})", file=sys.stderr)
        return None
    return pack, chosen, warnings


def run(args: argparse.Namespace) -> int:
    opened: tuple[Pack, str, list[str]] | None = None
    if args.path is not None:
        opened = _read_level(Path(args.path), args.level)
        if opened is None:
            return 2

    from alexvolkihar_sokoban.ui.app import App
    from alexvolkihar_sokoban.ui.context import AppContext

    override = getattr(args, "data_dir", None)
    context = AppContext.load(data_dir(Path(override) if override else None))
    app = App(context.settings, context=context)
    app.push("main_menu")
    if opened is not None:
        pack, level_id, warnings = opened
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        # Shown by the main menu once the player is back on it.
        context.warnings.extend(f"{args.path}: {w}" for w in warnings)
        app.push("game", pack=pack, level_id=level_id)
    app.run()
    return 0
