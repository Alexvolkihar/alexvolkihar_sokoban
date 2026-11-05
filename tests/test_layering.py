"""Only ``alexvolkihar_sokoban.ui`` (and ``commands.play``) may import pygame (spec 6)."""

import subprocess
import sys

NON_UI = ["core", "formats", "solver", "scoring", "persistence", "benchmark", "generator"]
NON_UI_COMMANDS = ["solve", "convert", "annotate", "bench", "generate"]

# Runs in a fresh interpreter so no module copy leaks into the test session's sys.modules.
SCRIPT = """
import importlib, pkgutil, sys
sys.modules["pygame"] = None  # any `import pygame` now raises ImportError
names = []
for sub in {packages!r}:
    pkg = importlib.import_module("alexvolkihar_sokoban." + sub)
    names.append(pkg.__name__)
    for info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        importlib.import_module(info.name)
        names.append(info.name)
for cmd in {commands!r}:
    names.append(importlib.import_module("alexvolkihar_sokoban.commands." + cmd).__name__)
print(len(names))
"""


def test_non_ui_packages_import_without_pygame() -> None:
    code = SCRIPT.format(packages=NON_UI, commands=NON_UI_COMMANDS)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.strip()) >= len(NON_UI) + len(NON_UI_COMMANDS)
