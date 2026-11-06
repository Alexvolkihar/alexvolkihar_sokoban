"""Level file formats: XSB/SOK, the legacy format of Sokoban-LAMA and JSON packs (spec 7.3, 9.2)."""

from __future__ import annotations

from pathlib import Path


class FormatError(ValueError):
    """A file that cannot be read as a level pack.

    ``path`` and ``line`` (1-based) locate the problem when known; ``reason`` is the bare message.
    """

    def __init__(self, reason: str, *, path: Path | None = None, line: int | None = None) -> None:
        self.reason = reason
        self.path = path
        self.line = line
        where = "" if path is None else str(path)
        if line is not None:
            where = f"{where}:{line}" if where else f"line {line}"
        super().__init__(f"{where}: {reason}" if where else reason)
