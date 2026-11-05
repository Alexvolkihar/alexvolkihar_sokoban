"""Cross-engine conformance vectors (spec 9.7): any port of the rules must pass these files."""

import json
from pathlib import Path
from typing import Any

import pytest

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.state import GameState, MoveOutcome

VECTORS = Path(__file__).resolve().parent.parent / "vectors"


def _cases(name: str) -> list[dict[str, Any]]:
    data = json.loads((VECTORS / name).read_text(encoding="utf-8"))
    assert data["format"].startswith("alexvolkihar-sokoban/") and data["version"] == 1
    cases: list[dict[str, Any]] = data["cases"]
    return cases


def test_vector_files_are_big_enough() -> None:
    assert len(_cases("moves.json")) >= 8 and len(_cases("hash.json")) >= 3


@pytest.mark.parametrize("case", _cases("moves.json"), ids=lambda c: c["name"])
def test_move_vectors(case: dict[str, Any]) -> None:
    state = GameState(Level.from_rows(case["rows"]))
    blocked = 0
    for key in case["input"]:
        if state.move(Direction.from_char(key)) is MoveOutcome.BLOCKED:
            blocked += 1
    exp = case["expected"]
    assert list(state.player) == exp["player"]
    assert sorted([list(b) for b in state.boxes]) == exp["boxes"]
    assert (state.moves, state.pushes, state.is_solved, blocked) == (
        exp["moves"],
        exp["pushes"],
        exp["solved"],
        exp["blocked_steps"],
    )


@pytest.mark.parametrize("case", _cases("hash.json"), ids=lambda c: c["hash"][7:19])
def test_hash_vectors(case: dict[str, Any]) -> None:
    lv = Level.from_rows(case["rows"])
    assert "\n".join(r.rstrip() for r in lv.to_rows()).strip("\n") == case["canonical"]
    assert lv.canonical_hash() == case["hash"]
