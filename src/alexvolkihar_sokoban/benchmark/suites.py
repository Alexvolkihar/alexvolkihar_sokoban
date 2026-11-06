"""Benchmark suites (``data/benchmarks/suites.json``) and the packs they draw levels from (spec 7.7).

A suite item is ``"<pack_id>"`` (the whole pack) or ``"<pack_id>/<level_id>"`` (one level; the pack id ends
at the first ``/``). Items whose pack or level is absent are reported, never raised, so a missing pack only
shrinks a suite.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TypeGuard

from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.formats.jsonfmt import pack_from_dict
from alexvolkihar_sokoban.solver.api import SolveLimits

SUITES_FORMAT = "alexvolkihar-sokoban/benchmark-suites"
SUITES_VERSION = 1
EXTRA_PACK_ID = "bench-extra"


@dataclass(frozen=True)
class Suite:
    id: str
    title: str
    limits: SolveLimits
    items: tuple[str, ...]


def _data(name: str) -> Traversable:
    return files("alexvolkihar_sokoban").joinpath("data").joinpath(name)


def limits_from_dict(data: object) -> SolveLimits:
    """``{"time_ms": int > 0, "max_nodes": int > 0}``. Raises ``ValueError``."""
    if not isinstance(data, Mapping):
        raise ValueError("'limits' must be an object")
    time_ms, max_nodes = data.get("time_ms"), data.get("max_nodes")
    if not _positive_int(time_ms) or not _positive_int(max_nodes):
        raise ValueError("'limits' needs positive integers 'time_ms' and 'max_nodes'")
    return SolveLimits(time_s=time_ms / 1000, max_nodes=max_nodes)


def _positive_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def limits_to_dict(limits: SolveLimits) -> dict[str, int]:
    return {"time_ms": round(limits.time_s * 1000), "max_nodes": limits.max_nodes}


def _suite(data: object) -> Suite:
    if not isinstance(data, Mapping):
        raise ValueError("a suite must be an object")
    suite_id, title, items = data.get("id"), data.get("title"), data.get("items")
    if not isinstance(suite_id, str) or not suite_id or not isinstance(title, str):
        raise ValueError("a suite needs a non-empty 'id' and a 'title'")
    if not isinstance(items, list) or not items:
        raise ValueError(f"suite {suite_id!r}: 'items' must be a non-empty list")
    for item in items:
        if not isinstance(item, str) or not item.partition("/")[0]:
            raise ValueError(f"suite {suite_id!r}: bad item {item!r}")
    return Suite(suite_id, title, limits_from_dict(data.get("limits")), tuple(items))


def load_suites(path: Path | Traversable | None = None) -> dict[str, Suite]:
    """The suites of ``path`` (default: the bundled ``suites.json``) in file order. Raises ``ValueError``."""
    source = _data("benchmarks/suites.json") if path is None else path
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read the benchmark suites: {exc}") from exc
    if not isinstance(data, Mapping) or data.get("format") != SUITES_FORMAT:
        raise ValueError(f"'format' must be {SUITES_FORMAT!r}")
    if data.get("version") != SUITES_VERSION:
        raise ValueError(f"unsupported suites version {data.get('version')!r}")
    raw = data.get("suites")
    if not isinstance(raw, list):
        raise ValueError("'suites' must be a list")
    suites: dict[str, Suite] = {}
    for item in raw:
        suite = _suite(item)
        if suite.id in suites:
            raise ValueError(f"duplicate suite id {suite.id!r}")
        suites[suite.id] = suite
    return suites


def _read_pack(source: Traversable) -> tuple[Pack, list[str]]:
    warnings: list[str] = []
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    return pack_from_dict(data, warnings=warnings), warnings


def load_extra_pack() -> Pack:
    """The hidden ``bench-extra`` pack (benchmark-only levels: generated, unsolvable and very large ones)."""
    pack, _ = _read_pack(_data("benchmarks/extra.json"))
    return pack


def load_bundled_packs(root: Path | Traversable | None = None) -> tuple[dict[str, Pack], list[str]]:
    """Every ``*.json`` pack of ``root`` (default: the bundled ``data/levels``) plus ``bench-extra``.

    A broken file or level is skipped and described in the returned warnings; the first pack with a given
    id wins.
    """
    levels_root = _data("levels") if root is None else root
    sources: list[Traversable] = []
    warnings: list[str] = []
    try:
        sources = sorted(
            (c for c in levels_root.iterdir() if c.name.lower().endswith(".json")), key=lambda c: c.name
        )
    except OSError as exc:
        warnings.append(f"cannot list the bundled packs: {exc}")
    sources.append(_data("benchmarks/extra.json"))
    packs: dict[str, Pack] = {}
    for source in sources:
        try:
            pack, level_warnings = _read_pack(source)
        except (OSError, ValueError) as exc:  # FormatError and JSONDecodeError are ValueErrors
            warnings.append(f"pack {source.name} skipped: {exc}")
            continue
        warnings.extend(level_warnings)
        if pack.id in packs:
            warnings.append(f"pack {source.name} skipped: pack id {pack.id!r} already used")
            continue
        packs[pack.id] = pack
    return packs, warnings


def resolve(suite: Suite, packs: Mapping[str, Pack]) -> tuple[list[tuple[Pack, LevelEntry]], list[str]]:
    """The levels of ``suite`` in order, and the items that could not be found."""
    resolved: list[tuple[Pack, LevelEntry]] = []
    missing: list[str] = []
    for item in suite.items:
        pack_id, sep, level_id = item.partition("/")
        pack = packs.get(pack_id)
        if pack is None:
            missing.append(item)
        elif not sep:
            resolved.extend((pack, entry) for entry in pack.levels)
        else:
            try:
                resolved.append((pack, pack.entry(level_id)))
            except KeyError:
                missing.append(item)
    return resolved, missing
