import json
from pathlib import Path

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.formats import FormatError, detect, jsonfmt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "formats"
ROOM = ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"]


def test_detect_legacy_vs_xsb(tmp_path: Path) -> None:
    assert detect.detect_format(FIXTURES / "legacy_room.txt") == "legacy"
    assert detect.detect_format(FIXTURES / "multi.sok") == "xsb"
    assert detect.detect_format(FIXTURES / "rle.xsb") == "xsb"
    (tmp_path / "pack.txt").write_text('  {"format": "x"}', encoding="utf-8")
    assert detect.detect_format(tmp_path / "pack.txt") == "json"


def test_load_legacy_file_as_single_level_pack() -> None:
    pack, warnings = detect.load_any(FIXTURES / "legacy_room.txt")
    assert warnings == []
    assert pack.id == "legacy_room" and [e.id for e in pack.levels] == ["1"]
    assert pack.levels[0].level == Level.from_rows(ROOM)


def test_load_xsb_collection_keeps_warnings() -> None:
    pack, warnings = detect.load_any(FIXTURES / "invalid_mixed.sok")
    assert pack.id == "invalid_mixed" and len(pack.levels) == 2 and len(warnings) == 1


def test_crlf_bom_file_loads_like_clean_file() -> None:
    clean, _ = detect.load_any(FIXTURES / "clean.xsb")
    messy, _ = detect.load_any(FIXTURES / "crlf_bom.sok")
    assert messy.levels[0].level.canonical_hash() == clean.levels[0].level.canonical_hash()


def test_forced_format_overrides_detection(tmp_path: Path) -> None:
    path = tmp_path / "odd.txt"
    path.write_text("#####\n#@*.#\n#####\n", encoding="utf-8")  # '*' is a box in legacy
    with pytest.raises(FormatError):
        detect.load_any(path)  # auto → xsb: box already on a goal, one box left without a goal
    pack, _ = detect.load_any(path, fmt="legacy")
    assert pack.levels[0].level == Level.from_rows(["#####", "#@$.#", "#####"])


def test_json_pack_and_single_level_files(tmp_path: Path) -> None:
    entry = LevelEntry("t1", Level.from_rows(ROOM, title="T"), par=Par(1, 2, "rR", "push-astar/1"))
    pack = Pack(id="p", title="P", levels=(entry,))
    (tmp_path / "pack.json").write_text(json.dumps(jsonfmt.pack_to_dict(pack)), encoding="utf-8")
    (tmp_path / "one.json").write_text(json.dumps(jsonfmt.level_to_dict(entry)), encoding="utf-8")
    assert detect.load_any(tmp_path / "pack.json") == (pack, [])
    single, _ = detect.load_any(tmp_path / "one.json")
    assert (single.id, single.title, single.levels) == ("one", "one", (entry,))


def test_json_pack_with_an_invalid_level_gives_a_warning(tmp_path: Path) -> None:
    data = jsonfmt.pack_to_dict(Pack(id="p", title="P", levels=(LevelEntry("a", Level.from_rows(ROOM)),)))
    data["levels"] = [*data["levels"], {"id": "b", "rows": ["#####", "#@$ #", "#####"]}]  # type: ignore[misc]
    (tmp_path / "p.json").write_text(json.dumps(data), encoding="utf-8")
    pack, warnings = detect.load_any(tmp_path / "p.json")
    assert [e.id for e in pack.levels] == ["a"] and len(warnings) == 1


@pytest.mark.parametrize(
    "content,reason",
    [
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00", "text"),
        (b"\xff\xfe\xfa", "UTF-8"),
        (b"{not json", "JSON"),
        (b'{"format": "alexvolkihar-sokoban/settings", "version": 1}', "format"),
        (b"[1, 2]", "object"),
        (b"just a note\n", "no level"),
        (b"#####\n#@$ #\n#####\n", "no valid level"),
    ],
)
def test_broken_files_raise_format_error_with_path(tmp_path: Path, content: bytes, reason: str) -> None:
    path = tmp_path / "broken.sok"
    if content.startswith((b"{", b"[")):
        path = tmp_path / "broken.json"
    path.write_bytes(content)
    with pytest.raises(FormatError, match=reason) as info:
        detect.load_any(path)
    assert info.value.path == path


def test_missing_file_raises_format_error(tmp_path: Path) -> None:
    with pytest.raises(FormatError, match="cannot read"):
        detect.load_any(tmp_path / "nope.xsb")


@pytest.mark.parametrize("name", ["out.json", "out.xsb", "out.sok", "out.txt"])
def test_save_any_roundtrip(tmp_path: Path, name: str) -> None:
    pack, _ = detect.load_any(FIXTURES / "multi.sok")
    path = tmp_path / "sub" / name
    detect.save_any(pack, path)
    again, warnings = detect.load_any(path)
    assert warnings == []
    assert [e.level for e in again.levels] == [e.level for e in pack.levels]
    assert again.title == pack.title


def test_save_any_writes_lf_utf8(tmp_path: Path) -> None:
    pack = Pack(id="p", title="First steps — demo", levels=(LevelEntry("1", Level.from_rows(ROOM)),))
    detect.save_any(pack, tmp_path / "p.json")
    raw = (tmp_path / "p.json").read_bytes()
    assert b"\r\n" not in raw and "—".encode() in raw and raw.endswith(b"\n")


def test_save_any_rejects_unknown_extension(tmp_path: Path) -> None:
    pack, _ = detect.load_any(FIXTURES / "multi.sok")
    with pytest.raises(FormatError, match="extension"):
        detect.save_any(pack, tmp_path / "out.png")
