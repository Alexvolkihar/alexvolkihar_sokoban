"""Step-by-step upgrades of persisted payloads, ``vN -> vN+1`` (spec 7.6).

A migration receives and returns the payload without its ``format``/``version`` keys.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

Migration = Callable[[dict[str, object]], dict[str, object]]


class MigrationError(Exception):
    """No registered path from the file's version to the requested one."""


class MigrationRegistry:
    def __init__(self) -> None:
        self._steps: dict[tuple[str, int], Migration] = {}

    def register(self, format_id: str, from_version: int, fn: Migration) -> None:
        """Register the step ``from_version -> from_version + 1`` for ``format_id``."""
        if from_version < 1:
            raise ValueError(f"from_version must be >= 1, got {from_version}")
        key = (format_id, from_version)
        if key in self._steps:
            raise ValueError(f"migration {format_id} {from_version} -> {from_version + 1} already registered")
        self._steps[key] = fn

    def upgrade(
        self, format_id: str, data: dict[str, object], from_version: int, to_version: int
    ) -> dict[str, object]:
        """Apply every step from ``from_version`` to ``to_version``; ``data`` itself is never mutated."""
        if from_version > to_version:
            raise MigrationError(f"{format_id}: cannot downgrade {from_version} -> {to_version}")
        result = copy.deepcopy(data)
        for version in range(from_version, to_version):
            step = self._steps.get((format_id, version))
            if step is None:
                raise MigrationError(f"{format_id}: no migration {version} -> {version + 1}")
            result = step(result)
        return result
