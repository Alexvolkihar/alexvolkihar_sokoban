"""Scenes, loaded by name: ``alexvolkihar_sokoban.ui.scenes.<name>`` defines ``SCENE = <Scene subclass>``.

Names used by the app: main_menu, level_select, game, pause, victory, settings, themes, keybindings,
benchmark, generate, credits, replay. A name whose module does not exist yet gives ``PlaceholderScene``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alexvolkihar_sokoban.ui.scene import Scene


def load_scene_class(name: str) -> type[Scene]:
    """The ``SCENE`` class of module ``<name>``; ``PlaceholderScene`` when there is no such module.

    Raises ``ValueError`` for a name that is not a plain identifier. An import error raised *inside* an
    existing scene module is not hidden.
    """
    if not name.isidentifier():
        raise ValueError(f"invalid scene name: {name!r}")
    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise
        from alexvolkihar_sokoban.ui.scenes.placeholder import PlaceholderScene

        return PlaceholderScene
    scene: type[Scene] = module.SCENE
    return scene
