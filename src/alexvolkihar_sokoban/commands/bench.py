"""``bench [--suite quick] [--out FILE] [--csv FILE]`` and ``bench compare A B`` (spec 7.7, 10).

A run solves every level of a suite once and prints one row per level as it finishes, then the summary and
the machine block, and writes the JSON run to ``--out`` (default ``<data dir>/benchmarks/<run_id>.json``).
Limit hits are results, not failures. Exit code: 0 done, 2 unknown suite, no level to run, unwritable or
unreadable file, 130 interrupted (nothing written).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alexvolkihar_sokoban.benchmark import suites
from alexvolkihar_sokoban.benchmark.compare import compare, format_comparison
from alexvolkihar_sokoban.benchmark.export import BenchmarkFileError, read_json, write_csv, write_json
from alexvolkihar_sokoban.benchmark.machine import MachineInfo
from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult, run_suite
from alexvolkihar_sokoban.persistence.paths import data_dir

PROG = "alexvolkihar-sokoban bench"
DEFAULT_SUITE = "quick"
BENCHMARKS_DIR = "benchmarks"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--suite", default=DEFAULT_SUITE, metavar="ID", help="quick, standard or stress (default: quick)"
    )
    parser.add_argument(
        "--out", type=Path, default=None, metavar="FILE", help="JSON result (default: <data dir>/benchmarks/)"
    )
    parser.add_argument("--csv", type=Path, default=None, metavar="FILE", help="also write a CSV file")
    sub = parser.add_subparsers(dest="bench_command", metavar="compare")
    cmp = sub.add_parser(
        "compare", help="compare two benchmark runs", description="compare two benchmark runs"
    )
    cmp.add_argument("run_a", type=Path, metavar="A", help="reference run (JSON)")
    cmp.add_argument("run_b", type=Path, metavar="B", help="run to compare with A (JSON)")


def _error(message: str) -> int:
    print(f"{PROG}: {message}", file=sys.stderr)
    return 2


def _row(result: LevelResult) -> str:
    pushes = "-" if result.pushes is None else str(result.pushes)
    return (
        f"{result.label:<28} {result.status!s:<11} {pushes:>6} {result.nodes_expanded:>10} "
        f"{result.elapsed_ms:>8} ms {result.peak_mem_bytes // 1024:>8} KiB"
    )


def _machine_block(m: MachineInfo) -> list[str]:
    ram = "unknown" if m.ram_total_bytes is None else f"{m.ram_total_bytes / 2**30:.1f} GiB"
    os_line = f"{m.os} {m.os_version}" + (" (WSL)" if m.is_wsl else "")
    return [
        "machine:",
        f"  os: {os_line}",
        f"  arch: {m.arch}",
        f"  cpu: {m.cpu_model or 'unknown'} ({m.cpu_count_logical or '?'} logical)",
        f"  ram: {ram}",
        f"  python: {m.python}",
        f"  pygame-ce: {m.pygame_ce or 'not installed'}",
        f"  app: {m.app_version}",
    ]


def _summary_block(run: BenchmarkRun) -> list[str]:
    s = run.summary
    solver = run.solver
    return [
        f"suite: {run.suite_id}  solver: {solver['name']}/{solver['version']} ({solver['mode']})",
        f"solved {s.solved}/{s.total}  total {s.total_ms} ms  nodes/s {s.nodes_per_s}",
    ]


def _compare(args: argparse.Namespace) -> int:
    try:
        a, b = read_json(args.run_a), read_json(args.run_b)
    except BenchmarkFileError as exc:
        return _error(str(exc))
    print(format_comparison(compare(a, b)))
    return 0


def run(args: argparse.Namespace) -> int:
    if getattr(args, "bench_command", None) == "compare":
        return _compare(args)
    try:
        known = suites.load_suites()
    except ValueError as exc:
        return _error(str(exc))
    suite = known.get(args.suite)
    if suite is None:
        return _error(f"unknown suite {args.suite!r} (suites: {', '.join(known)})")

    packs, warnings = suites.load_bundled_packs()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    items, missing = suites.resolve(suite, packs)
    if missing:
        print(f"warning: skipped, not installed: {', '.join(missing)}", file=sys.stderr)
    if not items:
        return _error(f"no level to run in suite {suite.id!r}")

    print(
        f"{suite.title} benchmark: {len(items)} levels, limits {suite.limits.time_s:g} s / "
        f"{suite.limits.max_nodes} nodes per level"
    )
    print(f"{'level':<28} {'status':<11} {'pushes':>6} {'nodes':>10} {'time':>11} {'peak mem':>12}")
    try:
        result = run_suite(
            items,
            suite_id=suite.id,
            limits=suite.limits,
            on_level_done=lambda _i, r: print(_row(r), flush=True),
        )
    except KeyboardInterrupt:
        print(f"{PROG}: interrupted, nothing written", file=sys.stderr)
        return 130

    print()
    print("\n".join(_summary_block(result)))
    print("\n".join(_machine_block(result.machine)))

    override = getattr(args, "data_dir", None)
    out = (
        args.out or data_dir(Path(override) if override else None) / BENCHMARKS_DIR / f"{result.run_id}.json"
    )
    try:
        write_json(result, out)
        if args.csv is not None:
            write_csv(result, args.csv)
    except OSError as exc:
        return _error(f"cannot write the results: {exc}")
    print(f"results: {out}")
    if args.csv is not None:
        print(f"csv: {args.csv}")
    return 0
