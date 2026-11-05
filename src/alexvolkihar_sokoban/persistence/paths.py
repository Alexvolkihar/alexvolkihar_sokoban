"""Location of the user data directory (spec 7.6)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "alexvolkihar-sokoban"
ENV_HOME = "ALEXVOLKIHAR_SOKOBAN_HOME"

logger = logging.getLogger(__name__)


def data_dir(override: Path | None = None) -> Path:
    """The data directory: ``override`` (``--data-dir``) > ``$ALEXVOLKIHAR_SOKOBAN_HOME`` > platformdirs.

    The directory is created when possible. A directory that cannot be created is logged, not raised:
    the game still runs and every later save simply reports failure.
    """
    if override is not None:
        path = Path(override).expanduser()
    elif env := os.environ.get(ENV_HOME):
        path = Path(env).expanduser()
    else:
        path = Path(user_data_dir(APP_NAME, appauthor=False))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("cannot create the data directory %s: %s", path, exc)
    return path
