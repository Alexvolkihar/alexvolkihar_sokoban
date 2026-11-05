import csv
import json
from pathlib import Path

import jsonschema
import pytest

from alexvolkihar_sokoban.benchmark.export import (
    BENCHMARK_FORMAT,
    BenchmarkFileError,
    read_json,
    run_from_dict,
    run_to_dict,
    write_csv,
    write_json,
)
from alexvolkihar_sokoban.benchmark.machine import MachineInfo
from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult, Summary
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveStatus

ROOT = Path(__file__).resolve().parents[2]
MACHINE = MachineInfo(
    "Linux",
    "Ubuntu 24.04 (kernel 6.8.0)",
    "x86_64",
    True,
    "Some CPU",
    8,
    16 * 2**30,
    "CPython 3.13.1",
    "2.5.2",
    "0.1.0",
)
RUN = BenchmarkRun(
    run_id="2026-11-05T14-03-22Z-a1b2",
    created_at="2026-11-05T14:03:22Z",
    app_version="0.1.0",
    solver={"name": "push-astar", "version": "1", "mode": "optimal"},
    machine=MACHINE,
    suite_id="quick",
    limits=SolveLimits(10.0, 1_000_000),
    results=(
        LevelResult(
            "lama-original", "test1", "sha256:" + "a" * 64, SolveStatus.SOLVED, 4, 9, 10, 30, 12, 2048
        ),
        LevelResult(
            "lama-original",
            "test2",
            "sha256:" + "b" * 64,
            SolveStatus.LIMIT_TIME,
            None,
            None,
            5000,
            9000,
            10000,
            4096,
        ),
    ),
    summary=Summary(1, 2, 10012, 499),
)


def schema() -> dict[str, object]:
    loaded: dict[str, object] = json.loads((ROOT / "schemas" / "benchmark.schema.json").read_text("utf-8"))
    return loaded


def test_json_roundtrip_and_schema(tmp_path: Path) -> None:
    data = run_to_dict(RUN)
    assert data["format"] == BENCHMARK_FORMAT and data["version"] == 1
    assert data["measure"] == "tracemalloc"
    assert data["suite"] == {"id": "quick", "limits": {"time_ms": 10000, "max_nodes": 1_000_000}}
    jsonschema.validate(data, schema())
    assert run_from_dict(data) == RUN
    path = tmp_path / "out" / "run.json"
    write_json(RUN, path)
    assert read_json(path) == RUN
    jsonschema.validate(json.loads(path.read_text("utf-8")), schema())
    assert not list(path.parent.glob("*.tmp"))


def test_schema_rejects_a_hostname_field() -> None:
    data = run_to_dict(RUN)
    machine = data["machine"]
    assert isinstance(machine, dict)
    machine["hostname"] = "box"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(format="other"),
        lambda d: d.update(version=2),
        lambda d: d["results"][0].update(status="won"),
        lambda d: d["results"][0].update(elapsed_ms="12"),
        lambda d: d.pop("summary"),
        lambda d: d["machine"].update(is_wsl="yes"),
        lambda d: d["suite"]["limits"].update(time_ms=0),
    ],
)
def test_run_from_dict_rejects_bad_data(mutate) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(json.dumps(run_to_dict(RUN)))
    mutate(data)
    with pytest.raises(BenchmarkFileError):
        run_from_dict(data)


def test_read_json_reports_unreadable_files(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkFileError):
        read_json(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(BenchmarkFileError):
        read_json(bad)


def test_csv_has_one_row_per_level_and_header(tmp_path: Path) -> None:
    path = tmp_path / "run.csv"
    write_csv(RUN, path)
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == [
        "pack_id",
        "level_id",
        "level_hash",
        "status",
        "pushes",
        "moves",
        "nodes_expanded",
        "nodes_generated",
        "elapsed_ms",
        "peak_mem_bytes",
    ]
    assert len(rows) == 1 + len(RUN.results)
    assert rows[1] == [
        "lama-original",
        "test1",
        "sha256:" + "a" * 64,
        "solved",
        "4",
        "9",
        "10",
        "30",
        "12",
        "2048",
    ]
    assert rows[2][3:6] == ["limit_time", "", ""]
