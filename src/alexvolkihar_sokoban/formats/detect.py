"""``load_any``/``save_any``: the single entry point to level files for the CLI, the game and benchmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from alexvolkihar_sokoban.core.pack import Pack
from alexvolkihar_sokoban.formats import FormatError, jsonfmt, legacy, xsb

FileFormat = Literal["xsb", "legacy", "json"]
FormatChoice = Literal["auto", "xsb", "legacy", "json"]
FORMATS: tuple[FormatChoice, ...] = ("auto", "xsb", "legacy", "json")
XSB_EXTENSIONS = (".xsb", ".sok", ".txt")


def _read_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FormatError(f"cannot read the file ({exc.strerror or exc})", path=path) from exc
    if b"\x00" in raw:
        raise FormatError("binary file, not a level text", path=path)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormatError(f"not UTF-8 text (byte {exc.start})", path=path) from exc


def _guess(text: str, path: Path) -> FileFormat:
    """JSON by extension or a leading ``{``; legacy when the text has ``X`` and no ``#``; XSB otherwise."""
    if path.suffix.lower() == ".json" or text.removeprefix("﻿").lstrip().startswith("{"):
        return "json"
    if "X" in text and "#" not in text:
        return "legacy"
    return "xsb"


def detect_format(path: Path) -> FileFormat:
    return _guess(_read_text(path), path)


def _load_json(text: str, path: Path) -> tuple[Pack, list[str]]:
    try:
        data = json.loads(text.removeprefix("﻿"))
    except json.JSONDecodeError as exc:
        raise FormatError(f"invalid JSON: {exc.msg}", path=path, line=exc.lineno) from exc
    if not isinstance(data, dict):
        raise FormatError("the JSON root must be an object", path=path)
    warnings: list[str] = []
    if data.get("format") == jsonfmt.LEVEL_FORMAT:
        entry = jsonfmt.level_from_dict(data)
        return Pack(id=path.stem, title=path.stem, levels=(entry,)), warnings
    return jsonfmt.pack_from_dict(data, warnings=warnings), warnings


def load_any(path: Path, *, fmt: FormatChoice = "auto") -> tuple[Pack, list[str]]:
    """The pack in ``path`` and one warning per invalid level it skipped.

    A single-level file becomes a one-level pack named after the file (level id ``"1"`` for XSB and legacy
    files). Raises ``FormatError`` (with ``path`` set) when the file cannot be read, is malformed, or holds
    no valid level at all.
    """
    text = _read_text(path)
    kind = _guess(text, path) if fmt == "auto" else fmt
    try:
        if kind == "json":
            pack, warnings = _load_json(text, path)
        elif kind == "legacy":
            pack, warnings = legacy.parse(text, pack_id=path.stem), []
        else:
            pack, warnings = xsb.parse(text, pack_id=path.stem)
            if not pack.levels:
                reason = ("no valid level: " + "; ".join(warnings)) if warnings else "no level in the file"
                raise FormatError(reason)
    except FormatError as exc:
        if exc.path is not None:
            raise
        raise FormatError(exc.reason, path=path, line=exc.line) from exc
    return pack, warnings


def save_any(pack: Pack, path: Path) -> None:
    """Write ``pack`` as JSON (``.json``) or XSB (``.xsb``, ``.sok``, ``.txt``), UTF-8 with LF line ends.

    Missing parent folders are created. Raises ``FormatError`` for another extension and ``OSError`` when
    the file cannot be written.
    """
    suffix = path.suffix.lower()
    if suffix == ".json":
        text = json.dumps(jsonfmt.pack_to_dict(pack), indent=2, ensure_ascii=False) + "\n"
    elif suffix in XSB_EXTENSIONS:
        text = xsb.dump(pack)
    else:
        raise FormatError(f"unknown extension {path.suffix!r} (use .json, .xsb, .sok or .txt)", path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
