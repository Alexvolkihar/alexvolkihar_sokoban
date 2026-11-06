from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.scoring.records import LevelRecord, RecordUpdate, RunResult
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.victory import VictoryScene
from tests.ui.game_helpers import ENTER, ESCAPE, PACK, PAR_ONE, RIGHT, UP, names, start_game


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def win_level_one(tmp_path: Path, language: str = "en") -> tuple[App, VictoryScene]:
    app, _ = start_game(tmp_path, language=language)
    app.step([RIGHT], 61_000)
    app.step([UP], 0)
    victory = app.top
    assert isinstance(victory, VictoryScene)
    return app, victory


def win_level_two(tmp_path: Path, language: str = "en") -> tuple[App, VictoryScene]:
    app, _ = start_game(tmp_path, "two", language=language)
    app.step([RIGHT], 0)
    victory = app.top
    assert isinstance(victory, VictoryScene)
    return app, victory


def choose(app: App, victory: VictoryScene, index: int) -> None:
    victory.menu.selected = index
    app.step([ENTER], 0)


def test_items_with_a_next_level(tmp_path: Path) -> None:
    _, victory = win_level_one(tmp_path)
    assert [item.text for item in victory.menu.items] == ["Next level", "Replay", "Level select"]
    assert victory.menu.selected == 0


def test_no_next_level_on_the_last_level(tmp_path: Path) -> None:
    _, victory = win_level_two(tmp_path, "fr")
    assert [item.text for item in victory.menu.items] == ["Rejouer", "Choix du niveau"]


def test_victory_next_level(tmp_path: Path) -> None:
    app, victory = win_level_one(tmp_path)
    choose(app, victory, 0)
    assert names(app) == ["main_menu", "game"]
    game = app.top
    assert isinstance(game, GameScene)
    assert game.entry.id == "two" and game.state.moves == 0 and game.elapsed_ms == 0
    assert app.context is not None and app.context.progress.last_played is not None
    assert app.context.progress.last_played.level_id == "two"


def test_replay_starts_the_same_level_again(tmp_path: Path) -> None:
    app, victory = win_level_one(tmp_path)
    choose(app, victory, 1)
    assert names(app) == ["main_menu", "game"]
    game = app.top
    assert isinstance(game, GameScene)
    assert game.entry.id == "one" and game.state.moves == 0


def test_level_select_item_and_back(tmp_path: Path) -> None:
    app, victory = win_level_one(tmp_path)
    choose(app, victory, 2)
    assert names(app) == ["main_menu", "level_select"]
    app2, _ = win_level_two(tmp_path / "other")
    app2.step([ESCAPE], 0)
    assert names(app2) == ["main_menu", "level_select"]


def test_summary_lines(tmp_path: Path) -> None:
    _, victory = win_level_one(tmp_path)
    assert victory.summary_lines() == ["Moves 2", "Pushes 1", "Time 1:01"]
    set_language("fr")
    assert victory.summary_lines() == ["Pas 2", "Poussées 1", "Temps 1:01"]


def test_first_win_badges(tmp_path: Path) -> None:
    _, victory = win_level_one(tmp_path)
    assert victory.badges() == ["New best: moves", "New best: pushes", "New best: time"]
    set_language("fr")
    assert victory.badges() == ["Nouveau record : pas", "Nouveau record : poussées", "Nouveau record : temps"]


def update(**kw: object) -> RecordUpdate:
    fields: dict[str, object] = {
        "record": LevelRecord(PACK.id, "one", completed=True, stars=3, plays=2),
        "stars_earned": 3,
        "new_best_moves": False,
        "new_best_pushes": False,
        "new_best_time": False,
        "beats_par_moves": False,
    }
    fields.update(kw)
    return RecordUpdate(**fields)  # type: ignore[arg-type]


def run(*, assisted: bool = False) -> RunResult:
    return RunResult(
        moves=2, pushes=1, elapsed_ms=1_000, lurd="rU", assisted=assisted, finished_at="2026-11-05T10:00:00Z"
    )


def push_victory(
    tmp_path: Path, upd: RecordUpdate, result: RunResult, par: Par | None, language: str = "en"
) -> VictoryScene:
    app, _ = start_game(tmp_path, language=language)
    scene = app.push("victory", pack=PACK, level_id="one", update=upd, run=result, par=par)
    assert isinstance(scene, VictoryScene)
    return scene


def test_better_than_par_badge(tmp_path: Path) -> None:
    scene = push_victory(tmp_path, update(beats_par_moves=True), run(), PAR_ONE, "fr")
    assert scene.badges() == ["Mieux que le par !"]


def test_no_badge_on_a_plain_replay(tmp_path: Path) -> None:
    scene = push_victory(tmp_path, update(), run(), PAR_ONE)
    assert scene.badges() == []


def test_assisted_badge(tmp_path: Path) -> None:
    scene = push_victory(tmp_path, update(stars_earned=0), run(assisted=True), PAR_ONE)
    assert scene.badges() == ["Assisted: no stars or records"]


def test_victory_needs_its_parameters(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    with pytest.raises(TypeError):
        app.push("victory", pack=PACK, level_id="one")


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_victory_draws_at_any_size(tmp_path: Path, size: tuple[int, int], language: str) -> None:
    app, victory = win_level_one(tmp_path, language)
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size)])
    assert len(victory.menu.item_rects) == 3
    assert all(app.screen.get_rect().contains(r) for r in victory.menu.item_rects)


def test_mouse_click_on_replay(tmp_path: Path) -> None:
    app, victory = win_level_one(tmp_path)
    app.step([], 0)
    rect = victory.menu.item_rects[1]
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)], 0)
    assert names(app) == ["main_menu", "game"]
