import json
from pathlib import Path

import pytest

from alexvolkihar_sokoban.cli import main
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.formats.detect import load_any
from alexvolkihar_sokoban.generator.api import generate


def test_generate_cli_prints_xsb(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["generate", "--preset", "easy", "--seed", "3"]) == 0
    captured = capsys.readouterr()
    rows = [line for line in captured.out.splitlines() if line and ":" not in line]
    level = Level.from_rows(rows)
    assert level.canonical_hash() == generate("easy", 3).entry.level.canonical_hash()
    assert "Title: easy-3" in captured.out
    assert "easy-3" in captured.err and "pushes" in captured.err


def test_generate_cli_writes_a_json_pack_with_par_and_seed(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "level.json"
    assert main(["generate", "--preset", "easy", "--seed", "4", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["levels"][0]["seed"] == 4 and data["levels"][0]["par"]["pushes"] >= 6
    pack, warnings = load_any(out)
    assert not warnings and pack.levels[0] == generate("easy", 4).entry


def test_generate_cli_rejects_unknown_preset_and_negative_seed() -> None:
    with pytest.raises(SystemExit):
        main(["generate", "--preset", "nightmare"])
    with pytest.raises(SystemExit):
        main(["generate", "--seed", "-1"])


def test_generate_cli_reports_an_unknown_extension(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["generate", "--preset", "easy", "--seed", "1", "--out", str(tmp_path / "x.bmp")]) == 2
    assert "extension" in capsys.readouterr().err


def test_generate_cli_reports_a_failed_generation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from alexvolkihar_sokoban.commands import generate as command
    from alexvolkihar_sokoban.generator.api import GenerationFailed

    def failing(*args: object, **kwargs: object) -> None:
        raise GenerationFailed("no level after 50 attempts")

    monkeypatch.setattr(command, "generate", failing)
    assert main(["generate", "--seed", "1"]) == 1
    assert "50 attempts" in capsys.readouterr().err


def test_generate_cli_interrupted_exits_130(monkeypatch: pytest.MonkeyPatch) -> None:
    from alexvolkihar_sokoban.commands import generate as command

    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(command, "generate", interrupted)
    assert main(["generate"]) == 130
