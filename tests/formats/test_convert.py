import json
from pathlib import Path

import pytest

from alexvolkihar_sokoban.cli import main
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.formats import detect, jsonfmt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "formats"
ROOM = ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"]


def test_convert_legacy_to_json_cli(tmp_path: Path) -> None:
    out = tmp_path / "room.json"
    assert main(["convert", str(FIXTURES / "legacy_room.txt"), str(out)]) == 0
    pack = jsonfmt.pack_from_dict(json.loads(out.read_text(encoding="utf-8")))
    assert pack.id == "legacy_room"
    assert pack.levels[0].level == Level.from_rows(ROOM)


def test_convert_json_to_xsb_and_back(tmp_path: Path) -> None:
    mid, out = tmp_path / "multi.json", tmp_path / "again.sok"
    assert main(["convert", str(FIXTURES / "multi.sok"), str(mid)]) == 0
    assert main(["convert", str(mid), str(out)]) == 0
    original, _ = detect.load_any(FIXTURES / "multi.sok")
    again, _ = detect.load_any(out)
    assert [e.level for e in again.levels] == [e.level for e in original.levels]


def test_convert_with_forced_format(tmp_path: Path) -> None:
    src, out = tmp_path / "odd.txt", tmp_path / "odd.xsb"
    src.write_text("#####\n#@*.#\n#####\n", encoding="utf-8")
    assert main(["convert", "--format", "legacy", str(src), str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("Title: odd\n\n#####\n#@$.#\n#####")


def test_convert_reports_skipped_levels(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "mixed.json"
    assert main(["convert", str(FIXTURES / "invalid_mixed.sok"), str(out)]) == 0
    err = capsys.readouterr().err
    assert "warning" in err and "level 2" in err
    assert len(detect.load_any(out)[0].levels) == 2


def test_convert_missing_input_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "x.json"
    assert main(["convert", str(tmp_path / "nope.xsb"), str(out)]) == 1
    assert "nope.xsb" in capsys.readouterr().err and not out.exists()


def test_convert_unknown_output_extension_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["convert", str(FIXTURES / "multi.sok"), str(tmp_path / "x.png")]) == 1
    assert "extension" in capsys.readouterr().err


def test_convert_unwritable_output_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    assert main(["convert", str(FIXTURES / "multi.sok"), str(blocker / "out.json")]) == 1
    assert "cannot write" in capsys.readouterr().err


def test_convert_rejects_unknown_format_choice(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(["convert", "--format", "png", "a", "b"])
    assert info.value.code == 2
