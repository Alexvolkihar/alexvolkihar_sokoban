import pytest

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.lurd import LurdError, encode, replay, restore, step_char
from alexvolkihar_sokoban.core.state import GameState, Step

TEST1 = ["######", "#.  .#", "#    #", "# $$ #", "#@   #", "######"]


def test_step_char_lowercase_walk_uppercase_push() -> None:
    assert step_char(Step(Direction.LEFT, False)) == "l"
    assert step_char(Step(Direction.UP, True)) == "U"


def test_encode() -> None:
    steps = [Step(Direction.RIGHT, False), Step(Direction.UP, True), Step(Direction.DOWN, False)]
    assert encode(steps) == "rUd"
    assert encode([]) == ""


def test_lurd_encode_and_replay() -> None:
    s = replay(Level.from_rows(TEST1), "rU")
    assert isinstance(s, GameState)
    assert s.lurd == "rU" and s.pushes == 1 and s.boxes == {(2, 2), (3, 3)}


def test_replay_solves_test1() -> None:
    # Solution found by the original LAMA solver, normalised to LURD case.
    s = replay(Level.from_rows(TEST1), "rUUdRdrUUluL")
    assert s.is_solved and (s.moves, s.pushes) == (12, 6)


def test_replay_rejects_case_mismatch() -> None:
    lv = Level.from_rows(TEST1)
    with pytest.raises(LurdError):
        replay(lv, "ru")  # u would push
    with pytest.raises(LurdError):
        replay(lv, "R")  # R would not push
    s = replay(lv, "ru", strict_case=False)
    assert s.lurd == "rU"


def test_replay_rejects_blocked_steps_and_unknown_characters() -> None:
    lv = Level.from_rows(TEST1)
    with pytest.raises(LurdError):
        replay(lv, "l")  # wall
    with pytest.raises(LurdError):
        replay(lv, "rx")


def test_replay_ignores_whitespace() -> None:
    assert replay(Level.from_rows(TEST1), "r U\n").lurd == "rU"


def test_lurd_error_is_a_value_error() -> None:
    assert issubclass(LurdError, ValueError)


def test_restore_rebuilds_redo_stack() -> None:
    lv = Level.from_rows(TEST1)
    s = restore(lv, "rU", "dl")
    assert s.lurd == "rU" and s.redo_lurd == "dl"
    s.redo()
    assert s.lurd == "rUd" and s.redo_lurd == "l"


def test_restore_rejects_an_illegal_redo_tail() -> None:
    with pytest.raises(LurdError):
        restore(Level.from_rows(TEST1), "rU", "Dl")  # D would not push after rU
