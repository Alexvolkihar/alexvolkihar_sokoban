import json
from importlib.resources import files
from pathlib import Path

import jsonschema
import pytest

from alexvolkihar_sokoban.benchmark.suites import (
    EXTRA_PACK_ID,
    Suite,
    load_bundled_packs,
    load_extra_pack,
    load_suites,
    resolve,
)
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.solver.api import SolveLimits
from alexvolkihar_sokoban.solver.deadlocks import dead_squares

ROOT = Path(__file__).resolve().parents[2]


def tiny_pack(pack_id: str, *level_ids: str) -> Pack:
    level = Level.from_rows(["#####", "#@$.#", "#####"])
    return Pack(pack_id, pack_id, tuple(LevelEntry(i, level) for i in level_ids))


def test_suites_load_and_items_parse() -> None:
    suites = load_suites()
    assert list(suites) == ["quick", "standard", "stress"]
    quick = suites["quick"]
    assert quick == Suite("quick", quick.title, SolveLimits(10.0, 1_000_000), ("lama-original",))
    standard = suites["standard"]
    assert standard.limits == SolveLimits(30.0, 3_000_000)
    assert standard.items == ("lama-original", *(f"boxoban-hard/{i}" for i in range(1, 41)))
    stress = suites["stress"]
    assert stress.limits == SolveLimits(60.0, 5_000_000)
    assert stress.items == ("lama-unsolvable", EXTRA_PACK_ID, "boxoban-hard")
    assert all(s.title for s in suites.values())


def test_suites_file_carries_format_and_version() -> None:
    data = json.loads(files("alexvolkihar_sokoban").joinpath("data/benchmarks/suites.json").read_text())
    assert data["format"] == "alexvolkihar-sokoban/benchmark-suites"
    assert data["version"] == 1


def test_load_suites_rejects_a_broken_file(tmp_path: Path) -> None:
    bad = tmp_path / "suites.json"
    bad.write_text(
        json.dumps(
            {
                "format": "alexvolkihar-sokoban/benchmark-suites",
                "version": 1,
                "suites": [{"id": "x", "title": "X", "items": []}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_suites(bad)


def test_resolve_reports_missing_items() -> None:
    suite = Suite("s", "S", SolveLimits(), ("a", "b/2", "b/9", "nope", "nope/1"))
    packs = {"a": tiny_pack("a", "1", "2"), "b": tiny_pack("b", "1", "2")}
    items, missing = resolve(suite, packs)
    assert [(p.id, e.id) for p, e in items] == [("a", "1"), ("a", "2"), ("b", "2")]
    assert missing == ["b/9", "nope", "nope/1"]


def test_resolve_splits_on_the_first_slash_only() -> None:
    suite = Suite("s", "S", SolveLimits(), ("custom/dir/level",))
    items, missing = resolve(suite, {"custom": tiny_pack("custom", "dir/level")})
    assert [e.id for _, e in items] == ["dir/level"] and missing == []


def test_extra_pack_holds_the_repaired_test_performance() -> None:
    pack = load_extra_pack()
    assert pack.id == EXTRA_PACK_ID and pack.hidden
    assert "modified" in pack.license.lower()
    entry = pack.entry("test_performance")
    level = entry.level
    assert len(level.boxes) == len(level.goals) == 12
    # The original left boxes in rooms no box could leave: every box must now be able to reach a goal.
    assert not level.boxes & dead_squares(level)
    assert (level.width, level.height) == (34, 34)


def test_extra_pack_validates_against_the_pack_schema() -> None:
    schema = json.loads((ROOT / "schemas" / "pack.schema.json").read_text(encoding="utf-8"))
    data = json.loads(files("alexvolkihar_sokoban").joinpath("data/benchmarks/extra.json").read_text())
    jsonschema.validate(data, schema)


def test_bundled_packs_include_the_extra_pack() -> None:
    packs, warnings = load_bundled_packs()
    assert EXTRA_PACK_ID in packs
    assert all(isinstance(w, str) for w in warnings)


def test_bundled_packs_skip_broken_files(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{nope", encoding="utf-8")
    good = {
        "format": "alexvolkihar-sokoban/pack",
        "version": 1,
        "id": "good",
        "title": "Good",
        "levels": [{"id": "1", "rows": ["#####", "#@$.#", "#####"]}],
    }
    (tmp_path / "good.json").write_text(json.dumps(good), encoding="utf-8")
    packs, warnings = load_bundled_packs(tmp_path)
    assert "good" in packs and EXTRA_PACK_ID in packs
    assert len(warnings) == 1 and "broken.json" in warnings[0]
