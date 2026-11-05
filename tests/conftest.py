import os

# pytest runs with --import-mode=importlib (pyproject.toml): a helper module next to tests is imported with
# its full path from the repository root, e.g. `from tests.solver.levels import LEVELS`, never `from levels`.

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
