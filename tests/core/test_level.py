import hashlib

import pytest

from alexvolkihar_sokoban.core.level import InvalidLevelError, Level

ROOM = ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"]


def test_from_rows_reads_walls_goals_boxes_player() -> None:
    lv = Level.from_rows(ROOM)
    assert lv.player == (4, 1) and lv.boxes == {(2, 3), (3, 2)} and lv.goals == {(1, 1), (1, 5)}
    assert (0, 0) in lv.walls and lv.width == 7 and lv.height == 6


def test_plus_and_star_mean_player_and_box_on_goal() -> None:
    lv = Level.from_rows(["######", "#+*$ #", "#    #", "######"])  # 2 goals (+ *), 2 boxes (* $)
    assert lv.player == (1, 1) and (1, 1) in lv.goals and (1, 2) in lv.boxes & lv.goals


def test_metadata_is_kept() -> None:
    lv = Level.from_rows(ROOM, title="Two crates", author="Alexis MABANZA", comment="first")
    assert (lv.title, lv.author, lv.comment) == ("Two crates", "Alexis MABANZA", "first")


@pytest.mark.parametrize(
    "rows,reason",
    [
        (["#####", "#@$ #", "#####"], "goals"),  # 1 box, 0 goals
        (["#####", "# $.#", "#####"], "player"),  # no player
        (["#####", "#@@$.", "#####"], "player"),  # two players
        (["@$.", "###"], "enclosed"),  # player walks off the grid
        (["####", "#@*#", "####"], "solved"),  # already solved at start
        (["#####", "#@  #", "#####"], "box"),  # no box at all
        (["#####", "#@$.#", "#####", "#$.#"], "floor"),  # second box/goal outside the player's area
        (["#####", "#@$x#", "#####"], "character"),  # unknown character
    ],
)
def test_invalid_levels(rows: list[str], reason: str) -> None:
    with pytest.raises(InvalidLevelError, match=reason):
        Level.from_rows(rows)


def test_box_goal_count_message() -> None:
    with pytest.raises(InvalidLevelError, match="2 boxes but 1 goals"):
        Level.from_rows(["######", "#@$$.#", "######"])


def test_invalid_level_error_is_a_value_error() -> None:
    assert issubclass(InvalidLevelError, ValueError)


def test_floor_excludes_cells_outside_the_walls() -> None:
    lv = Level.from_rows(["  #####", "###   #", "#@$.  #", "#######"])
    assert (0, 0) not in lv.floor and (0, 1) not in lv.floor
    assert {(1, 3), (2, 1), (2, 2), (2, 3), (2, 5)} <= lv.floor
    assert not lv.walls & lv.floor
    assert lv.is_floor((1, 4)) and not lv.is_floor((0, 0)) and not lv.is_floor((1, 2))
    assert lv.is_wall((1, 2)) and not lv.is_wall((0, 0)) and not lv.is_wall((9, 9))


def test_leading_and_trailing_empty_rows_are_dropped() -> None:
    lv = Level.from_rows(["", "#####", "#@$.#", "#####", "   "])
    assert lv.player == (1, 1) and lv.height == 3 and lv.width == 5


def test_to_rows_renders_initial_and_given_state() -> None:
    lv = Level.from_rows(ROOM)
    assert lv.to_rows() == tuple(ROOM)
    rows = lv.to_rows(boxes=frozenset({(1, 1), (2, 3)}), player=(1, 5))
    assert rows == ("#######", "#*   +#", "#  $  #", "#     #", "#     #", "#######")


def test_to_rows_pads_to_width_and_blanks_outside() -> None:
    lv = Level.from_rows(["--####", "###--#", "#@$.-#", "######"])
    assert lv.to_rows() == ("  ####", "###  #", "#@$. #", "######")


def test_canonical_hash_ignores_trailing_spaces_and_dash_floor() -> None:
    a = Level.from_rows(["#####", "#@$.#", "#####"])
    b = Level.from_rows(["#####  ", "#@$.#", "#####", ""])
    d = Level.from_rows(["#####", "#@$.#-", "#####"])
    assert a.canonical_hash() == b.canonical_hash() == d.canonical_hash()
    assert a.canonical_hash().startswith("sha256:") and len(a.canonical_hash()) == 7 + 64


def test_canonical_hash_is_sha256_of_canonical_text() -> None:
    lv = Level.from_rows(ROOM)
    expected = hashlib.sha256("\n".join(ROOM).encode("utf-8")).hexdigest()
    assert lv.canonical_hash() == "sha256:" + expected


def test_canonical_hash_ignores_metadata_but_not_layout() -> None:
    a = Level.from_rows(ROOM, title="x")
    b = Level.from_rows(ROOM, title="y", author="z")
    c = Level.from_rows(["#######", "#.   .#", "#  $  #", "# $   #", "# @   #", "#######"])
    assert a.canonical_hash() == b.canonical_hash() != c.canonical_hash()


def test_level_is_immutable() -> None:
    lv = Level.from_rows(ROOM)
    with pytest.raises(AttributeError):
        lv.player = (1, 1)  # type: ignore[misc]
