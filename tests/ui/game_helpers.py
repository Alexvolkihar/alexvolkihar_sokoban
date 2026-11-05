"""Shared fixtures of the game, pause and victory scene tests (import as ``tests.ui.game_helpers``)."""

from __future__ import annotations

from pathlib import Path

import pygame

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.scenes.game import GameScene

# Solved by "rU": walk right, push the box up onto the goal.
ONE_BOX = Level.from_rows(
    [
        "#####",
        "#   #",
        "# . #",
        "# $ #",
        "#@  #",
        "#####",
    ]
)
# Solved by "R".
CORRIDOR = Level.from_rows(["#####", "#@$.#", "#####"])

PAR_ONE = Par(pushes=1, moves=2, lurd="rU", solver="push-astar/1")
PACK = Pack(
    id="test",
    title="Test pack",
    levels=(LevelEntry("one", ONE_BOX, par=PAR_ONE), LevelEntry("two", CORRIDOR)),
)


def key(k: int, scancode: int = 0, mod: int = pygame.KMOD_NONE) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=mod, unicode="")


LEFT = key(pygame.K_LEFT, 80)
RIGHT = key(pygame.K_RIGHT, 79)
UP = key(pygame.K_UP, 82)
DOWN = key(pygame.K_DOWN, 81)
UNDO = key(pygame.K_u, 24)
REDO = key(pygame.K_y, 28)
RESTART = key(pygame.K_r, 21)
PAUSE = key(pygame.K_p, 19)
ESCAPE = key(pygame.K_ESCAPE, 41)
ENTER = key(pygame.K_RETURN, 40)
QUIT = pygame.event.Event(pygame.QUIT)


def make_context(tmp_path: Path, *, animation: str = "off", language: str = "en") -> AppContext:
    ctx = AppContext.load(tmp_path, bundled=[PACK])
    ctx.settings.animation = animation  # type: ignore[assignment]
    ctx.settings.language = language  # type: ignore[assignment]  # App applies it
    return ctx


def start_game(
    tmp_path: Path,
    level_id: str = "one",
    *,
    animation: str = "off",
    language: str = "en",
    context: AppContext | None = None,
    **params: object,
) -> tuple[App, GameScene]:
    """An app on [main_menu, game]; animations off and English unless asked."""
    ctx = context if context is not None else make_context(tmp_path, animation=animation, language=language)
    app = App(ctx.settings, context=ctx, headless=True)
    app.push("main_menu")
    scene = app.push("game", pack=ctx.pack(PACK.id), level_id=level_id, **params)
    assert isinstance(scene, GameScene)
    return app, scene


def names(app: App) -> list[str]:
    return [s.name for s in app.stack]
