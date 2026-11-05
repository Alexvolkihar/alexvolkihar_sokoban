"""Stars for a completed, non-assisted run, relative to the solver's par (spec 7.5)."""

from __future__ import annotations

from alexvolkihar_sokoban.core.pack import Par


def two_star_pushes(par: Par) -> int:
    """Most pushes still worth 2 stars: ``ceil(1.25 * par.pushes)``, in exact integer arithmetic."""
    return (5 * par.pushes + 3) // 4


def compute_stars(moves: int, pushes: int, par: Par | None) -> int:
    """1 to 3 stars: 3 at par (pushes and moves), 2 within 25 % more pushes, 1 otherwise or without par."""
    if par is None:
        return 1
    if pushes <= par.pushes and moves <= par.moves:
        return 3
    if pushes <= two_star_pushes(par):
        return 2
    return 1


def beats_par_moves(moves: int, par: Par | None) -> bool:
    """True when the run used strictly fewer moves than the par ("better than par" badge)."""
    return par is not None and moves < par.moves
