import random

import pytest

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.lurd import replay
from alexvolkihar_sokoban.generator.carve import carve_room
from alexvolkihar_sokoban.generator.reverse import reverse_play

ROOM: frozenset[Pos] = frozenset((r, c) for r in range(1, 6) for c in range(1, 6))
GOALS: frozenset[Pos] = frozenset({(3, 3), (2, 4)})


@pytest.mark.parametrize("seed", range(30))
def test_reverse_play_keeps_box_count_and_floor(seed: int) -> None:
    rng = random.Random(seed)
    floor = carve_room(rng, 8, 8)
    cells = sorted(floor)
    goals = frozenset(rng.sample(cells, 3))
    player = rng.choice([p for p in cells if p not in goals])
    boxes, end = reverse_play(rng, floor, goals, player, 80)
    assert len(boxes) == 3 and boxes <= floor
    assert end in floor and end not in boxes


def test_reverse_play_with_zero_steps_changes_nothing() -> None:
    assert reverse_play(random.Random(1), ROOM, GOALS, (1, 1), 0) == (GOALS, (1, 1))


def test_reverse_play_moves_boxes_off_their_goals() -> None:
    moved = [reverse_play(random.Random(s), ROOM, GOALS, (1, 1), 60)[0] != GOALS for s in range(10)]
    assert any(moved)


def test_reverse_play_is_deterministic_for_a_seed() -> None:
    a = reverse_play(random.Random(3), ROOM, GOALS, (1, 1), 50)
    b = reverse_play(random.Random(3), ROOM, GOALS, (1, 1), 50)
    assert a == b


def test_reverse_play_rejects_a_player_on_a_box_or_off_the_floor() -> None:
    with pytest.raises(ValueError, match="player"):
        reverse_play(random.Random(0), ROOM, GOALS, (3, 3), 5)
    with pytest.raises(ValueError, match="player"):
        reverse_play(random.Random(0), ROOM, GOALS, (0, 0), 5)


@pytest.mark.parametrize("seed", range(10))
def test_reverse_play_start_can_be_pushed_back_to_the_goals(seed: int) -> None:
    """Each pull is a push played backwards: the reverse of the trace solves the level."""
    from alexvolkihar_sokoban.core.level import Level

    trace: list[str] = []
    boxes, player = reverse_play(random.Random(seed), ROOM, GOALS, (1, 1), 40, trace=trace)
    rows = []
    for r in range(7):
        row = ""
        for c in range(7):
            pos = (r, c)
            if pos not in ROOM:
                row += "#"
            elif pos in boxes:
                row += "*" if pos in GOALS else "$"
            elif pos == player:
                row += "+" if pos in GOALS else "@"
            else:
                row += "." if pos in GOALS else " "
        rows.append(row)
    if boxes == GOALS:
        return  # nothing to solve
    level = Level.from_rows(rows)
    forward = "".join(reversed(trace))
    assert replay(level, forward).is_solved
