import json
from importlib.resources import files
from pathlib import Path

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry
from alexvolkihar_sokoban.formats import FormatError, jsonfmt, legacy

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "formats"
ROOM = ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"]


def test_legacy_symbols() -> None:
    pack = legacy.parse("XXXXX\nX@*.X\nXXXXX\n", pack_id="tiny")
    assert pack.levels[0].level == Level.from_rows(["#####", "#@$.#", "#####"])


def test_single_level_pack_takes_its_id_from_the_argument() -> None:
    pack = legacy.parse((FIXTURES / "legacy_room.txt").read_text(encoding="utf-8"), pack_id="room")
    assert (pack.id, pack.title) == ("room", "room")
    assert [e.id for e in pack.levels] == ["1"]
    assert pack.levels[0].level == Level.from_rows(ROOM)


def test_crlf_bom_tabs_trailing_spaces_load_like_clean_file() -> None:
    clean = (FIXTURES / "legacy_room.txt").read_text(encoding="utf-8")
    messy = "﻿" + "".join(f"\t{row}  \r\n" for row in clean.splitlines()) + "\r\n"
    a = legacy.parse(clean, pack_id="a").levels[0].level
    b = legacy.parse(messy, pack_id="b").levels[0].level
    assert a.canonical_hash() == b.canonical_hash()


def test_invalid_legacy_level_raises_format_error_with_reason() -> None:
    with pytest.raises(FormatError, match="goals"):
        legacy.parse("XXXXX\nX@** X\nXX.XX\n", pack_id="bad")


def test_empty_legacy_file_raises_format_error() -> None:
    with pytest.raises(FormatError, match="no level"):
        legacy.parse("\n\n", pack_id="empty")


FIRST_STEPS_JSON = files("alexvolkihar_sokoban.data") / "levels" / "first-steps.json"
FIRST_STEPS = jsonfmt.pack_from_dict(json.loads(FIRST_STEPS_JSON.read_text(encoding="utf-8")))


@pytest.mark.parametrize("entry", FIRST_STEPS.levels, ids=lambda e: e.id)
def test_bundled_levels_written_in_the_legacy_format_load_back(entry: LevelEntry) -> None:
    rows = entry.level.to_rows()
    assert not any(c in "*+" for row in rows for c in row)  # the format has no box or player on a goal
    text = "\n".join(row.translate(str.maketrans({"#": "X", "$": "*"})) for row in rows) + "\n"
    loaded = legacy.parse(text, pack_id=entry.id).levels[0].level
    assert loaded.canonical_hash() == entry.level.canonical_hash()
