"""``bench compare A B``: per-level and total deltas between two runs (spec 7.7).

Levels are matched by canonical hash (spec 9.1), so a renamed or moved level still lines up and an edited
level shows as two different levels.
"""

from __future__ import annotations

from dataclasses import dataclass

from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult


def _pct(a: int, b: int) -> float | None:
    return (b - a) * 100 / a if a > 0 else None


@dataclass(frozen=True)
class LevelDelta:
    a: LevelResult | None
    b: LevelResult | None

    @property
    def _ref(self) -> LevelResult:
        ref = self.a or self.b
        assert ref is not None  # compare() never builds a delta without either side
        return ref

    @property
    def label(self) -> str:
        return self._ref.label

    @property
    def level_id(self) -> str:
        return self._ref.level_id

    @property
    def time_pct(self) -> float | None:
        """Time change in percent of A (``None`` when a side is missing or A took 0 ms)."""
        if self.a is None or self.b is None:
            return None
        return _pct(self.a.elapsed_ms, self.b.elapsed_ms)

    @property
    def nodes_delta(self) -> int | None:
        if self.a is None or self.b is None:
            return None
        return self.b.nodes_expanded - self.a.nodes_expanded

    @property
    def status_changed(self) -> bool:
        return self.a is not None and self.b is not None and self.a.status != self.b.status


@dataclass(frozen=True)
class Comparison:
    a: BenchmarkRun
    b: BenchmarkRun
    levels: tuple[LevelDelta, ...]

    @property
    def total_ms(self) -> tuple[int, int]:
        return (self.a.summary.total_ms, self.b.summary.total_ms)

    @property
    def solved(self) -> tuple[int, int]:
        return (self.a.summary.solved, self.b.summary.solved)

    @property
    def nodes(self) -> tuple[int, int]:
        return (
            sum(r.nodes_expanded for r in self.a.results),
            sum(r.nodes_expanded for r in self.b.results),
        )

    @property
    def nodes_per_s(self) -> tuple[int, int]:
        return (self.a.summary.nodes_per_s, self.b.summary.nodes_per_s)

    @property
    def changed(self) -> tuple[str, ...]:
        """Labels of the levels whose status differs between A and B."""
        return tuple(d.label for d in self.levels if d.status_changed)


def compare(a: BenchmarkRun, b: BenchmarkRun) -> Comparison:
    """Pair the levels of ``a`` and ``b``: A's order first, then the levels only B has."""
    by_hash = {r.level_hash: r for r in b.results}
    deltas = [LevelDelta(r, by_hash.pop(r.level_hash, None)) for r in a.results]
    deltas.extend(LevelDelta(None, r) for r in b.results if r.level_hash in by_hash)
    return Comparison(a, b, tuple(deltas))


def _fmt_pct(pct: float | None) -> str:
    return "-" if pct is None else f"{pct:+.1f}%"


def _fmt_int(value: int | None, suffix: str = "") -> str:
    return "-" if value is None else f"{value}{suffix}"


def _fmt_signed(value: int | None) -> str:
    return "-" if value is None else f"{value:+d}"


def _describe(label: str, run: BenchmarkRun) -> str:
    m = run.machine
    cpu = m.cpu_model or "unknown CPU"
    return f"{label}: {run.run_id}  suite {run.suite_id}  {cpu}, {m.os} {m.os_version}, {m.python}"


def format_comparison(c: Comparison) -> str:
    """A plain-text report: both runs, one row per level, totals, then the status changes."""
    rows: list[tuple[str, ...]] = [
        ("level", "status A", "status B", "time A", "time B", "time", "nodes A", "nodes B", "nodes")
    ]
    for d in c.levels:
        rows.append(
            (
                d.label,
                "-" if d.a is None else str(d.a.status),
                "-" if d.b is None else str(d.b.status),
                _fmt_int(None if d.a is None else d.a.elapsed_ms, " ms"),
                _fmt_int(None if d.b is None else d.b.elapsed_ms, " ms"),
                _fmt_pct(d.time_pct),
                _fmt_int(None if d.a is None else d.a.nodes_expanded),
                _fmt_int(None if d.b is None else d.b.nodes_expanded),
                _fmt_signed(d.nodes_delta),
            )
        )
    (ms_a, ms_b), (n_a, n_b) = c.total_ms, c.nodes
    rows.append(
        (
            "total",
            f"{c.solved[0]}/{len(c.a.results)} solved",
            f"{c.solved[1]}/{len(c.b.results)} solved",
            f"{ms_a} ms",
            f"{ms_b} ms",
            _fmt_pct(_pct(ms_a, ms_b)),
            str(n_a),
            str(n_b),
            _fmt_signed(n_b - n_a),
        )
    )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = [_describe("A", c.a), _describe("B", c.b), ""]
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [
            cell.rjust(w) for cell, w in zip(row[1:], widths[1:], strict=True)
        ]
        lines.append("  ".join(cells).rstrip())
    nps_a, nps_b = c.nodes_per_s
    lines.append("")
    lines.append(f"nodes/s: {nps_a} -> {nps_b} ({_fmt_pct(_pct(nps_a, nps_b))})")
    for d in c.levels:
        if d.status_changed and d.a is not None and d.b is not None:
            lines.append(f"! status changed: {d.label} {d.a.status} -> {d.b.status}")
    return "\n".join(lines)
