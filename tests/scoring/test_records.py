import dataclasses
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.scoring.records import (
    PROGRESS_FORMAT,
    PROGRESS_VERSION,
    BestSolution,
    LastPlayed,
    LevelRecord,
    Progress,
    RecordUpdate,
    RunResult,
)

PAR = Par(pushes=8, moves=30, lurd="", solver="push-astar/1")
H1 = "sha256:" + "a" * 64
H2 = "sha256:" + "b" * 64
H3 = "sha256:" + "c" * 64
T1 = "2026-11-05T14:03:22Z"
T2 = "2026-11-06T09:00:00Z"
SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "progress.schema.json"


def run(
    moves: int = 40,
    pushes: int = 10,
    elapsed_ms: int = 5000,
    *,
    lurd: str = "",
    assisted: bool = False,
    finished_at: str = T1,
) -> RunResult:
    return RunResult(
        moves=moves,
        pushes=pushes,
        elapsed_ms=elapsed_ms,
        lurd=lurd or "r" * (moves - pushes) + "R" * pushes,
        assisted=assisted,
        finished_at=finished_at,
    )


def test_constants() -> None:
    assert PROGRESS_FORMAT == "alexvolkihar-sokoban/progress"
    assert PROGRESS_VERSION == 1


def test_all_dataclasses_are_frozen() -> None:
    record = LevelRecord(pack_id="p", level_id="l")
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.stars = 3  # type: ignore[misc]
    for cls in (RunResult, BestSolution, LevelRecord, RecordUpdate, LastPlayed):
        assert cls.__dataclass_params__.frozen  # type: ignore[attr-defined]


def test_unknown_level_has_no_record() -> None:
    assert Progress().get(H1) is None


def test_first_completion_sets_all_bests() -> None:
    p = Progress()
    up = p.record_run(H1, "pack", "lvl", run(40, 10, 5000, finished_at=T1), PAR)
    assert up.stars_earned == 2
    assert up.new_best_moves and up.new_best_pushes and up.new_best_time
    assert not up.beats_par_moves
    rec = p.get(H1)
    assert rec is not None and up.record == rec
    assert rec.pack_id == "pack" and rec.level_id == "lvl"
    assert rec.completed and rec.stars == 2 and rec.plays == 1
    assert rec.first_completed_at == T1
    assert rec.best_moves == BestSolution(moves=40, pushes=10, lurd="r" * 30 + "R" * 10)
    assert rec.best_pushes == rec.best_moves
    assert rec.best_time_ms == 5000


def test_bests_tracked_independently() -> None:
    p = Progress()
    p.record_run(H1, "pack", "lvl", run(40, 12, 9000), PAR)  # A: fewer moves
    up = p.record_run(H1, "pack", "lvl", run(50, 9, 4000, finished_at=T2), PAR)  # B: fewer pushes, faster
    assert not up.new_best_moves and up.new_best_pushes and up.new_best_time
    rec = up.record
    assert rec.best_moves is not None and (rec.best_moves.moves, rec.best_moves.pushes) == (40, 12)
    assert rec.best_pushes is not None and (rec.best_pushes.moves, rec.best_pushes.pushes) == (50, 9)
    assert rec.best_time_ms == 4000
    assert rec.plays == 2 and rec.first_completed_at == T1


def test_worse_run_changes_no_best() -> None:
    p = Progress()
    p.record_run(H1, "pack", "lvl", run(40, 10, 5000), PAR)
    up = p.record_run(H1, "pack", "lvl", run(41, 11, 5000), PAR)
    assert not (up.new_best_moves or up.new_best_pushes or up.new_best_time)
    assert up.record.best_moves is not None and up.record.best_moves.moves == 40


def test_tie_breaks() -> None:
    p = Progress()
    p.record_run(H1, "pack", "lvl", run(40, 10), PAR)
    up = p.record_run(H1, "pack", "lvl", run(40, 9), PAR)  # same moves, fewer pushes
    assert up.new_best_moves and up.record.best_moves == BestSolution(40, 9, "r" * 31 + "R" * 9)
    up = p.record_run(H1, "pack", "lvl", run(38, 9), PAR)  # same pushes, fewer moves
    assert up.new_best_pushes and up.record.best_pushes == BestSolution(38, 9, "r" * 29 + "R" * 9)
    up = p.record_run(H1, "pack", "lvl", run(38, 9), PAR)  # exact tie: the first one is kept
    assert not (up.new_best_moves or up.new_best_pushes or up.new_best_time)


def test_assisted_run_only_marks_completed() -> None:
    p = Progress()
    up = p.record_run(H1, "pack", "lvl", run(30, 8, assisted=True), PAR)
    assert up.stars_earned == 0
    assert not (up.new_best_moves or up.new_best_pushes or up.new_best_time or up.beats_par_moves)
    rec = up.record
    assert rec.completed and rec.plays == 1 and rec.first_completed_at == T1
    assert rec.stars == 0 and rec.best_moves is None and rec.best_pushes is None and rec.best_time_ms is None


def test_assisted_run_keeps_existing_stars_and_bests() -> None:
    p = Progress()
    before = p.record_run(H1, "pack", "lvl", run(40, 10, 5000), PAR).record
    up = p.record_run(H1, "pack", "lvl", run(20, 8, 100, assisted=True, finished_at=T2), PAR)
    assert up.stars_earned == 0
    assert up.record == dataclasses.replace(before, plays=2)


def test_stars_keep_maximum() -> None:
    p = Progress()
    assert p.record_run(H1, "pack", "lvl", run(30, 8), PAR).record.stars == 3
    up = p.record_run(H1, "pack", "lvl", run(99, 20), PAR)
    assert up.stars_earned == 1 and up.record.stars == 3


def test_beats_par_moves_flag() -> None:
    up = Progress().record_run(H1, "pack", "lvl", run(29, 8), PAR)
    assert up.beats_par_moves and up.stars_earned == 3


def test_no_par_gives_one_star() -> None:
    up = Progress().record_run(H1, "pack", "lvl", run(10, 2), None)
    assert up.stars_earned == 1 and not up.beats_par_moves


def test_record_follows_the_latest_pack_and_level_ids() -> None:
    p = Progress()
    p.record_run(H1, "custom", "a.xsb#1", run(), PAR)
    rec = p.record_run(H1, "lama-original", "test1", run(), PAR).record
    assert (rec.pack_id, rec.level_id) == ("lama-original", "test1")


def test_completed_count() -> None:
    p = Progress()
    p.record_run(H1, "pack", "a", run(), PAR)
    p.record_run(H2, "pack", "b", run(assisted=True), PAR)
    assert p.completed_count([H1, H2, H3]) == 2
    assert p.completed_count([H1, H1]) == 1
    assert p.completed_count([H3]) == 0


def test_last_played_and_reset() -> None:
    p = Progress()
    assert p.last_played is None
    lp = LastPlayed(pack_id="pack", level_id="a", level_hash=H1)
    p.set_last_played(lp)
    assert p.last_played == lp
    p.record_run(H1, "pack", "a", run(), PAR)
    p.reset()
    assert p.last_played is None and p.levels == {} and p.get(H1) is None


def _sample() -> Progress:
    p = Progress()
    p.record_run(H1, "pack", "a", run(40, 12, 9000), PAR)
    p.record_run(H1, "pack", "a", run(50, 9, 4000, finished_at=T2), PAR)
    p.record_run(H2, "pack", "b", run(assisted=True), None)
    p.set_last_played(LastPlayed(pack_id="pack", level_id="b", level_hash=H2))
    return p


def test_progress_roundtrip_and_schema() -> None:
    p = _sample()
    data = p.to_dict()
    assert "format" not in data and "version" not in data
    assert json.loads(json.dumps(data)) == data  # plain JSON
    assert Progress.from_dict(data) == p
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate({"format": PROGRESS_FORMAT, "version": PROGRESS_VERSION, **data}, schema)
    jsonschema.validate(
        {"format": PROGRESS_FORMAT, "version": PROGRESS_VERSION, **Progress().to_dict()}, schema
    )


def test_to_dict_layout_matches_spec() -> None:
    data = _sample().to_dict()
    assert data["last_played"] == {"pack_id": "pack", "level_id": "b", "level_hash": H2}
    levels = data["levels"]
    assert isinstance(levels, dict)
    assert levels[H2] == {
        "pack_id": "pack",
        "level_id": "b",
        "completed": True,
        "stars": 0,
        "plays": 1,
        "first_completed_at": T1,
        "best_moves": None,
        "best_pushes": None,
        "best_time_ms": None,
    }
    assert levels[H1]["best_moves"] == {"moves": 40, "pushes": 12, "lurd": "r" * 28 + "R" * 12}


def _doc(**changes: Any) -> dict[str, Any]:
    """A valid progress document with some top-level keys replaced."""
    record = {"pack_id": "p", "level_id": "l", "completed": False, "stars": 0, "plays": 0}
    record |= {"first_completed_at": None, "best_moves": None, "best_pushes": None, "best_time_ms": None}
    doc: dict[str, Any] = {"format": PROGRESS_FORMAT, "version": 1, "levels": {H1: record}}
    return doc | {"last_played": None} | changes


def test_schema_accepts_the_reference_document() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(_doc(), schema)


@pytest.mark.parametrize(
    "bad",
    [
        _doc(levels={"not-a-hash": _doc()["levels"][H1]}),
        _doc(levels={H1: _doc()["levels"][H1] | {"stars": 4}}),
        _doc(levels={H1: _doc()["levels"][H1] | {"first_completed_at": "yesterday"}}),
        _doc(extra=1),
        _doc(format="alexvolkihar-sokoban/settings"),
        _doc(version=2),
    ],
)
def test_schema_rejects_invalid_documents(bad: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_from_dict_of_empty_or_garbage_gives_empty_progress() -> None:
    for data in ({}, {"levels": 3, "last_played": "x"}, {"levels": [1, 2]}):
        p = Progress.from_dict(data)
        assert p.levels == {} and p.last_played is None


def test_from_dict_skips_unusable_records_and_defaults_bad_fields() -> None:
    good = _sample().to_dict()["levels"]
    assert isinstance(good, dict)
    data: dict[str, Any] = {
        "levels": {
            H1: good[H1],
            H2: "garbage",  # not a record → skipped
            "not-a-hash": good[H1],  # not a canonical level hash → skipped
            H3: {"level_id": "c"},  # no pack id → skipped
            "sha256:" + "d" * 64: {
                "pack_id": "pack",
                "level_id": "d",
                "completed": "yes",
                "stars": 7,
                "plays": True,
                "first_completed_at": 12,
                "best_moves": {"moves": "many", "pushes": 1, "lurd": "R"},
                "best_pushes": {"moves": 1, "pushes": 1, "lurd": "R"},
                "best_time_ms": -5,
            },
        },
        "last_played": {"pack_id": "pack", "level_id": 3, "level_hash": H1},
    }
    p = Progress.from_dict(data)
    assert set(p.levels) == {H1, "sha256:" + "d" * 64}
    assert p.get(H1) == _sample().get(H1)
    assert p.get("sha256:" + "d" * 64) == LevelRecord(
        pack_id="pack", level_id="d", best_pushes=BestSolution(moves=1, pushes=1, lurd="R")
    )
    assert p.last_played is None
