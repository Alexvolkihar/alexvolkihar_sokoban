"""JSON packs (``alexvolkihar-sokoban/pack``) and single levels (``alexvolkihar-sokoban/level``), spec 9.2.

The JSON Schemas live in ``schemas/``; this module checks the same rules by hand because ``jsonschema`` is
not a runtime dependency.
"""

from __future__ import annotations

from collections.abc import Mapping

from alexvolkihar_sokoban.core.level import InvalidLevelError, Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.formats import FormatError

PACK_FORMAT = "alexvolkihar-sokoban/pack"
LEVEL_FORMAT = "alexvolkihar-sokoban/level"
VERSION = 1


def _check_header(data: Mapping[str, object], fmt: str) -> None:
    if data.get("format") != fmt:
        raise FormatError(f"'format' must be {fmt!r}, got {data.get('format')!r}")
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != VERSION:
        raise FormatError(f"unsupported 'version' {version!r} (expected {VERSION})")


def _str(data: Mapping[str, object], key: str, *, required: bool = False) -> str:
    value = data.get(key, None if required else "")
    if not isinstance(value, str) or (required and not value):
        raise FormatError(f"'{key}' must be a {'non-empty ' if required else ''}string")
    return value


def _count(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise FormatError(f"par '{key}' must be a non-negative integer")
    return value


def _par(value: object) -> Par | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise FormatError("'par' must be an object or null")
    return Par(
        pushes=_count(value, "pushes"),
        moves=_count(value, "moves"),
        lurd=_str(value, "lurd", required=False),
        solver=_str(value, "solver", required=True),
    )


def _entry(data: Mapping[str, object]) -> LevelEntry:
    level_id = _str(data, "id", required=True)
    rows = data.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
        raise FormatError("'rows' must be a list of strings")
    seed = data.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise FormatError("'seed' must be an integer or null")
    par = _par(data.get("par"))
    try:
        level = Level.from_rows(
            [str(row) for row in rows],
            title=_str(data, "title"),
            author=_str(data, "author"),
            comment=_str(data, "comment"),
        )
    except InvalidLevelError as exc:
        raise FormatError(str(exc)) from exc
    return LevelEntry(level_id, level, par=par, seed=seed)


def _describe(raw: object, index: int) -> str:
    if isinstance(raw, Mapping) and isinstance(raw.get("id"), str):
        return repr(raw["id"])
    return f"#{index + 1}"


def pack_from_dict(data: Mapping[str, object], *, warnings: list[str] | None = None) -> Pack:
    """A pack from decoded JSON. Raises ``FormatError`` on any problem.

    When ``warnings`` is given, a broken or invalid level (or a duplicate id) is skipped and described in it
    instead; problems with the pack itself still raise.
    """
    if not isinstance(data, Mapping):
        raise FormatError("a pack must be a JSON object")
    _check_header(data, PACK_FORMAT)
    pack_id = _str(data, "id", required=True)
    hidden = data.get("hidden", False)
    if not isinstance(hidden, bool):
        raise FormatError("'hidden' must be a boolean")
    raw_levels = data.get("levels")
    if not isinstance(raw_levels, list):
        raise FormatError("'levels' must be a list")
    entries: list[LevelEntry] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_levels):
        try:
            if not isinstance(raw, Mapping):
                raise FormatError("a level must be a JSON object")
            entry = _entry(raw)
            if entry.id in seen:
                raise FormatError(f"duplicate level id {entry.id!r}")
        except FormatError as exc:
            message = f"level {_describe(raw, index)}: {exc}"
            if warnings is None:
                raise FormatError(message) from exc
            warnings.append(f"{pack_id} {message}")
            continue
        seen.add(entry.id)
        entries.append(entry)
    return Pack(
        id=pack_id,
        title=_str(data, "title"),
        levels=tuple(entries),
        author=_str(data, "author"),
        license=_str(data, "license"),
        source=_str(data, "source"),
        hidden=hidden,
    )


def level_from_dict(data: Mapping[str, object]) -> LevelEntry:
    """A single-level file. Raises ``FormatError`` on any problem."""
    if not isinstance(data, Mapping):
        raise FormatError("a level must be a JSON object")
    _check_header(data, LEVEL_FORMAT)
    return _entry(data)


def _entry_to_dict(entry: LevelEntry) -> dict[str, object]:
    level = entry.level
    out: dict[str, object] = {"id": entry.id, "title": level.title}
    if level.author:
        out["author"] = level.author
    if level.comment:
        out["comment"] = level.comment
    out["rows"] = level.canonical_text().split("\n")
    par = entry.par
    out["par"] = (
        None
        if par is None
        else {"pushes": par.pushes, "moves": par.moves, "lurd": par.lurd, "solver": par.solver}
    )
    if entry.seed is not None:
        out["seed"] = entry.seed
    return out


def pack_to_dict(pack: Pack) -> dict[str, object]:
    return {
        "format": PACK_FORMAT,
        "version": VERSION,
        "id": pack.id,
        "title": pack.title,
        "author": pack.author,
        "license": pack.license,
        "source": pack.source,
        "hidden": pack.hidden,
        "levels": [_entry_to_dict(entry) for entry in pack.levels],
    }


def level_to_dict(entry: LevelEntry) -> dict[str, object]:
    return {"format": LEVEL_FORMAT, "version": VERSION, **_entry_to_dict(entry)}
