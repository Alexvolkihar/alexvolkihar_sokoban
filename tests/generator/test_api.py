from collections.abc import Callable

import pytest

from alexvolkihar_sokoban.core.lurd import replay
from alexvolkihar_sokoban.generator.api import GeneratedLevel, GenerationCancelled, GenerationFailed, generate
from alexvolkihar_sokoban.generator.presets import PRESETS, Preset
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveLimits, SolveResult, SolveStatus

FAST = Preset("tiny", 7, 7, 2, 3, 40, SolveLimits(time_s=5.0, max_nodes=50_000), 20)


def unsolvable(*args: object, **kwargs: object) -> SolveResult:
    return SolveResult(SolveStatus.UNSOLVABLE, None, None, None, 1, 1, 0)


def test_presets_match_the_spec() -> None:
    assert list(PRESETS) == ["easy", "medium", "hard"]
    easy, medium, hard = PRESETS["easy"], PRESETS["medium"], PRESETS["hard"]
    assert (easy.width, easy.height, easy.boxes, easy.min_pushes, easy.pull_steps) == (7, 7, 2, 6, 60)
    assert (medium.width, medium.height, medium.boxes, medium.min_pushes) == (8, 8, 3, 12)
    assert (hard.width, hard.height, hard.boxes, hard.min_pushes, hard.pull_steps) == (10, 9, 4, 20, 200)
    assert easy.limits == SolveLimits(time_s=2.0, max_nodes=200_000)
    assert hard.limits == SolveLimits(time_s=8.0, max_nodes=800_000)
    assert all(p.max_attempts == 50 and PRESETS[p.id] is p for p in PRESETS.values())


def test_generate_is_deterministic_for_a_seed() -> None:
    a = generate("easy", 11)
    b = generate(PRESETS["easy"], 11)
    assert a.entry.level.canonical_hash() == b.entry.level.canonical_hash()
    assert a == b


@pytest.mark.parametrize("seed", range(1, 6))
def test_generated_level_is_valid_and_meets_min_pushes(seed: int) -> None:
    result = generate("easy", seed)
    assert isinstance(result, GeneratedLevel) and 1 <= result.attempts <= PRESETS["easy"].max_attempts
    entry = result.entry
    assert entry.id == f"easy-{seed}" and entry.seed == seed
    assert len(entry.level.boxes) == 2 and entry.level.width <= 7 and entry.level.height <= 7
    par = entry.par
    assert par is not None and par.solver == SOLVER_ID and par.pushes >= 6
    state = replay(entry.level, par.lurd)
    assert state.is_solved and (state.pushes, state.moves) == (par.pushes, par.moves)


def test_generate_without_a_seed_records_the_seed_it_used() -> None:
    result = generate(FAST)
    seed = result.entry.seed
    assert isinstance(seed, int) and seed >= 0 and result.entry.id == f"tiny-{seed}"
    assert generate(FAST, seed).entry.level == result.entry.level


def test_generation_failure_raises() -> None:
    calls: list[int] = []

    def fake(*args: object, **kwargs: object) -> SolveResult:
        calls.append(1)
        return unsolvable()

    with pytest.raises(GenerationFailed, match="20 attempts"):
        generate(FAST, 1, solve_fn=fake)
    assert 1 <= len(calls) <= FAST.max_attempts


def test_levels_below_min_pushes_are_rejected() -> None:
    def too_short(*args: object, **kwargs: object) -> SolveResult:
        return SolveResult(SolveStatus.SOLVED, "U", 1, 1, 1, 1, 0)

    with pytest.raises(GenerationFailed):
        generate(FAST, 1, solve_fn=too_short)


def test_solver_gets_the_preset_limits_and_optimal_mode() -> None:
    seen: list[dict[str, object]] = []

    def spy(*args: object, **kwargs: object) -> SolveResult:
        seen.append(kwargs)
        return unsolvable()

    with pytest.raises(GenerationFailed):
        generate(FAST, 2, solve_fn=spy)
    assert seen and all(k["limits"] == FAST.limits and k["mode"] == "optimal" for k in seen)


def test_should_stop_cancels_before_the_next_attempt() -> None:
    stop: Callable[[], bool] = lambda: True  # noqa: E731
    with pytest.raises(GenerationCancelled):
        generate(FAST, 1, should_stop=stop)
    assert issubclass(GenerationCancelled, GenerationFailed)


def test_cancelled_solver_cancels_the_generation() -> None:
    def cancelled(*args: object, **kwargs: object) -> SolveResult:
        return SolveResult(SolveStatus.CANCELLED, None, None, None, 0, 0, 0)

    with pytest.raises(GenerationCancelled):
        generate(FAST, 1, solve_fn=cancelled)


def test_unknown_preset_name_raises() -> None:
    with pytest.raises(ValueError, match="unknown preset"):
        generate("nightmare", 1)
