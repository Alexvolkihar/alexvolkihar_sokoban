from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.persistence.session import SavedSession
from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.victory import VictoryScene
from tests.ui.game_helpers import (
    CORRIDOR,
    ENTER,
    ESCAPE,
    LEFT,
    ONE_BOX,
    PACK,
    PAUSE,
    QUIT,
    REDO,
    RESTART,
    RIGHT,
    UNDO,
    UP,
    names,
    start_game,
)

HASH_ONE = ONE_BOX.canonical_hash()


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def session(**kw: object) -> SavedSession:
    fields: dict[str, object] = {
        "pack_id": PACK.id,
        "level_id": "one",
        "level_hash": HASH_ONE,
        "lurd": "r",
        "redo_lurd": "",
        "elapsed_ms": 4_000,
        "assisted": False,
        "saved_at": "2026-11-05T10:00:00Z",
    }
    fields.update(kw)
    return SavedSession(**fields)  # type: ignore[arg-type]


# -- moves --------------------------------------------------------------------------------------------------


def test_undo_redo_actions(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT, RIGHT, UNDO])
    assert scene.state.lurd == "r" and scene.state.redo_lurd == "r"
    app.step([REDO])
    assert scene.state.lurd == "rr"
    app.step([UNDO, UNDO, UNDO])  # one undo too many does nothing
    assert scene.state.moves == 0


def test_restart_needs_double_press(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT, RESTART], 0)
    assert scene.state.moves == 1
    assert scene.message == "Press R again to restart"
    app.step([RESTART], 0)
    assert scene.state.moves == 0 and scene.message is None


def test_restart_second_press_too_late_does_not_restart(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT, RESTART], 0)
    app.step([], 1_600)
    assert scene.message is None  # the prompt went away with the time window
    app.step([RESTART], 0)
    assert scene.state.moves == 1  # this press only armed it again
    app.step([RESTART], 0)
    assert scene.state.moves == 0


def test_restart_prompt_is_translated(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, language="fr")
    app.step([RIGHT, RESTART], 0)
    assert scene.message == "Appuyez encore sur R pour recommencer"


def test_restart_resets_the_timer(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT], 3_000)
    app.step([RESTART, RESTART], 0)
    assert scene.elapsed_ms == 0


# -- timer --------------------------------------------------------------------------------------------------


def test_timer_counts_while_on_top(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([], 500)
    app.step([], 250)
    assert scene.elapsed_ms == 750


def test_timer_pauses_with_pause_overlay(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([], 500)
    app.step([PAUSE], 0)
    assert names(app)[-1] == "pause" and scene.paused
    app.step([], 1_000)
    assert scene.elapsed_ms == 500
    app.step([ESCAPE], 0)  # Esc in the pause menu resumes
    assert app.top is scene and not scene.paused
    app.step([], 100)
    assert scene.elapsed_ms == 600


def test_timer_stops_while_the_window_has_no_focus(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([pygame.event.Event(pygame.WINDOWFOCUSLOST)], 0)
    app.step([], 1_000)
    assert scene.elapsed_ms == 0
    app.step([pygame.event.Event(pygame.WINDOWFOCUSGAINED)], 0)
    app.step([], 200)
    assert scene.elapsed_ms == 200


def test_timer_stops_on_an_activeevent_focus_loss(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([pygame.event.Event(pygame.ACTIVEEVENT, gain=0, state=pygame.APPINPUTFOCUS)], 0)
    app.step([], 1_000)
    assert scene.elapsed_ms == 0
    app.step([pygame.event.Event(pygame.ACTIVEEVENT, gain=1, state=pygame.APPINPUTFOCUS)], 0)
    app.step([], 300)
    assert scene.elapsed_ms == 300


# -- winning ------------------------------------------------------------------------------------------------


def test_win_records_progress_and_shows_victory(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT], 1_000)
    app.step([UP], 0)
    assert names(app) == ["main_menu", "game", "victory"]
    victory = app.top
    assert isinstance(victory, VictoryScene) and victory.is_overlay
    assert victory.record_update.stars_earned == 3  # par is 1 push / 2 moves
    assert victory.run.moves == 2 and victory.run.pushes == 1 and victory.run.lurd == "rU"
    assert victory.run.elapsed_ms == 1_000 and not victory.run.assisted
    ctx = app.context
    assert ctx is not None
    record = ctx.progress.get(HASH_ONE)
    assert record is not None and record.completed and record.stars == 3
    assert ctx.session is None and not ctx.store.path("session").exists()
    reloaded = AppContext.load(tmp_path, bundled=[PACK])
    assert reloaded.progress.get(HASH_ONE) == record  # saved on disk


def test_win_without_par_gives_one_star(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path, "two")
    app.step([RIGHT])
    victory = app.top
    assert isinstance(victory, VictoryScene)
    assert victory.par is None and victory.record_update.stars_earned == 1


def test_assisted_win_earns_no_star(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    scene.assisted = True
    app.step([RIGHT, UP])
    victory = app.top
    assert isinstance(victory, VictoryScene)
    assert victory.run.assisted and victory.record_update.stars_earned == 0


def test_timer_stops_after_the_win(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT, UP], 0)
    scene.update(5_000)  # even if something updates it
    assert scene.elapsed_ms == 0


# -- sessions -----------------------------------------------------------------------------------------------


def test_session_saved_and_resumed(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT], 2_000)
    app.step([PAUSE], 0)
    app.step([UP], 0)  # wraps to the last item: Main menu
    app.step([ENTER], 0)
    assert names(app) == ["main_menu"]
    ctx = app.context
    assert ctx is not None and ctx.session is not None
    assert ctx.session.lurd == "r" and ctx.session.level_hash == HASH_ONE
    assert ctx.session.elapsed_ms == 2_000

    reloaded = AppContext.load(tmp_path, bundled=[PACK])  # it is on disk too
    assert reloaded.session == ctx.session
    _, resumed = start_game(tmp_path, context=reloaded, resume=reloaded.session)
    assert resumed.state.lurd == "r" and resumed.state.player == (4, 2)
    assert resumed.elapsed_ms == 2_000 and not resumed.assisted


def test_resume_keeps_the_redo_stack_and_assisted_flag(tmp_path: Path) -> None:
    _, scene = start_game(tmp_path, resume=session(lurd="r", redo_lurd="U", assisted=True))
    assert scene.state.lurd == "r" and scene.state.redo_lurd == "U" and scene.assisted


def test_resume_with_stale_hash_starts_fresh(tmp_path: Path) -> None:
    stale = session(level_hash="sha256:" + "0" * 64)
    _, scene = start_game(tmp_path, resume=stale)
    assert scene.state.moves == 0 and scene.elapsed_ms == 0


def test_resume_with_illegal_moves_starts_fresh(tmp_path: Path) -> None:
    _, scene = start_game(tmp_path, resume=session(lurd="lll"))  # walks into the wall
    assert scene.state.moves == 0 and scene.elapsed_ms == 0


def test_resume_none_starts_fresh(tmp_path: Path) -> None:
    _, scene = start_game(tmp_path, resume=None)
    assert scene.state.moves == 0


def test_session_saved_on_pause(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.step([RIGHT, PAUSE], 0)
    assert app.context is not None and app.context.session is not None
    assert app.context.session.lurd == "r"


def test_session_saved_on_window_close(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.step([RIGHT], 0)
    app.step([QUIT], 0)
    assert not app.running
    assert AppContext.load(tmp_path, bundled=[PACK]).session is not None


def test_session_saved_every_ten_seconds_of_play(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.step([RIGHT], 0)
    ctx = app.context
    assert ctx is not None and ctx.session is None
    app.step([], 9_000)
    assert ctx.session is None
    app.step([], 1_000)
    assert ctx.session is not None and ctx.session.elapsed_ms == 10_000


def test_save_session_method(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT], 0)
    scene.save_session()
    assert app.context is not None and app.context.session is not None
    assert app.context.session.lurd == "r"


def test_leaving_without_moves_deletes_this_levels_session(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, resume=session(lurd="r"))
    app.step([UNDO], 0)
    assert scene.state.moves == 0 and app.context is not None
    app.step([QUIT], 0)
    assert app.context.session is None
    assert AppContext.load(tmp_path, bundled=[PACK]).session is None


def test_visiting_another_level_keeps_the_saved_session(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path, "two")
    ctx = app.context
    assert ctx is not None
    ctx.save_session(session())  # a game of level one, saved earlier
    app.step([QUIT], 0)  # no move on level two: nothing to save, and level one's game must stay
    assert ctx.session == session()
    assert AppContext.load(tmp_path, bundled=[PACK]).session == session()


def test_last_played_updated_on_enter(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path, "two")
    ctx = app.context
    assert ctx is not None and ctx.progress.last_played is not None
    assert ctx.progress.last_played.level_id == "two"
    assert ctx.progress.last_played.level_hash == CORRIDOR.canonical_hash()
    reloaded = AppContext.load(tmp_path, bundled=[PACK])
    assert reloaded.progress.last_played == ctx.progress.last_played


def test_game_without_context_still_plays() -> None:
    app = App(Settings(animation="off"), headless=True)
    app.push("main_menu")
    scene = app.push("game", pack=PACK, level_id="one")
    assert isinstance(scene, GameScene)
    app.step([RIGHT, UP, PAUSE, QUIT])
    assert not app.running


# -- animation ----------------------------------------------------------------------------------------------


def test_animation_off_applies_every_move_at_once(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, animation="off")
    app.step([RIGHT, LEFT, RIGHT, LEFT], 0)
    assert scene.state.lurd == "rlrl" and not scene.animating


@pytest.mark.parametrize(("animation", "duration"), [("normal", 120), ("fast", 60)])
def test_animation_queues_at_most_two_moves(tmp_path: Path, animation: str, duration: int) -> None:
    app, scene = start_game(tmp_path, animation=animation)
    app.step([RIGHT, LEFT, RIGHT, LEFT], 0)
    assert scene.state.lurd == "r" and scene.animating  # two queued, the fourth dropped
    app.step([], duration)
    assert scene.state.lurd == "rl"
    app.step([], duration)
    app.step([], duration)
    assert scene.state.lurd == "rlr" and not scene.animating


def test_animated_win_shows_victory_after_the_push(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path, animation="normal")
    app.step([RIGHT], 200)
    app.step([UP], 0)
    assert names(app)[-1] == "game"
    app.step([], 200)
    assert names(app)[-1] == "victory"


def test_undo_during_animation_finishes_it_first(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, animation="normal")
    app.step([RIGHT, LEFT, UNDO], 0)  # the queued "l" is dropped by the undo
    assert scene.state.lurd == "" and not scene.animating


def test_animation_draws_between_cells(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, animation="normal")
    app.step([RIGHT], 60)  # half way: drawing must not raise
    assert scene.animating


# -- layout -------------------------------------------------------------------------------------------------


def test_resize_mid_game_relayouts(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RIGHT])
    assert scene.board_layout is not None
    before = scene.board_layout.tile
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=700, h=500, size=(700, 500))])
    assert scene.board_layout is not None and scene.board_layout.tile != before
    assert app.screen.get_size() == (700, 500)
    assert scene.state.lurd == "r"


def test_escape_opens_the_pause_menu(tmp_path: Path) -> None:
    app, _ = start_game(tmp_path)
    app.step([ESCAPE])
    assert names(app) == ["main_menu", "game", "pause"]


def test_restart_action_does_nothing_without_moves(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path)
    app.step([RESTART], 0)
    assert scene.message is None and scene.state.moves == 0


def test_enter_during_an_animation_keeps_the_queued_moves(tmp_path: Path) -> None:
    app, scene = start_game(tmp_path, animation="normal")
    app.step([RIGHT, LEFT, ENTER], 0)
    app.step([], 120)
    assert scene.state.lurd == "rl"


def test_failed_save_warns_and_play_goes_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene = start_game(tmp_path)
    ctx = app.context
    assert ctx is not None
    monkeypatch.setattr(ctx.store, "save", lambda *a, **kw: False)
    app.step([RIGHT, PAUSE, ESCAPE], 0)
    assert app.top is scene
    assert scene.message == "Could not save the game in progress."
    app.step([UP], 0)
    assert names(app)[-1] == "victory"  # the win is shown even though progress cannot be saved
