"""The in-progress game, saved as LURD history plus redo stack (spec 7.6)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass

SESSION_FORMAT = "alexvolkihar-sokoban/session"
SESSION_VERSION = 1

HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
LURD_PATTERN = re.compile(r"[lurdLURD]*")
TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@dataclass(frozen=True)
class SavedSession:
    pack_id: str
    level_id: str
    level_hash: str
    lurd: str
    redo_lurd: str
    elapsed_ms: int
    assisted: bool
    saved_at: str

    def to_dict(self) -> dict[str, object]:
        """JSON-ready fields, without ``format``/``version`` (the store adds them)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SavedSession:
        """Strict reader: raises ``ValueError`` naming the first missing or invalid field.

        The moves are only checked for LURD characters here; replaying them on the level (and checking
        ``level_hash``) is the caller's job.
        """
        return cls(
            pack_id=_text(data, "pack_id"),
            level_id=_text(data, "level_id"),
            level_hash=_matching(data, "level_hash", HASH_PATTERN),
            lurd=_matching(data, "lurd", LURD_PATTERN),
            redo_lurd=_matching(data, "redo_lurd", LURD_PATTERN),
            elapsed_ms=_duration(data, "elapsed_ms"),
            assisted=_flag(data, "assisted"),
            saved_at=_matching(data, "saved_at", TIMESTAMP_PATTERN),
        )


def _get(data: Mapping[str, object], key: str) -> object:
    if key not in data:
        raise ValueError(f"session: missing {key}")
    return data[key]


def _text(data: Mapping[str, object], key: str) -> str:
    value = _get(data, key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"session: {key} must be a non-empty string")
    return value


def _matching(data: Mapping[str, object], key: str, pattern: re.Pattern[str]) -> str:
    value = _get(data, key)
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"session: invalid {key}")
    return value


def _duration(data: Mapping[str, object], key: str) -> int:
    value = _get(data, key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"session: {key} must be a non-negative integer")
    return value


def _flag(data: Mapping[str, object], key: str) -> bool:
    value = _get(data, key)
    if not isinstance(value, bool):
        raise ValueError(f"session: {key} must be a boolean")
    return value
