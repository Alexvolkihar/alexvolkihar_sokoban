"""Benchmark run files: JSON (``alexvolkihar-sokoban/benchmark``, spec 9.6) and CSV (one row per level).

``schemas/benchmark.schema.json`` describes the JSON; ``run_from_dict`` checks the same rules by hand because
``jsonschema`` is not a runtime dependency.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

from alexvolkihar_sokoban.benchmark.machine import MachineInfo
from alexvolkihar_sokoban.benchmark.runner import MEASURE, BenchmarkRun, LevelResult, Summary
from alexvolkihar_sokoban.benchmark.suites import limits_from_dict, limits_to_dict
from alexvolkihar_sokoban.solver.api import SolveStatus

BENCHMARK_FORMAT = "alexvolkihar-sokoban/benchmark"
BENCHMARK_VERSION = 1
CSV_COLUMNS = (
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
)


class BenchmarkFileError(ValueError):
    """A benchmark file that cannot be read back."""


def _machine_to_dict(m: MachineInfo) -> dict[str, object]:
    return {
        "os": m.os,
        "os_version": m.os_version,
        "arch": m.arch,
        "is_wsl": m.is_wsl,
        "cpu_model": m.cpu_model,
        "cpu_count_logical": m.cpu_count_logical,
        "ram_total_bytes": m.ram_total_bytes,
        "python": m.python,
        "pygame_ce": m.pygame_ce,
        "app_version": m.app_version,
    }


def _result_to_dict(r: LevelResult) -> dict[str, object]:
    return {
        "pack_id": r.pack_id,
        "level_id": r.level_id,
        "level_hash": r.level_hash,
        "status": str(r.status),
        "pushes": r.pushes,
        "moves": r.moves,
        "nodes_expanded": r.nodes_expanded,
        "nodes_generated": r.nodes_generated,
        "elapsed_ms": r.elapsed_ms,
        "peak_mem_bytes": r.peak_mem_bytes,
    }


def run_to_dict(run: BenchmarkRun) -> dict[str, object]:
    s = run.summary
    return {
        "format": BENCHMARK_FORMAT,
        "version": BENCHMARK_VERSION,
        "run_id": run.run_id,
        "created_at": run.created_at,
        "app_version": run.app_version,
        "solver": dict(run.solver),
        "machine": _machine_to_dict(run.machine),
        "suite": {"id": run.suite_id, "limits": limits_to_dict(run.limits)},
        "measure": MEASURE,
        "results": [_result_to_dict(r) for r in run.results],
        "summary": {
            "solved": s.solved,
            "total": s.total,
            "total_ms": s.total_ms,
            "nodes_per_s": s.nodes_per_s,
        },
    }


# --- reading ---------------------------------------------------------------------------------------------


def _is_count(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _obj(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise BenchmarkFileError(f"'{key}' must be an object")
    return value


def _text(data: Mapping[str, object], key: str, *, nullable: bool = False) -> str | None:
    value = data.get(key)
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise BenchmarkFileError(f"'{key}' must be a string")
    return value


def _req_text(data: Mapping[str, object], key: str) -> str:
    value = _text(data, key)
    assert value is not None  # _text only returns None when nullable
    return value


def _count(data: Mapping[str, object], key: str, *, nullable: bool = False) -> int | None:
    value = data.get(key)
    if value is None and nullable:
        return None
    if not _is_count(value):
        raise BenchmarkFileError(f"'{key}' must be a non-negative integer")
    return value


def _req_count(data: Mapping[str, object], key: str) -> int:
    value = _count(data, key)
    assert value is not None  # _count only returns None when nullable
    return value


def _machine(data: Mapping[str, object]) -> MachineInfo:
    is_wsl = data.get("is_wsl")
    if not isinstance(is_wsl, bool):
        raise BenchmarkFileError("'is_wsl' must be a boolean")
    return MachineInfo(
        os=_req_text(data, "os"),
        os_version=_req_text(data, "os_version"),
        arch=_req_text(data, "arch"),
        is_wsl=is_wsl,
        cpu_model=_text(data, "cpu_model", nullable=True),
        cpu_count_logical=_count(data, "cpu_count_logical", nullable=True),
        ram_total_bytes=_count(data, "ram_total_bytes", nullable=True),
        python=_req_text(data, "python"),
        pygame_ce=_text(data, "pygame_ce", nullable=True),
        app_version=_req_text(data, "app_version"),
    )


def _result(data: object) -> LevelResult:
    if not isinstance(data, Mapping):
        raise BenchmarkFileError("a result must be an object")
    try:
        status = SolveStatus(_req_text(data, "status"))
    except ValueError as exc:  # BenchmarkFileError is a ValueError too
        raise BenchmarkFileError(f"unknown status {data.get('status')!r}") from exc
    return LevelResult(
        pack_id=_req_text(data, "pack_id"),
        level_id=_req_text(data, "level_id"),
        level_hash=_req_text(data, "level_hash"),
        status=status,
        pushes=_count(data, "pushes", nullable=True),
        moves=_count(data, "moves", nullable=True),
        nodes_expanded=_req_count(data, "nodes_expanded"),
        nodes_generated=_req_count(data, "nodes_generated"),
        elapsed_ms=_req_count(data, "elapsed_ms"),
        peak_mem_bytes=_req_count(data, "peak_mem_bytes"),
    )


def run_from_dict(data: Mapping[str, object]) -> BenchmarkRun:
    """A run from decoded JSON. Raises ``BenchmarkFileError`` on any problem."""
    if not isinstance(data, Mapping):
        raise BenchmarkFileError("a benchmark run must be a JSON object")
    if data.get("format") != BENCHMARK_FORMAT:
        raise BenchmarkFileError(f"'format' must be {BENCHMARK_FORMAT!r}, got {data.get('format')!r}")
    if data.get("version") != BENCHMARK_VERSION or isinstance(data.get("version"), bool):
        raise BenchmarkFileError(f"unsupported 'version' {data.get('version')!r}")
    solver = _obj(data, "solver")
    suite = _obj(data, "suite")
    summary = _obj(data, "summary")
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        raise BenchmarkFileError("'results' must be a list")
    try:
        limits = limits_from_dict(suite.get("limits"))
    except ValueError as exc:
        raise BenchmarkFileError(str(exc)) from exc
    return BenchmarkRun(
        run_id=_req_text(data, "run_id"),
        created_at=_req_text(data, "created_at"),
        app_version=_req_text(data, "app_version"),
        solver={key: _req_text(solver, key) for key in ("name", "version", "mode")},
        machine=_machine(_obj(data, "machine")),
        suite_id=_req_text(suite, "id"),
        limits=limits,
        results=tuple(_result(r) for r in raw_results),
        summary=Summary(
            solved=_req_count(summary, "solved"),
            total=_req_count(summary, "total"),
            total_ms=_req_count(summary, "total_ms"),
            nodes_per_s=_req_count(summary, "nodes_per_s"),
        ),
    )


# --- files -----------------------------------------------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    """Write through ``<name>.tmp`` in the same directory, ``fsync``, then ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(run: BenchmarkRun, path: Path) -> None:
    """Write the run as JSON. Raises ``OSError`` when the file cannot be written."""
    _write_atomic(path, json.dumps(run_to_dict(run), indent=2, ensure_ascii=False) + "\n")


def write_csv(run: BenchmarkRun, path: Path) -> None:
    """One header row, then one row per level (empty cells for unknown pushes/moves)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for result in run.results:
        row = _result_to_dict(result)
        writer.writerow(["" if row[c] is None else row[c] for c in CSV_COLUMNS])
    _write_atomic(path, buffer.getvalue())


def read_json(path: Path) -> BenchmarkRun:
    """Read a run written by ``write_json``. Raises ``BenchmarkFileError`` (unreadable, invalid)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise BenchmarkFileError(f"{path}: cannot read the file ({exc.strerror or exc})") from exc
    except ValueError as exc:
        raise BenchmarkFileError(f"{path}: invalid JSON ({exc})") from exc
    try:
        return run_from_dict(data)
    except BenchmarkFileError as exc:
        raise BenchmarkFileError(f"{path}: {exc}") from exc
