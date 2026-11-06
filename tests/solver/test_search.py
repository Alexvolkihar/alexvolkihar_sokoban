import time

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.lurd import replay
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus, solve
from tests.solver.levels import LEVELS, SOLVABLE, UNSOLVABLE

LIMITS = SolveLimits(time_s=5)


def check_solution(level: Level, r: SolveResult) -> None:
    assert r.status is SolveStatus.SOLVED
    assert r.lurd is not None
    assert replay(level, r.lurd).is_solved
    assert r.pushes == sum(c.isupper() for c in r.lurd)
    assert r.moves == len(r.lurd)
    assert r.nodes_expanded >= 0 and r.nodes_generated >= 0 and r.elapsed_ms >= 0


@pytest.mark.parametrize("name", SOLVABLE)
def test_solves_bundled_levels_and_solution_replays(name: str) -> None:
    check_solution(LEVELS[name], solve(LEVELS[name], limits=LIMITS))


@pytest.mark.parametrize("name", UNSOLVABLE)
def test_detects_unsolvable(name: str) -> None:
    started = time.monotonic()
    r = solve(LEVELS[name], limits=LIMITS)
    assert r.status is SolveStatus.UNSOLVABLE
    assert (r.lurd, r.pushes, r.moves) == (None, None, None)
    assert time.monotonic() - started < 1.0


def test_push_optimal_on_known_level() -> None:
    room = Level.from_rows(["#######", "#@    #", "# $   #", "#    .#", "#######"])
    # one push down and three pushes right, in either order: 4 pushes is optimal
    r = solve(room)
    check_solution(room, r)
    assert r.pushes == 4


def test_three_push_corridor() -> None:
    corridor = Level.from_rows(["#######", "#@$  .#", "#######"])
    r = solve(corridor)
    check_solution(corridor, r)
    assert (r.lurd, r.pushes, r.moves) == ("RRR", 3, 3)


def test_walks_are_part_of_the_solution() -> None:
    level = Level.from_rows(["######", "#    #", "#@$. #", "######"])
    r = solve(level)
    check_solution(level, r)
    assert r.lurd == "R"
    level = Level.from_rows(["######", "#@   #", "# $. #", "######"])
    r = solve(level)
    check_solution(level, r)
    assert r.lurd == "dR"


def test_solve_from_mid_game_state() -> None:
    level = LEVELS["room"]
    state = replay(level, "rU")
    r = solve(level, boxes=state.boxes, player=state.player, limits=LIMITS)
    assert r.status is SolveStatus.SOLVED and r.lurd is not None
    mid = Level.from_rows(level.to_rows(state.boxes, state.player))
    assert replay(mid, r.lurd).is_solved
    assert replay(level, "rU" + r.lurd).is_solved


def test_initial_deadlock_is_unsolvable_immediately() -> None:
    level = Level.from_rows(["######", "#$  .#", "#@   #", "######"])  # box in a corner, off goal
    r = solve(level)
    assert r.status is SolveStatus.UNSOLVABLE and r.nodes_expanded <= 1


def test_initial_freeze_deadlock_is_unsolvable_immediately() -> None:
    level = Level.from_rows(["#######", "#@    #", "# $$  #", "# $$  #", "# .. ..#", "########"])
    r = solve(level)
    assert r.status is SolveStatus.UNSOLVABLE and r.nodes_expanded <= 1


@pytest.mark.parametrize("name", SOLVABLE)
def test_fast_mode_returns_valid_solution(name: str) -> None:
    check_solution(LEVELS[name], solve(LEVELS[name], limits=LIMITS, mode="fast"))


def test_fast_mode_detects_unsolvable() -> None:
    assert solve(LEVELS["sealed"], limits=LIMITS, mode="fast").status is SolveStatus.UNSOLVABLE


def test_counts_nodes() -> None:
    r = solve(LEVELS["twins"], limits=LIMITS)
    assert r.nodes_expanded >= 1 and r.nodes_generated >= r.nodes_expanded - 1


def reference_min_pushes(level: Level) -> int | None:
    """Plain breadth-first search over pushes, without heuristic or deadlock pruning."""
    from collections import deque

    from alexvolkihar_sokoban.core.geometry import Direction, step
    from alexvolkihar_sokoban.solver.reachability import reachable

    start = (level.boxes, reachable(level, level.boxes, level.player)[1])
    seen = {start}
    todo = deque([(level.boxes, level.player, 0)])
    while todo:
        boxes, player, pushes = todo.popleft()
        cells, _ = reachable(level, boxes, player)
        for box in boxes:
            for d in Direction:
                behind = (box[0] - d.dr, box[1] - d.dc)
                target = step(box, d)
                if behind in cells and target in level.floor and target not in boxes:
                    nxt = (boxes - {box}) | {target}
                    if nxt == level.goals:
                        return pushes + 1
                    key = (nxt, reachable(level, nxt, box)[1])
                    if key not in seen:
                        seen.add(key)
                        todo.append((nxt, box, pushes + 1))
    return None


@pytest.mark.parametrize("name", ["first-push", "room", "twins", "spiral", "hallway", "pillars", "three-way"])
def test_optimal_mode_matches_a_plain_breadth_first_search(name: str) -> None:
    assert solve(LEVELS[name], limits=LIMITS).pushes == reference_min_pushes(LEVELS[name])
