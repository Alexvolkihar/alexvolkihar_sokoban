"""The JSON Schemas, the shipped data and the examples of ``docs/formats.md`` agree (plan Task 21).

``docs/formats.md`` is the reference for the Godot port, so every example in it is checked here: a fenced
```json block right after a ``<!-- schema: NAME -->`` line must validate against ``schemas/NAME.schema.json``,
pack and level examples must load and their par must solve the level, saves must replay on a level of the
document, and the worked hash example must give the hash it states.
"""

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.lurd import replay, restore
from alexvolkihar_sokoban.formats.jsonfmt import level_from_dict, pack_from_dict
from alexvolkihar_sokoban.persistence.session import SavedSession
from alexvolkihar_sokoban.persistence.settings import SETTINGS_FORMAT, SETTINGS_VERSION, Settings
from alexvolkihar_sokoban.scoring.records import Progress

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
DOC = ROOT / "docs" / "formats.md"
DATA = files("alexvolkihar_sokoban").joinpath("data")

SCHEMA_NAMES = sorted(p.name.removesuffix(".schema.json") for p in SCHEMAS.glob("*.schema.json"))
SCHEMA_MARK = re.compile(r"<!--\s*schema:\s*([a-z-]+)\s*-->")
HASH_MARK = re.compile(r"<!--\s*canonical-hash:\s*(sha256:[0-9a-f]{64})\s*-->")
FENCE = re.compile(r"^```(\w*)\n(.*?)^```$", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Block:
    lang: str
    text: str
    mark: str  # the last non-empty line above the fence
    line: int


def schema(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return data


def doc_blocks() -> list[Block]:
    text = DOC.read_text(encoding="utf-8")
    blocks = []
    for match in FENCE.finditer(text):
        before = text[: match.start()].rstrip("\n").rsplit("\n", 1)[-1].strip()
        line = text.count("\n", 0, match.start()) + 1
        blocks.append(Block(match.group(1), match.group(2), before, line))
    return blocks


def examples(name: str) -> list[dict[str, Any]]:
    """The decoded ```json blocks marked ``<!-- schema: name -->``."""
    found = []
    for block in doc_blocks():
        mark = SCHEMA_MARK.fullmatch(block.mark)
        if block.lang == "json" and mark and mark.group(1) == name:
            found.append(json.loads(block.text))
    return found


def doc_levels() -> dict[str, Level]:
    """Every level of the document's pack and level examples, by canonical hash."""
    entries = [e for p in examples("pack") for e in pack_from_dict(p).levels]
    entries += [level_from_dict(d) for d in examples("level")]
    return {entry.level.canonical_hash(): entry.level for entry in entries}


# --- the schemas themselves ------------------------------------------------------------------------------


def test_schemas_folder_holds_only_schemas() -> None:
    assert SCHEMA_NAMES == ["benchmark", "level", "pack", "progress", "session", "settings"]
    assert sorted(p.name for p in SCHEMAS.iterdir()) == [f"{n}.schema.json" for n in SCHEMA_NAMES]


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schema_is_valid_draft_2020_12(name: str) -> None:
    data = schema(name)
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(data)
    assert data["properties"]["format"] == {"const": f"alexvolkihar-sokoban/{name}"}
    assert data["properties"]["version"] == {"const": 1}


# --- shipped data ----------------------------------------------------------------------------------------


def shipped_packs() -> list[str]:
    levels = [f"levels/{e.name}" for e in DATA.joinpath("levels").iterdir() if e.name.endswith(".json")]
    return sorted(levels) + ["benchmarks/extra.json"]


@pytest.mark.parametrize("name", shipped_packs())
def test_shipped_pack_matches_the_pack_schema(name: str) -> None:
    data = json.loads(DATA.joinpath(name).read_text(encoding="utf-8"))
    jsonschema.validate(data, schema("pack"), cls=jsonschema.Draft202012Validator)


def test_every_bundled_level_pack_is_checked() -> None:
    assert {"levels/lama-original.json", "levels/lama-unsolvable.json", "levels/boxoban-hard.json"} <= set(
        shipped_packs()
    )


def test_default_settings_match_the_settings_schema() -> None:
    data = {"format": SETTINGS_FORMAT, "version": SETTINGS_VERSION, **Settings().to_dict()}
    jsonschema.validate(data, schema("settings"), cls=jsonschema.Draft202012Validator)


def test_empty_progress_matches_the_progress_schema() -> None:
    data = {"format": "alexvolkihar-sokoban/progress", "version": 1, **Progress().to_dict()}
    jsonschema.validate(data, schema("progress"), cls=jsonschema.Draft202012Validator)


# --- docs/formats.md -------------------------------------------------------------------------------------


def test_every_json_block_of_the_doc_parses() -> None:
    blocks = [b for b in doc_blocks() if b.lang == "json"]
    assert blocks
    for block in blocks:
        try:
            json.loads(block.text)
        except json.JSONDecodeError as exc:  # pragma: no cover - the message names the block
            pytest.fail(f"docs/formats.md line {block.line}: {exc}")


def test_doc_has_an_example_for_every_schema() -> None:
    assert {name for name in SCHEMA_NAMES if examples(name)} == set(SCHEMA_NAMES)


def test_schema_marks_name_existing_schemas_and_precede_json() -> None:
    for block in doc_blocks():
        mark = SCHEMA_MARK.fullmatch(block.mark)
        if mark:
            assert block.lang == "json", block.line
            assert mark.group(1) in SCHEMA_NAMES, block.line


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_doc_examples_validate_against_their_schema(name: str) -> None:
    for data in examples(name):
        jsonschema.validate(data, schema(name), cls=jsonschema.Draft202012Validator)


def test_doc_pack_and_level_examples_load_and_their_par_solves() -> None:
    entries = [e for p in examples("pack") for e in pack_from_dict(p).levels]
    entries += [level_from_dict(d) for d in examples("level")]
    assert entries
    for entry in entries:
        if entry.par is None:
            continue
        state = replay(entry.level, entry.par.lurd)
        assert state.is_solved, entry.id
        assert (state.pushes, state.moves) == (entry.par.pushes, entry.par.moves), entry.id


def test_doc_session_example_restores_on_a_doc_level() -> None:
    levels = doc_levels()
    for data in examples("session"):
        payload = {k: v for k, v in data.items() if k not in ("format", "version")}
        session = SavedSession.from_dict(payload)
        state = restore(levels[session.level_hash], session.lurd, session.redo_lurd)
        assert not state.is_solved


def test_doc_progress_example_replays_on_doc_levels() -> None:
    levels = doc_levels()
    for data in examples("progress"):
        payload = {k: v for k, v in data.items() if k not in ("format", "version")}
        assert Progress.from_dict(payload).to_dict() == payload  # nothing dropped by the lenient reader
        for level_hash, record in data["levels"].items():
            for key in ("best_moves", "best_pushes"):
                best = record[key]
                if best is not None:
                    state = replay(levels[level_hash], best["lurd"])
                    assert state.is_solved and (state.moves, state.pushes) == (best["moves"], best["pushes"])
        last = data["last_played"]
        assert last is None or last["level_hash"] in levels


def test_doc_worked_hash_example_gives_the_stated_hash() -> None:
    worked = [(b, HASH_MARK.fullmatch(b.mark)) for b in doc_blocks()]
    worked = [(b, m) for b, m in worked if m]
    assert worked, "docs/formats.md needs a <!-- canonical-hash: sha256:... --> example"
    for block, mark in worked:
        rows = block.text.rstrip("\n").split("\n")
        level = Level.from_rows(rows)
        assert level.canonical_text() == block.text.rstrip("\n"), "the example must be the canonical text"
        assert level.canonical_hash() == mark.group(1)
