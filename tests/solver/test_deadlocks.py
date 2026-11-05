from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.deadlocks import dead_squares, is_frozen
from alexvolkihar_sokoban.solver.distances import goal_distances
from alexvolkihar_sokoban.solver.reachability import Board

ROOM = Level.from_rows(
    [
        "######",
        "#@   #",
        "# $  #",
        "#   .#",
        "######",
    ]
)


def test_dead_squares_include_corners_off_goal() -> None:
    dead = dead_squares(ROOM)
    assert {(1, 1), (1, 4), (3, 1)} <= dead  # corners without a goal
    assert (3, 4) not in dead  # the goal itself
    assert (2, 2) not in dead and (1, 2) in dead  # top row: a box there can never leave it
    assert (3, 2) not in dead  # bottom row leads to the goal


def test_dead_squares_are_floor_cells_only() -> None:
    assert dead_squares(ROOM) <= ROOM.floor


def test_goal_distances_count_pushes_to_the_nearest_goal() -> None:
    board = Board(ROOM)
    dist = goal_distances(board)
    assert dist[board.index[(3, 4)]] == 0
    assert dist[board.index[(2, 2)]] == 3  # down once, right twice
    assert dist[board.index[(1, 1)]] < 0  # unreachable: dead


CORRIDOR = Level.from_rows(
    [
        "#######",
        "#@    #",
        "# $$  #",
        "#  .. #",
        "#######",
    ]
)


def test_box_against_wall_and_box_is_frozen() -> None:
    # two boxes side by side against the top wall, not on goals: neither can ever move
    boxes = frozenset({(1, 2), (1, 3)})
    assert is_frozen(CORRIDOR, boxes, (1, 3))


def test_box_with_free_axis_is_not_frozen() -> None:
    assert not is_frozen(CORRIDOR, CORRIDOR.boxes, (2, 3))


def test_two_by_two_block_is_frozen() -> None:
    boxes = frozenset({(2, 2), (2, 3), (3, 2), (3, 3)})
    level = Level.from_rows(
        [
            "########",
            "#@     #",
            "# $$   #",
            "# $$   #",
            "#  .. ..#",
            "#########",
        ]
    )
    assert is_frozen(level, boxes, (3, 3))


def test_frozen_boxes_all_on_goals_are_not_a_deadlock() -> None:
    level = Level.from_rows(
        [
            "######",
            "#@   #",
            "#    #",
            "#$$  #",
            "#..  #",
            "######",
        ]
    )
    assert not is_frozen(level, frozenset({(4, 1), (4, 2)}), (4, 2))
