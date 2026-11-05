import random

import pytest

from alexvolkihar_sokoban.core.geometry import Direction, Pos, step
from alexvolkihar_sokoban.generator.carve import carve_room


def connected(floor: frozenset[Pos]) -> bool:
    start = min(floor)
    seen = {start}
    todo = [start]
    while todo:
        pos = todo.pop()
        for d in Direction:
            nxt = step(pos, d)
            if nxt in floor and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen == floor


@pytest.mark.parametrize("width,height", [(7, 7), (8, 8), (10, 9), (5, 4)])
@pytest.mark.parametrize("seed", range(20))
def test_carve_is_connected_and_enclosed(width: int, height: int, seed: int) -> None:
    floor = carve_room(random.Random(seed), width, height)
    assert floor and connected(floor)
    # Strictly inside the rectangle: the border row/column stays wall.
    assert all(1 <= r <= height - 2 and 1 <= c <= width - 2 for r, c in floor)
    interior = (width - 2) * (height - 2)
    assert len(floor) >= 0.6 * interior


def test_carve_is_deterministic_for_a_seed() -> None:
    assert carve_room(random.Random(7), 8, 8) == carve_room(random.Random(7), 8, 8)


def test_carve_varies_with_the_seed() -> None:
    rooms = {carve_room(random.Random(seed), 8, 8) for seed in range(10)}
    assert len(rooms) > 1


@pytest.mark.parametrize("width,height", [(2, 5), (5, 2), (3, 3)])
def test_carve_rejects_a_rectangle_without_room_for_a_level(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="too small"):
        carve_room(random.Random(0), width, height)
