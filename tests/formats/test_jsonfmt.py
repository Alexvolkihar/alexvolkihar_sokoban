import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.formats import FormatError, jsonfmt

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
A = Level.from_rows(["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"], title="Two crates")
B = Level.from_rows(["  ####", "###  #", "#@$ .#", "######"], author="Ann", comment="bent")
PAR = Par(pushes=1, moves=2, lurd="rR", solver="push-astar/1")


def _pack() -> Pack:
    return Pack(
        id="first-steps",
        title="First steps — demo",
        levels=(LevelEntry("room", A), LevelEntry("bent", B, par=PAR, seed=42)),
        author="Alexis MABANZA",
        license="MIT (see LICENSE)",
        source="https://github.com/Alexvolkihar/alexvolkihar_sokoban",
        hidden=True,
    )


def _schema(name: str) -> Any:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_json_pack_roundtrip_with_par() -> None:
    pack = _pack()
    data = jsonfmt.pack_to_dict(pack)
    assert jsonfmt.pack_from_dict(json.loads(json.dumps(data))) == pack


def test_pack_dict_shape_matches_spec() -> None:
    data = jsonfmt.pack_to_dict(_pack())
    assert data["format"] == "alexvolkihar-sokoban/pack" and data["version"] == 1
    levels: Any = data["levels"]
    assert levels[0] == {
        "id": "room",
        "title": "Two crates",
        "rows": list(A.canonical_text().split("\n")),
        "par": None,
    }
    assert levels[1]["par"] == {"pushes": 1, "moves": 2, "lurd": "rR", "solver": "push-astar/1"}
    assert levels[1]["seed"] == 42 and levels[1]["author"] == "Ann" and levels[1]["comment"] == "bent"


def test_pack_json_validates_against_schema() -> None:
    schema = _schema("pack.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(jsonfmt.pack_to_dict(_pack()))


def test_level_json_validates_against_schema() -> None:
    schema = _schema("level.schema.json")
    Draft202012Validator.check_schema(schema)
    data = jsonfmt.level_to_dict(LevelEntry("bent", B, par=PAR))
    Draft202012Validator(schema).validate(data)
    assert data["format"] == "alexvolkihar-sokoban/level"
    assert jsonfmt.level_from_dict(data) == LevelEntry("bent", B, par=PAR)


def test_schema_rejects_a_wrong_format_tag() -> None:
    data = jsonfmt.pack_to_dict(_pack())
    data["format"] = "something/else"
    assert not Draft202012Validator(_schema("pack.schema.json")).is_valid(data)


def _mutated(path: list[Any], value: Any) -> dict[str, Any]:
    data: Any = copy.deepcopy(jsonfmt.pack_to_dict(_pack()))
    target = data
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return dict(data)


@pytest.mark.parametrize(
    "path,value,reason",
    [
        (["format"], "alexvolkihar-sokoban/level", "format"),
        (["version"], 2, "version"),
        (["version"], True, "version"),
        (["id"], KeyError, "id"),
        (["id"], 3, "id"),
        (["hidden"], "yes", "hidden"),
        (["levels"], {}, "levels"),
        (["levels", 0, "rows"], "######", "rows"),
        (["levels", 1, "par", "pushes"], "1", "pushes"),
        (["levels", 1, "seed"], 1.5, "seed"),
    ],
)
def test_malformed_pack_raises_format_error(path: list[Any], value: Any, reason: str) -> None:
    with pytest.raises(FormatError, match=reason):
        jsonfmt.pack_from_dict(_mutated(path, value))


def test_invalid_level_is_an_error_in_strict_mode() -> None:
    data = _mutated(["levels", 0, "rows"], ["#####", "#@$ #", "#####"])
    with pytest.raises(FormatError, match="room.*goals"):
        jsonfmt.pack_from_dict(data)


def test_invalid_level_is_skipped_with_a_warning_when_collecting_warnings() -> None:
    data = _mutated(["levels", 0, "rows"], ["#####", "#@$ #", "#####"])
    warnings: list[str] = []
    pack = jsonfmt.pack_from_dict(data, warnings=warnings)
    assert [e.id for e in pack.levels] == ["bent"]
    assert len(warnings) == 1 and "room" in warnings[0]


def test_duplicate_level_ids_are_rejected() -> None:
    data = _mutated(["levels", 1, "id"], "room")
    with pytest.raises(FormatError, match="duplicate"):
        jsonfmt.pack_from_dict(data)


def test_optional_pack_fields_default() -> None:
    data = {"format": "alexvolkihar-sokoban/pack", "version": 1, "id": "p", "title": "P", "levels": []}
    assert jsonfmt.pack_from_dict(data) == Pack(id="p", title="P", levels=())
