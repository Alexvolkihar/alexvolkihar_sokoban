"""``play [PATH] [--level ID]``: open the game (main menu when no path is given)."""

from __future__ import annotations

import argparse

from alexvolkihar_sokoban.commands._stub import not_implemented


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=None, help="level file or pack to play")
    parser.add_argument("--level", metavar="ID", default=None, help="level id inside the file")


def run(args: argparse.Namespace) -> int:
    return not_implemented("play")
