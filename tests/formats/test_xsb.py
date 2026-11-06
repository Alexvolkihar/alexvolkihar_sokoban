from pathlib import Path

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.formats import xsb

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "formats"


def _read(name: str) -> str:
    return (FIXTURES / name).read_bytes().decode("utf-8")


def test_parse_multi_level_sok_with_titles() -> None:
    pack, warnings = xsb.parse(_read("multi.sok"), pack_id="multi")
    assert warnings == []
    assert [e.id for e in pack.levels] == ["1", "2", "3"]
    assert [e.title for e in pack.levels] == ["Corridor", "Longer corridor", "Bent"]
    assert pack.levels[0].level.author == "Someone"
    assert pack.levels[1].level.comment == "two cells to push"
    assert pack.levels[0].level == Level.from_rows(
        ["#####", "#@$.#", "#####"], title="Corridor", author="Someone"
    )


def test_header_metadata_before_the_first_board_describes_the_pack() -> None:
    pack, _ = xsb.parse(_read("multi.sok"), pack_id="multi")
    assert pack.id == "multi"
    assert pack.title == "Three small levels"
    assert pack.author == "The test suite"


def test_pack_title_defaults_to_argument_then_id() -> None:
    text = "#####\n#@$.#\n#####\n"
    assert xsb.parse(text, pack_id="p", pack_title="Given")[0].title == "Given"
    assert xsb.parse(text, pack_id="p")[0].title == "p"


def test_metadata_keys_are_case_insensitive_and_comments_are_ignored() -> None:
    text = "; Title: not a title\n#####\n#@$.#\n#####\ntitle: Small\nAUTHOR:  Me \n"
    pack, _ = xsb.parse(text, pack_id="p")
    level = pack.levels[0].level
    assert (level.title, level.author) == ("Small", "Me")


def test_rle_and_pipe_rows() -> None:
    pack, warnings = xsb.parse("5#|#@$.#|5#", pack_id="p")
    assert warnings == []
    assert pack.levels[0].level == Level.from_rows(["#####", "#@$.#", "#####"])


def test_rle_fixture_expands_counts_and_dash_floor() -> None:
    pack, _ = xsb.parse(_read("rle.xsb"), pack_id="rle")
    expected = ["########", "#@ $ . #", "# **   #", "#  $.  #", "########"]
    assert pack.levels[0].level.canonical_hash() == Level.from_rows(expected).canonical_hash()


def test_rle_multi_digit_count() -> None:
    pack, _ = xsb.parse("12#|#@$.7-#|12#", pack_id="p")
    assert pack.levels[0].level.width == 12


def test_crlf_bom_tabs_trailing_spaces_load_like_clean_file() -> None:
    clean, _ = xsb.parse(_read("clean.xsb"), pack_id="clean")
    messy, warnings = xsb.parse(_read("crlf_bom.sok"), pack_id="messy")
    assert warnings == []
    assert len(messy.levels) == 1
    assert messy.levels[0].title == "Messy"
    assert messy.levels[0].level.canonical_hash() == clean.levels[0].level.canonical_hash()


def test_invalid_level_in_collection_becomes_warning() -> None:
    pack, warnings = xsb.parse(_read("invalid_mixed.sok"), pack_id="mixed")
    assert [e.title for e in pack.levels] == ["Good one", "Good two"]
    assert len(warnings) == 1
    assert "level 2" in warnings[0] and "goals" in warnings[0] and "line 6" in warnings[0]


def test_valid_levels_keep_their_position_as_id() -> None:
    pack, _ = xsb.parse(_read("invalid_mixed.sok"), pack_id="mixed")
    assert [e.id for e in pack.levels] == ["1", "3"]


def test_bad_rle_becomes_warning() -> None:
    pack, warnings = xsb.parse("5#|#@$.#|5#\n\n5#|#@$.#|5\n", pack_id="p")
    assert len(pack.levels) == 1 and len(warnings) == 1


def test_text_without_any_board_gives_an_empty_pack() -> None:
    pack, warnings = xsb.parse("just words\n; a comment\n", pack_id="p")
    assert pack.levels == () and warnings == []


def test_dump_then_parse_roundtrip() -> None:
    a = Level.from_rows(["#####", "#@$.#", "#####"], title="A", author="Ann", comment="first")
    b = Level.from_rows(["  ####", "###  #", "#@$ .#", "######"])
    pack = Pack(id="p", title="Pack", author="Bob", levels=(LevelEntry("1", a), LevelEntry("2", b)))
    text = xsb.dump(pack)
    again, warnings = xsb.parse(text, pack_id="p")
    assert warnings == []
    assert (again.title, again.author) == ("Pack", "Bob")
    assert [e.level for e in again.levels] == [a, b]


def test_dump_writes_plain_rows_with_title_lines() -> None:
    a = Level.from_rows(["#####", "#@$.#", "#####"], title="A")
    text = xsb.dump(Pack(id="p", title="", levels=(LevelEntry("1", a),)))
    assert text == "#####\n#@$.#\n#####\nTitle: A\n"


@pytest.mark.parametrize("line", ["#####", "  #@$.#", "5#|#@$.#|5#", "#-_ #"])
def test_board_line_detection(line: str) -> None:
    assert xsb.is_board_line(line)


@pytest.mark.parametrize("line", ["", "   ", "123", "Title: x", "; #####", "Level 1"])
def test_non_board_lines(line: str) -> None:
    assert not xsb.is_board_line(line)
