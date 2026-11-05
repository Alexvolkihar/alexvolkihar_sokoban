import importlib
import pkgutil
import sys

import pytest

NON_UI = ["core", "formats", "solver", "scoring", "persistence", "benchmark", "generator"]


def test_non_ui_packages_import_without_pygame(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "alexvolkihar_sokoban" or name.startswith("alexvolkihar_sokoban."):
            monkeypatch.delitem(sys.modules, name)
    for name in list(sys.modules):
        if name == "pygame" or name.startswith("pygame."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "pygame", None)  # any `import pygame` now raises ImportError

    imported: list[str] = []
    for sub in NON_UI:
        pkg = importlib.import_module(f"alexvolkihar_sokoban.{sub}")
        imported.append(pkg.__name__)
        for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg.__name__}."):
            importlib.import_module(info.name)
            imported.append(info.name)
    assert len(imported) >= len(NON_UI)
