"""Command-line dispatcher: each subcommand lives in ``commands/<name>.py``."""

from __future__ import annotations

import argparse
from types import ModuleType

from alexvolkihar_sokoban import __version__
from alexvolkihar_sokoban.commands import annotate, bench, convert, generate, play, solve

COMMANDS: dict[str, tuple[ModuleType, str]] = {
    "play": (play, "play a level file or open the main menu"),
    "solve": (solve, "solve a level with the push-based solver"),
    "convert": (convert, "convert levels between XSB, legacy and JSON formats"),
    "annotate": (annotate, "compute the par of every level of a JSON pack"),
    "bench": (bench, "run a solver benchmark suite"),
    "generate": (generate, "generate a random level validated by the solver"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alexvolkihar-sokoban",
        description="Alexvolkihar Sokoban, a remake of Sokoban-LAMA by the LAMA group.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--data-dir", metavar="PATH", default=None, help="override the data directory")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for name, (module, help_text) in COMMANDS.items():
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        module.add_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        # No subcommand: open the game on its main menu.
        play_parser = argparse.ArgumentParser(add_help=False)
        play.add_arguments(play_parser)
        args = play_parser.parse_args([], namespace=args)
        args.command = "play"
    module, _ = COMMANDS[args.command]
    result: int = module.run(args)
    return result
