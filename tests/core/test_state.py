from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.state import GameState, MoveOutcome, Step

TEST1 = ["######", "#.  .#", "#    #", "# $$ #", "#@   #", "######"]
U, D, L, R = Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT


def test_initial_state() -> None:
    lv = Level.from_rows(TEST1)
    s = GameState(lv)
    assert s.level is lv and s.player == lv.player and s.boxes == lv.boxes
    assert (s.moves, s.pushes, s.is_solved, s.history, s.lurd, s.redo_lurd) == (0, 0, False, (), "", "")
    assert not s.can_undo and not s.can_redo


def test_push_moves_box_and_counts() -> None:
    s = GameState(Level.from_rows(TEST1))
    assert s.move(R) is MoveOutcome.MOVED
    assert s.move(U) is MoveOutcome.PUSHED and s.boxes == {(2, 2), (3, 3)}
    assert (s.moves, s.pushes) == (2, 1)
    assert s.history == (Step(R, False), Step(U, True))


def test_blocked_by_wall_or_double_box_changes_nothing() -> None:
    s = GameState(Level.from_rows(TEST1))
    assert s.move(L) is MoveOutcome.BLOCKED  # wall
    assert s.move(D) is MoveOutcome.BLOCKED  # wall
    assert (s.player, s.moves, s.history) == ((4, 1), 0, ())
    s2 = GameState(Level.from_rows(["#######", "#@$$..#", "#######"]))
    assert s2.move(R) is MoveOutcome.BLOCKED  # box behind box
    s3 = GameState(Level.from_rows(["#####", "#@$.#", "#  $#", "#  .#", "#####"]))
    s3.move(D)
    s3.move(R)
    assert s3.move(R) is MoveOutcome.BLOCKED  # box against wall
    assert s3.boxes == {(1, 2), (2, 3)} and s3.moves == 2


def test_undo_redo_roundtrip_and_new_move_clears_redo() -> None:
    s = GameState(Level.from_rows(TEST1))
    s.move(R)
    s.move(U)
    assert s.undo() == Step(U, True)
    assert s.boxes == {(3, 2), (3, 3)} and s.player == (4, 2) and (s.moves, s.pushes) == (1, 0)
    assert s.can_redo and s.redo_lurd == "U"
    assert s.undo() == Step(R, False) and s.player == (4, 1) and s.redo_lurd == "rU"
    assert s.undo() is None
    assert s.redo() == Step(R, False) and s.redo() == Step(U, True)
    assert s.boxes == {(2, 2), (3, 3)} and s.lurd == "rU" and s.redo() is None
    s.undo()
    s.move(R)
    assert not s.can_redo and s.redo_lurd == "" and s.lurd == "rr"


def test_blocked_move_keeps_redo_stack() -> None:
    s = GameState(Level.from_rows(TEST1))
    s.move(R)
    s.undo()
    assert s.move(L) is MoveOutcome.BLOCKED and s.can_redo


def test_restart_clears_history_and_redo() -> None:
    lv = Level.from_rows(TEST1)
    s = GameState(lv)
    s.move(R)
    s.move(U)
    s.undo()
    s.restart()
    assert (s.player, s.boxes, s.moves, s.pushes) == (lv.player, lv.boxes, 0, 0)
    assert not s.can_undo and not s.can_redo


def test_is_solved_when_every_box_on_goal() -> None:
    s = GameState(Level.from_rows(["#######", "#@$ ..#", "#  $  #", "#     #", "#######"]))
    for d in (R, R):
        s.move(d)
    assert s.boxes == {(1, 4), (2, 3)} and not s.is_solved
    for d in (R, D, D, L, L, U, R, D, R, U):
        assert s.move(d) is not MoveOutcome.BLOCKED
    assert s.boxes == {(1, 4), (1, 5)} and s.is_solved


def test_signature_is_player_and_boxes() -> None:
    s = GameState(Level.from_rows(TEST1))
    assert s.signature() == ((4, 1), frozenset({(3, 2), (3, 3)}))
