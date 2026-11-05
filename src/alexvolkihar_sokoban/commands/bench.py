"""``bench`` subcommand (stub until its task lands)."""

from __future__ import annotations

import argparse

from alexvolkihar_sokoban.commands._stub import not_implemented


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> int:
    return not_implemented("bench")
