from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.reachability import reachable

#                    0123456
ROOM = Level.from_rows(
    [
        "#######",  # 0
        "#  .  #",  # 1
        "#  $  #",  # 2
        "## $ ##",  # 3
        "#  @. #",  # 4
        "#######",  # 5
    ]
)


def test_reachable_walks_around_boxes_and_normalises_to_top_left() -> None:
    cells, norm = reachable(ROOM, ROOM.boxes, ROOM.player)
    assert (3, 1) not in cells and (2, 3) not in cells and (3, 3) not in cells  # walls and boxes block
    assert {(4, 1), (4, 5), (1, 1), (1, 5), (3, 2), (3, 4)} <= cells
    assert norm == (1, 1)  # top-left-most reachable cell, row first


def test_boxes_can_split_the_floor() -> None:
    boxes = frozenset({(3, 2), (3, 4)})
    cells, norm = reachable(ROOM, boxes, (4, 3))
    # (3, 3) stays open between the two boxes, so the floor is still one region
    assert (3, 3) in cells and norm == (1, 1)
    walled = frozenset({(3, 2), (3, 3), (3, 4)})
    cells, norm = reachable(ROOM, walled, (4, 3))
    assert cells == {(4, 1), (4, 2), (4, 3), (4, 4), (4, 5)}
    assert norm == (4, 1)


def test_same_region_gives_same_normalised_cell() -> None:
    a = reachable(ROOM, ROOM.boxes, (4, 1))
    b = reachable(ROOM, ROOM.boxes, (1, 5))
    assert a == b
