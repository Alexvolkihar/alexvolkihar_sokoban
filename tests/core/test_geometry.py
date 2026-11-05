import pytest

from alexvolkihar_sokoban.core.geometry import Direction, step


def test_direction_deltas_are_row_col() -> None:
    assert (Direction.UP.dr, Direction.UP.dc) == (-1, 0)
    assert (Direction.DOWN.dr, Direction.DOWN.dc) == (1, 0)
    assert (Direction.LEFT.dr, Direction.LEFT.dc) == (0, -1)
    assert (Direction.RIGHT.dr, Direction.RIGHT.dc) == (0, 1)


def test_direction_chars_and_from_char_case_insensitive() -> None:
    assert [d.char for d in Direction] == ["u", "d", "l", "r"]
    for d in Direction:
        assert Direction.from_char(d.char) is d
        assert Direction.from_char(d.char.upper()) is d


@pytest.mark.parametrize("bad", ["x", "", "ud", " "])
def test_from_char_rejects_other_text(bad: str) -> None:
    with pytest.raises(ValueError):
        Direction.from_char(bad)


def test_step_moves_one_cell() -> None:
    assert step((4, 1), Direction.UP) == (3, 1)
    assert step((4, 1), Direction.RIGHT) == (4, 2)
    assert step((0, 0), Direction.LEFT) == (0, -1)
