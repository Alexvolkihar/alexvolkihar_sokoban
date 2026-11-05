"""Versioned, atomic JSON files in the data directory (spec 7.6).

Every file is an object whose first keys are ``"format"`` and ``"version"``. ``load`` never raises for a bad
file: a corrupt one is renamed ``<name>.corrupt-<UTC timestamp>.json``, a newer one is left untouched and the
store refuses to overwrite it. ``save`` never raises for an I/O failure: it logs and returns ``False``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from alexvolkihar_sokoban.persistence.migrations import MigrationError, MigrationRegistry

LoadStatus = Literal["ok", "missing", "corrupt", "too_new", "migrated"]

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    data: dict[str, object] | None
    status: LoadStatus
    backup_path: Path | None = None


class _BadFile(Exception):
    pass


class JsonStore:
    def __init__(self, root: Path, migrations: MigrationRegistry | None = None) -> None:
        self.root = Path(root)
        self.migrations = migrations if migrations is not None else MigrationRegistry()
        self._read_only: set[str] = set()

    def path(self, name: str) -> Path:
        """``<root>/<name>.json``; ``name`` may hold ``/`` for sub-directories but never escape the root."""
        parts = name.split("/")
        if not name or "\\" in name or any(p in ("", ".", "..") for p in parts) or ":" in name:
            raise ValueError(f"invalid store name: {name!r}")
        return self.root.joinpath(*PurePosixPath(name).parts).with_name(f"{parts[-1]}.json")

    def load(self, name: str, *, format_id: str, version: int) -> LoadResult:
        """Read ``name`` and return its payload without ``format``/``version``, upgraded to ``version``."""
        target = self.path(name)
        self._read_only.discard(name)
        try:
            raw = target.read_bytes()
        except FileNotFoundError:
            return LoadResult(None, "missing")
        except OSError as exc:
            # Unreadable, so it cannot be backed up either: never overwrite what was not read.
            logger.warning("cannot read %s: %s", target, exc)
            self._read_only.add(name)
            return LoadResult(None, "corrupt")
        try:
            file_version, payload = _parse(raw, format_id)
            if file_version > version:
                logger.warning(
                    "%s has version %d, newer than %d: left untouched", target, file_version, version
                )
                self._read_only.add(name)
                return LoadResult(None, "too_new")
            if file_version == version:
                return LoadResult(payload, "ok")
            try:
                upgraded = self.migrations.upgrade(format_id, payload, file_version, version)
            except (MigrationError, KeyError, TypeError, ValueError) as exc:
                raise _BadFile(f"migration failed: {exc}") from exc
            return LoadResult(upgraded, "migrated")
        except _BadFile as exc:
            backup = self._back_up(target)
            logger.warning("%s is corrupt (%s); backed up as %s", target, exc, backup)
            return LoadResult(None, "corrupt", backup)

    def save(self, name: str, payload: Mapping[str, object], *, format_id: str, version: int) -> bool:
        """Atomically write ``payload`` under ``format``/``version``; ``False`` if it was not written."""
        target = self.path(name)
        if name in self._read_only or self._newer_on_disk(target, format_id, version):
            self._read_only.add(name)
            logger.warning("%s is read-only for this version: not saved", target)
            return False
        body = {k: v for k, v in payload.items() if k not in ("format", "version")}
        text = json.dumps({"format": format_id, "version": version, **body}, ensure_ascii=False, indent=2)
        tmp_name: str | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=f".{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_name = tmp.name
                tmp.write(text + "\n")
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, target)
        except OSError as exc:
            logger.warning("cannot save %s: %s", target, exc)
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    logger.debug("cannot remove %s", tmp_name)
            return False
        return True

    def delete(self, name: str) -> None:
        """Remove ``name`` if it exists; a failure is logged, never raised."""
        target = self.path(name)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("cannot delete %s: %s", target, exc)
            return
        self._read_only.discard(name)

    def is_read_only(self, name: str) -> bool:
        """True once a load or save found a file newer than this app understands."""
        return name in self._read_only

    def _newer_on_disk(self, target: Path, format_id: str, version: int) -> bool:
        try:
            file_version, _ = _parse(target.read_bytes(), format_id)
        except (OSError, _BadFile):
            return False
        return file_version > version

    def _back_up(self, target: Path) -> Path | None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        base = f"{target.stem}.corrupt-{stamp}"
        backup = target.with_name(f"{base}.json")
        counter = 1
        while backup.exists():
            backup = target.with_name(f"{base}-{counter}.json")
            counter += 1
        try:
            target.rename(backup)
        except OSError as exc:
            logger.warning("cannot back up %s: %s", target, exc)
            return None
        return backup


def _parse(raw: bytes, format_id: str) -> tuple[int, dict[str, object]]:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise _BadFile(f"not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise _BadFile("not a JSON object")
    if data.get("format") != format_id:
        raise _BadFile(f"format is {data.get('format')!r}, expected {format_id!r}")
    file_version = data.get("version")
    if not isinstance(file_version, int) or isinstance(file_version, bool) or file_version < 1:
        raise _BadFile(f"invalid version {file_version!r}")
    payload = {k: v for k, v in data.items() if k not in ("format", "version")}
    return file_version, payload
