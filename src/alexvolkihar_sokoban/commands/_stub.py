from __future__ import annotations

import sys


def not_implemented(name: str) -> int:
    print(f"alexvolkihar-sokoban {name}: not implemented yet", file=sys.stderr)
    return 2
