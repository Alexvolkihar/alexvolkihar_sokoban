import csv
import json
from pathlib import Path

import pytest

from alexvolkihar_sokoban.benchmark import suites
from alexvolkihar_sokoban.benchmark.export import read_json, write_json
from alexvolkihar_sokoban.cli import main
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.solver.api import SolveStatus

FIXTURE = Pack(
    "first-steps",
    "Fixture",
    (
        LevelEntry("1", Level.from_rows(["#####", "#@$.#", "#####"])),
        LevelEntry("2", Level.from_rows(["######", "#@$ .#", "#    #", "######"])),
    ),
)


@pytest.fixture
def fixture_packs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suites, "load_bundled_packs", lambda root=None: ({FIXTURE.id: FIXTURE}, []))


def test_bench_cli_quick_on_fixture_pack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fixture_packs: None
) -> None:
    code = main(["--data-dir", str(tmp_path), "bench", "--suite", "quick"])
    out = capsys.readouterr().out
    assert code == 0
    written = list((tmp_path / "benchmarks").glob("*.json"))
    assert len(written) == 1
    run = read_json(written[0])
    assert run.suite_id == "quick" and written[0].stem == run.run_id
    assert [(r.level_id, r.status) for r in run.results] == [
        ("1", SolveStatus.SOLVED),
        ("2", SolveStatus.SOLVED),
    ]
    assert "first-steps/1" in out and "first-steps/2" in out
    assert "solved 2/2" in out.lower()
    assert "nodes/s" in out.lower()
    assert "cpu" in out.lower()
    assert str(written[0]) in out


def test_bench_cli_out_and_csv(tmp_path: Path, fixture_packs: None) -> None:
    out_json, out_csv = tmp_path / "r" / "run.json", tmp_path / "r" / "run.csv"
    code = main(
        ["--data-dir", str(tmp_path / "data"), "bench", "--out", str(out_json), "--csv", str(out_csv)]
    )
    assert code == 0
    assert read_json(out_json).suite_id == "quick"
    with out_csv.open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.reader(fh))) == 3
    assert not (tmp_path / "data" / "benchmarks").exists() or not list(
        (tmp_path / "data" / "benchmarks").iterdir()
    )


def test_bench_cli_unknown_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fixture_packs: None
) -> None:
    assert main(["--data-dir", str(tmp_path), "bench", "--suite", "nope"]) == 2
    err = capsys.readouterr().err
    assert "nope" in err and "quick" in err


def test_bench_cli_reports_missing_items_and_nothing_to_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(suites, "load_bundled_packs", lambda root=None: ({}, ["pack x skipped"]))
    assert main(["--data-dir", str(tmp_path), "bench"]) == 2
    err = capsys.readouterr().err
    assert "first-steps" in err and "pack x skipped" in err


def test_bench_compare(tmp_path: Path, capsys: pytest.CaptureFixture[str], fixture_packs: None) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["--data-dir", str(tmp_path), "bench", "--out", str(a)]) == 0
    run = read_json(a)
    write_json(run, b)
    capsys.readouterr()
    assert main(["bench", "compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "first-steps/1" in out and run.run_id in out


def test_bench_compare_unreadable_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "x"}), encoding="utf-8")
    assert main(["bench", "compare", str(bad), str(tmp_path / "missing.json")]) == 2
    assert "bad.json" in capsys.readouterr().err
