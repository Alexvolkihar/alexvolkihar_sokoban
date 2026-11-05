import pygame

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.scenes.game import GameScene

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


def big_level(n: int) -> Level:
    rows = ["#" * n] + ["#" + " " * (n - 2) + "#" for _ in range(n - 2)] + ["#" * n]
    rows[1] = "#@$ ." + " " * (n - 6) + "#"
    return Level.from_rows(rows)


PACK = Pack(
    id="test",
    title="Test pack",
    levels=(LevelEntry("one", ONE_BOX), LevelEntry("big", big_level(60))),
)


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


LEFT = key(pygame.K_LEFT, 80)
RIGHT = key(pygame.K_RIGHT, 79)
UP = key(pygame.K_UP, 82)
DOWN = key(pygame.K_DOWN, 81)
UNDO = key(pygame.K_u, 24)
REDO = key(pygame.K_y, 28)
RESTART = key(pygame.K_r, 21)
ESCAPE = key(pygame.K_ESCAPE, 41)


def game_app(level_id: str = "one", **settings: object) -> tuple[App, GameScene]:
    app = App(Settings(**settings), headless=True)  # type: ignore[arg-type]
    app.push("main_menu")
    scene = app.push("game", pack=PACK, level_id=level_id)
    assert isinstance(scene, GameScene)
    return app, scene


def test_game_basic_win_pops() -> None:
    app, scene = game_app()
    app.step([RIGHT])  # "r"
    assert scene.state.lurd == "r" and app.top is scene
    app.step([UP])  # "U": the box lands on the goal
    assert app.top is not None and app.top.name == "main_menu" and len(app.stack) == 1


def test_wasd_moves_the_player() -> None:
    app, scene = game_app()
    app.step([key(pygame.K_d, 7)])
    assert scene.state.lurd == "r"


def test_blocked_moves_change_nothing() -> None:
    app, scene = game_app()
    app.step([LEFT, DOWN])
    assert scene.state.moves == 0 and scene.state.player == ONE_BOX.player


def test_undo_redo_restart() -> None:
    app, scene = game_app()
    app.step([RIGHT, RIGHT, UNDO])
    assert scene.state.lurd == "r"
    app.step([REDO])
    assert scene.state.lurd == "rr"
    app.step([RESTART])
    assert scene.state.moves == 0


def test_escape_returns_to_the_previous_scene() -> None:
    app, _ = game_app()
    app.step([ESCAPE])
    assert app.top is not None and app.top.name == "main_menu"


def test_huge_level_draws_in_the_minimum_window_and_after_resizes() -> None:
    app, scene = game_app("big", window=(640, 480))
    app.step([RIGHT])
    for size in [(640, 480), (1000, 700), (10, 10)]:
        app.step([pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size)])
    assert scene.board_layout is not None and scene.board_layout.tile >= 4
    assert scene.state.boxes == frozenset({(1, 3)})
