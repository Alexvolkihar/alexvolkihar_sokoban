import pytest

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.scoring.stars import beats_par_moves, compute_stars

PAR = Par(pushes=8, moves=30, lurd="", solver="push-astar/1")


def test_stars() -> None:
    assert compute_stars(30, 8, PAR) == 3 and compute_stars(31, 8, PAR) == 2
    assert compute_stars(99, 10, PAR) == 2 and compute_stars(99, 11, PAR) == 1  # ceil(1.25*8) = 10
    assert compute_stars(5, 1, None) == 1


def test_three_stars_needs_both_pushes_and_moves_at_par() -> None:
    assert compute_stars(20, 9, PAR) == 2  # fewer moves but one push too many
    assert compute_stars(20, 7, PAR) == 3  # beating par on both


@pytest.mark.parametrize(
    ("par_pushes", "two_star_limit"),
    [(1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 9), (8, 10), (9, 12), (0, 0)],
)
def test_two_star_limit_is_ceil_of_one_and_a_quarter(par_pushes: int, two_star_limit: int) -> None:
    par = Par(pushes=par_pushes, moves=0, lurd="", solver="push-astar/1")
    assert compute_stars(1000, two_star_limit, par) == 2
    assert compute_stars(1000, two_star_limit + 1, par) == 1


def test_beats_par_moves() -> None:
    assert beats_par_moves(29, PAR)
    assert not beats_par_moves(30, PAR)
    assert not beats_par_moves(1, None)
