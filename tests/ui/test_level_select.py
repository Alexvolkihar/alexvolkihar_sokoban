from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.persistence.settings import Settings
from alexvolkihar_sokoban.scoring.records import LastPlayed, RunResult
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.game import pack_title
from alexvolkihar_sokoban.ui.scenes.level_select import LevelSelectScene


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode="")


UP = key(pygame.K_UP, 82)
DOWN = key(pygame.K_DOWN, 81)
LEFT = key(pygame.K_LEFT, 80)
RIGHT = key(pygame.K_RIGHT, 79)
ENTER = key(pygame.K_RETURN, 40)
ESCAPE = key(pygame.K_ESCAPE, 41)
TAB = key(pygame.K_TAB, 43)
F5 = key(pygame.K_F5, 62)


def level(n: int) -> Level:
    """A distinct 1-box level per ``n`` (corridor length), so every level has its own hash."""
    inner = "@$" + " " * n + "."
    return Level.from_rows(["#" * (len(inner) + 2), f"#{inner}#", "#" * (len(inner) + 2)])


def make_pack(pack_id: str, n: int, *, hidden: bool = False, start: int = 0) -> Pack:
    entries = tuple(
        LevelEntry(str(i + 1), level(start + i), par=Par(1 + start + i, 1 + start + i, "", "test"))
        for i in range(n)
    )
    return Pack(pack_id, f"Pack {pack_id}", entries, hidden=hidden)


ALPHA = make_pack("alpha", 13)
BETA = make_pack("beta", 2, start=50)
HIDDEN = make_pack("secret", 1, hidden=True, start=80)


def run(moves: int, pushes: int) -> RunResult:
    return RunResult(moves, pushes, 1000, "r" * moves, False, "2026-11-05T10:00:00Z")


def open_select(
    tmp_path: Path, *, window: tuple[int, int] = (1024, 768), language: str = "en", **params: object
) -> tuple[App, LevelSelectScene, AppContext]:
    ctx = AppContext.load(tmp_path, bundled=[ALPHA, BETA, HIDDEN])
    ctx.settings.window = window
    ctx.settings.language = language  # type: ignore[assignment]
    app = App(ctx.settings, context=ctx, headless=True)
    app.push("main_menu")
    scene = app.push("level_select", **params)
    assert isinstance(scene, LevelSelectScene)
    app.step([])  # one frame: layout and draw
    return app, scene, ctx


def spy_pushes(app: App, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = []
    real_push = app.push

    def push(name: str, **params: object) -> Scene:
        calls.append((name, params))
        return real_push(name, **params)

    monkeypatch.setattr(app, "push", push)
    return calls


# -- packs -----------------------------------------------------------------------------------------------


def test_lists_visible_packs_only(tmp_path: Path) -> None:
    _, scene, _ = open_select(tmp_path)
    assert [p.id for p in scene.packs] == ["alpha", "beta", "generated", "custom"]


def test_pack_titles_translated_for_generated_and_custom(tmp_path: Path) -> None:
    _, scene, ctx = open_select(tmp_path)
    titles = [scene.pack_title(p) for p in scene.packs]
    assert titles == ["Pack alpha", "Pack beta", "Generated", "Custom"]
    set_language("fr")
    assert [scene.pack_title(p) for p in scene.packs][2:] == ["Niveaux générés", "Mes niveaux"]


def test_bundled_first_steps_pack_title_is_translated(tmp_path: Path) -> None:
    ctx = AppContext.load(tmp_path)
    first = ctx.packs[0]
    assert first.id == "first-steps"
    set_language("en")
    assert pack_title(first) == "First steps"
    set_language("fr")
    assert pack_title(first) == "Premiers pas"


def test_starts_on_first_pack_or_requested_pack(tmp_path: Path) -> None:
    _, scene, _ = open_select(tmp_path)
    assert scene.pack.id == "alpha" and scene.selected == 0 and scene.focus == "grid"
    _, scene, _ = open_select(tmp_path / "b", pack_id="beta")
    assert scene.pack.id == "beta"
    _, scene, _ = open_select(tmp_path / "c", pack_id="nope")
    assert scene.pack.id == "alpha"


def test_starts_on_last_played_level(tmp_path: Path) -> None:
    ctx = AppContext.load(tmp_path, bundled=[ALPHA, BETA])
    lv = BETA.entry("2").level
    ctx.progress.set_last_played(LastPlayed("beta", "2", lv.canonical_hash()))
    app = App(ctx.settings, context=ctx, headless=True)
    scene = app.push("level_select")
    assert isinstance(scene, LevelSelectScene)
    assert scene.pack.id == "beta" and scene.selected == 1


def test_completed_count_and_stars_from_progress(tmp_path: Path) -> None:
    app, scene, ctx = open_select(tmp_path, language="en")
    e1, e2 = ALPHA.levels[0], ALPHA.levels[1]
    ctx.progress.record_run(e1.level.canonical_hash(), "alpha", "1", run(1, 1), e1.par)  # at par: 3 stars
    ctx.progress.record_run(e2.level.canonical_hash(), "alpha", "2", run(9, 9), e2.par)  # far: 1 star
    assert scene.completed(ALPHA) == (2, 13)
    assert scene.completed(BETA) == (0, 2)
    assert scene.pack_status(ALPHA) == "completed 2 / 13"
    rec = scene.record(e1)
    assert rec is not None and rec.completed and rec.stars == 3
    rec = scene.record(e2)
    assert rec is not None and rec.stars == 1
    assert scene.record(ALPHA.levels[2]) is None
    assert scene.best_text(e2) == "best 9 moves · 9 pushes"
    assert scene.best_text(ALPHA.levels[2]) == ""
    set_language("fr")
    assert scene.pack_status(ALPHA) == "terminés 2 / 13"
    assert scene.best_text(e2) == "record 9 pas · 9 poussées"
    app.step([])  # draws checks and stars without error


# -- navigation ------------------------------------------------------------------------------------------


def test_grid_navigation_and_confirm_opens_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene, _ = open_select(tmp_path)
    cols = scene.columns
    assert 2 <= cols < 13
    app.step([RIGHT])
    assert scene.selected == 1
    app.step([DOWN])
    assert scene.selected == 1 + cols
    app.step([UP, LEFT])
    assert scene.selected == 0 and scene.focus == "grid"
    app.step([UP])  # first row: stays
    assert scene.selected == 0
    for _ in range(20):
        app.step([DOWN])
    assert scene.selected == 12  # last row may be short: lands on the last level
    for _ in range(5):
        app.step([RIGHT])
    assert scene.selected == 12
    calls = spy_pushes(app, monkeypatch)
    app.step([ENTER])
    assert calls == [("game", {"pack": ALPHA, "level_id": "13"})]
    assert app.top is not None and app.top.name == "game"


def test_left_at_column_zero_and_tab_move_focus_to_packs(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path)
    app.step([LEFT])
    assert scene.focus == "packs"
    app.step([TAB])
    assert scene.focus == "grid"
    app.step([TAB])
    assert scene.focus == "packs"
    app.step([RIGHT])
    assert scene.focus == "grid"


def test_pack_list_switches_pack(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path)
    app.step([RIGHT, RIGHT, LEFT, LEFT, LEFT])  # back to column 0, then to the pack list
    assert scene.focus == "packs"
    app.step([DOWN])
    assert scene.pack.id == "beta" and scene.selected == 0
    app.step([DOWN, DOWN, DOWN])
    assert scene.pack.id == "custom"  # no wrap-around
    app.step([UP])
    assert scene.pack.id == "generated"
    app.step([ENTER])  # empty pack: focus stays on the list
    assert scene.focus == "packs"
    app.step([UP, ENTER])
    assert scene.pack.id == "beta" and scene.focus == "grid"


def test_back_returns_to_previous_scene(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path)
    app.step([ESCAPE])  # Escape is pause + back: back only
    assert app.top is not None and app.top.name == "main_menu"
    app, scene, _ = open_select(tmp_path / "b")
    app.step([LEFT, ESCAPE])  # from the pack list too
    assert app.top is not None and app.top.name == "main_menu"


def test_selection_scrolls_into_view_in_small_window(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path, window=(640, 480))
    for _ in range(13):
        app.step([RIGHT])
    assert scene.selected == 12
    rect = scene.tile_rect(12)
    assert rect is not None and scene.grid_rect.contains(rect)
    assert scene.tile_rect(0) is None  # scrolled out of view


def test_resize_relayouts(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path)
    wide = scene.columns
    app.step([pygame.event.Event(pygame.VIDEORESIZE, w=640, h=480, size=(640, 480))])
    assert scene.columns < wide


# -- mouse -----------------------------------------------------------------------------------------------


def test_click_on_tile_opens_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, scene, _ = open_select(tmp_path)
    rect = scene.tile_rect(2)
    assert rect is not None
    calls = spy_pushes(app, monkeypatch)
    app.step([pygame.event.Event(pygame.MOUSEMOTION, pos=rect.center, rel=(0, 0), buttons=(0, 0, 0))])
    assert scene.selected == 2 and calls == []
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)])
    assert calls == [("game", {"pack": ALPHA, "level_id": "3"})]


def test_click_on_pack_selects_it(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path)
    rect = scene.pack_rect(1)
    assert rect is not None
    app.step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)])
    assert scene.pack.id == "beta"


def test_mouse_wheel_scrolls_grid(tmp_path: Path) -> None:
    app, scene, _ = open_select(tmp_path, window=(640, 480))
    assert scene.tile_rect(0) is not None
    app.step([pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False)])
    assert scene.tile_rect(0) is None
    app.step([pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=5, flipped=False)])
    assert scene.tile_rect(0) is not None


# -- empty packs -----------------------------------------------------------------------------------------


def test_empty_custom_pack_shows_hint(tmp_path: Path) -> None:
    app, scene, ctx = open_select(tmp_path, pack_id="custom")
    assert scene.focus == "packs"
    hint = scene.empty_hint()
    assert str(ctx.levels_dir) in hint and ".xsb" in hint
    app.step([ENTER])
    assert app.top is scene  # nothing to open
    _, scene, _ = open_select(tmp_path / "g", pack_id="generated")
    assert "Random level" in scene.empty_hint()


def test_f5_reloads_custom_levels(tmp_path: Path) -> None:
    app, scene, ctx = open_select(tmp_path, pack_id="custom")
    (ctx.levels_dir / "mine.xsb").write_text("#####\n#@$.#\n#####\n", encoding="utf-8")
    app.step([F5])
    assert scene.pack.id == "custom" and [e.id for e in scene.pack.levels] == ["mine/1"]


def test_resume_follows_packs_and_last_played(tmp_path: Path) -> None:
    app, scene, ctx = open_select(tmp_path, pack_id="generated")
    app.push("placeholder")
    new = ctx.add_generated_level(LevelEntry("g-1", level(90)))
    ctx.progress.set_last_played(LastPlayed("generated", "g-1", new.levels[0].level.canonical_hash()))
    app.pop()
    assert scene.pack.id == "generated" and scene.selected == 0 and scene.focus == "grid"
    assert [e.id for e in scene.pack.levels] == ["g-1"]


def test_without_context_shows_nothing_and_goes_back() -> None:
    app = App(Settings(), headless=True)
    app.push("main_menu")
    scene = app.push("level_select")
    assert isinstance(scene, LevelSelectScene)
    app.step([DOWN, RIGHT, ENTER, TAB])
    assert scene.packs == []
    app.step([ESCAPE])
    assert app.top is not None and app.top.name == "main_menu"


def test_draws_with_every_theme_and_language(tmp_path: Path) -> None:
    app, scene, ctx = open_select(tmp_path, window=(640, 480), language="fr")
    e1 = ALPHA.levels[0]
    ctx.progress.record_run(e1.level.canonical_hash(), "alpha", "1", run(1, 1), e1.par)
    for theme_id in ("kenney", "classic", "neon", "contrast"):
        app.set_theme(theme_id)
        app.step([])
        app.step([LEFT])
        app.step([RIGHT])


def test_small_window_still_shows_two_rows(tmp_path: Path) -> None:
    _, scene, _ = open_select(tmp_path, window=(640, 480))
    second_row = scene.tile_rect(scene.columns)
    assert second_row is not None and scene.grid_rect.contains(second_row)
