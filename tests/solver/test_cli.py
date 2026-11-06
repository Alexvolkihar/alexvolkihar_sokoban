from pathlib import Path

import pytest

from alexvolkihar_sokoban.cli import main
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.lurd import replay

ROOM_LEGACY = "XXXXXXX\nX.   .X\nX  *  X\nX *   X\nX@    X\nXXXXXXX\n"
SEALED_LEGACY = "XXXXXXX\nX@  X.X\nX * *.X\nX   X X\nXXXXXXX\n"
BIG_XSB = "\n".join(
    [
        "##########",
        "#@       #",
        "# $ $ $  #",
        "#  $ $ $ #",
        "#        #",
        "#  ....  #",
        "#   ..   #",
        "##########",
    ]
)


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def output_fields(out: str) -> dict[str, str]:
    fields = {}
    for line in out.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_solve_legacy_file_prints_a_replayable_solution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["solve", write(tmp_path, "room.txt", ROOM_LEGACY)]) == 0
    fields = output_fields(capsys.readouterr().out)
    assert fields["status"] == "solved"
    level = Level.from_rows(ROOM_LEGACY.replace("X", "#").replace("*", "$").splitlines())
    assert replay(level, fields["lurd"]).is_solved
    assert int(fields["pushes"]) == sum(c.isupper() for c in fields["lurd"])
    assert int(fields["moves"]) == len(fields["lurd"])
    for key in ("nodes", "time"):
        assert fields[key]


def test_solve_xsb_file_in_fast_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, "one.xsb", "#######\n#@$  .#\n#######\n")
    assert main(["solve", path, "--mode", "fast"]) == 0
    assert output_fields(capsys.readouterr().out)["lurd"] == "RRR"


def test_unsolvable_exits_with_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", write(tmp_path, "sealed.txt", SEALED_LEGACY)]) == 1
    assert output_fields(capsys.readouterr().out)["status"] == "unsolvable"


def test_limit_exits_with_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, "big.xsb", BIG_XSB)
    assert main(["solve", path, "--max-nodes", "5", "--time-limit", "5"]) == 3
    fields = output_fields(capsys.readouterr().out)
    assert fields["status"] == "limit_nodes"
    assert "lurd" not in fields


def test_missing_or_invalid_file_exits_with_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", str(tmp_path / "nope.xsb")]) == 2
    assert main(["solve", write(tmp_path, "bad.xsb", "#####\n#@$ #\n#####\n")]) == 2
    err = capsys.readouterr().err
    assert "nope.xsb" in err and "bad.xsb" in err


def test_unknown_level_id_exits_with_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", write(tmp_path, "room.txt", ROOM_LEGACY), "--level", "zzz"]) == 2
    assert "zzz" in capsys.readouterr().err


@pytest.mark.parametrize("option", [["--max-nodes", "0"], ["--time-limit", "0"], ["--mode", "slow"]])
def test_bad_options_are_rejected(tmp_path: Path, option: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["solve", write(tmp_path, "room.txt", ROOM_LEGACY), *option])
    assert exc.value.code == 2


def test_picks_a_level_of_a_collection_by_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = "Title: first\n#######\n#@$  .#\n#######\n\nTitle: second\n######\n#@$ .#\n######\n"
    path = write(tmp_path, "two.sok", text)
    assert main(["solve", path, "--level", "2"]) == 0
    fields = output_fields(capsys.readouterr().out)
    assert fields["level"] == "two/2" and fields["lurd"] == "RR"
