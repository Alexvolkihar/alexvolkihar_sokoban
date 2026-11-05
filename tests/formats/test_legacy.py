from pathlib import Path

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.formats import FormatError, legacy

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "formats"
TEST1 = ["######", "#.  .#", "#    #", "# $$ #", "#@   #", "######"]


def test_legacy_symbols() -> None:
    pack = legacy.parse("XXXXX\nX@*.X\nXXXXX\n", pack_id="tiny")
    assert pack.levels[0].level == Level.from_rows(["#####", "#@$.#", "#####"])


def test_single_level_pack_takes_its_id_from_the_argument() -> None:
    pack = legacy.parse((FIXTURES / "legacy_test1.txt").read_text(encoding="utf-8"), pack_id="test1")
    assert (pack.id, pack.title) == ("test1", "test1")
    assert [e.id for e in pack.levels] == ["1"]
    assert pack.levels[0].level == Level.from_rows(TEST1)


def test_crlf_bom_tabs_trailing_spaces_load_like_clean_file() -> None:
    clean = (FIXTURES / "legacy_test1.txt").read_text(encoding="utf-8")
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


@pytest.mark.parametrize("n", range(1, 12))
def test_every_original_lama_level_loads(n: int) -> None:
    path = Path(__file__).resolve().parents[2] / "legacy" / "level" / f"test{n}.txt"
    assert legacy.parse(path.read_text(encoding="utf-8"), pack_id=path.stem).levels
