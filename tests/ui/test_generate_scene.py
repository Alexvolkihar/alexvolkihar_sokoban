import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Par
from alexvolkihar_sokoban.generator.api import GeneratedLevel, GenerationCancelled, GenerationFailed
from alexvolkihar_sokoban.generator.presets import PRESETS, Preset
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import GENERATED_ID, AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language
from alexvolkihar_sokoban.ui.scenes import generate as generate_module
from alexvolkihar_sokoban.ui.scenes.game import GameScene
from alexvolkihar_sokoban.ui.scenes.generate import (
    BACK,
    GENERATE,
    PLAY,
    PRESET,
    REGENERATE,
    SAVE,
    SEED,
    GenerateScene,
)

LEVEL = Level.from_rows(["#######", "#@ $ .#", "#######"])


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def key(k: int, scancode: int = 0, unicode: str = "") -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=pygame.KMOD_NONE, unicode=unicode)


UP = key(pygame.K_UP, 82)
DOWN = key(pygame.K_DOWN, 81)
LEFT = key(pygame.K_LEFT, 80)
RIGHT = key(pygame.K_RIGHT, 79)
ENTER = key(pygame.K_RETURN, 40)
ESCAPE = key(pygame.K_ESCAPE, 41)
BACKSPACE = key(pygame.K_BACKSPACE, 42)


def digit(ch: str) -> pygame.event.Event:
    return key(pygame.key.key_code(ch), 0, ch)


class FakeGenerator:
    """Stands in for ``generator.api.generate``: records its calls, returns a small level."""

    def __init__(self, behaviour: Callable[..., GeneratedLevel] | None = None) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.behaviour = behaviour

    def __call__(
        self, preset: Preset | str, seed: int | None = None, *, should_stop: Callable[[], bool] | None = None
    ) -> GeneratedLevel:
        preset_id = preset.id if isinstance(preset, Preset) else preset
        self.calls.append((preset_id, seed))
        if self.behaviour is not None:
            return self.behaviour(preset_id, seed, should_stop)
        used = 7 if seed is None else seed
        par = Par(pushes=2, moves=4, lurd="rRR", solver="push-astar/1")
        return GeneratedLevel(LevelEntry(f"{preset_id}-{used}", LEVEL, par=par, seed=used), attempts=1)


def make_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake: FakeGenerator | None = None, language: str = "en"
) -> tuple[App, AppContext, GenerateScene, FakeGenerator]:
    fake = fake if fake is not None else FakeGenerator()
    monkeypatch.setattr(generate_module, "generate_level", fake)
    ctx = AppContext.load(tmp_path, bundled=[])
    ctx.settings.language = language  # type: ignore[assignment]  # App applies it
    app = App(ctx.settings, context=ctx, headless=True)
    app.push("main_menu")
    scene = app.push("generate")
    assert isinstance(scene, GenerateScene)
    return app, ctx, scene, fake


def select(app: App, scene: GenerateScene, index: int) -> None:
    for _ in range(len(scene.menu.items)):
        if scene.menu.selected == index:
            return
        app.step([DOWN])
    raise AssertionError(f"item {index} cannot be selected")


def finish(app: App, scene: GenerateScene) -> None:
    """Wait for the background generation, then let the scene pick up its outcome."""
    worker = scene.worker
    assert worker is not None
    worker.join(timeout=10)
    assert not worker.is_alive()
    app.step([])


def generate_now(app: App, scene: GenerateScene) -> None:
    select(app, scene, GENERATE)
    app.step([ENTER])
    finish(app, scene)


def names(app: App) -> list[str]:
    return [s.name for s in app.stack]


def test_starts_on_default_preset_with_random_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch)
    assert scene.preset_id == "medium"
    assert scene.seed_text == ""
    assert scene.result is None
    assert not scene.busy
    assert not scene.menu.items[PLAY].enabled
    assert not scene.menu.items[REGENERATE].enabled
    assert not scene.menu.items[SAVE].enabled


def test_generate_adds_to_generated_pack_and_opens_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, ctx, scene, fake = make_app(tmp_path, monkeypatch)
    generate_now(app, scene)
    assert fake.calls == [("medium", None)]
    assert scene.result is not None
    assert scene.result.entry.id == "medium-7"
    assert scene.menu.selected == PLAY
    assert ctx.pack(GENERATED_ID).levels == ()  # nothing saved before Play or Save

    app.step([ENTER])  # Play
    assert names(app) == ["main_menu", "game"]
    game = app.top
    assert isinstance(game, GameScene)
    assert game.pack.id == GENERATED_ID
    assert game.entry.id == "medium-7"
    assert [e.id for e in ctx.pack(GENERATED_ID).levels] == ["medium-7"]
    assert (tmp_path / "generated.json").exists()


def test_save_keeps_the_scene_and_stores_the_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, ctx, scene, _fake = make_app(tmp_path, monkeypatch)
    generate_now(app, scene)
    select(app, scene, SAVE)
    app.step([ENTER])
    assert names(app) == ["main_menu", "generate"]
    assert [e.id for e in ctx.pack(GENERATED_ID).levels] == ["medium-7"]
    assert "Generated" in scene.status
    assert not scene.menu.items[SAVE].enabled  # already saved
    reloaded = AppContext.load(tmp_path, bundled=[])
    assert [e.id for e in reloaded.pack(GENERATED_ID).levels] == ["medium-7"]


def test_preset_changes_with_left_right_and_reaches_the_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ctx, scene, fake = make_app(tmp_path, monkeypatch)
    assert scene.menu.selected == PRESET
    app.step([RIGHT])
    assert scene.preset_id == "hard"
    app.step([RIGHT])
    assert scene.preset_id == "easy"  # wraps
    app.step([LEFT])
    assert scene.preset_id == "hard"
    app.step([ENTER])  # confirm cycles forward too
    assert scene.preset_id == "easy"
    generate_now(app, scene)
    assert fake.calls == [("easy", None)]


def test_seed_input_digits_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ctx, scene, fake = make_app(tmp_path, monkeypatch)
    app.step([digit("4"), key(pygame.K_a, 4, "a"), digit("2"), key(pygame.K_MINUS, 45, "-")])
    assert scene.seed_text == "42"
    assert scene.menu.selected == SEED  # typing a digit focuses the seed field
    app.step([BACKSPACE])
    assert scene.seed_text == "4"
    app.step([digit("0")])
    generate_now(app, scene)
    assert fake.calls == [("medium", 40)]
    assert scene.result is not None
    assert scene.result.entry.id == "medium-40"


def test_seed_is_bounded_and_leading_zeros_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch)
    app.step([digit("0"), digit("0")])
    assert scene.seed_text == "0"
    app.step([BACKSPACE])
    app.step([digit(c) for c in "2147483647"])
    assert scene.seed_text == "2147483647"
    app.step([digit("1")])  # an 11th digit would leave the seed range
    assert scene.seed_text == "2147483647"
    app.step([BACKSPACE, digit("9")])
    assert scene.seed_text == "214748364"  # 2147483649 is above the largest seed: refused


def test_backspace_on_seed_does_not_leave_the_scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch)
    app.step([BACKSPACE, BACKSPACE])
    assert names(app) == ["main_menu", "generate"]
    assert scene.seed_text == ""


def test_regenerate_draws_a_new_random_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ctx, scene, fake = make_app(tmp_path, monkeypatch)
    app.step([digit("5")])
    generate_now(app, scene)
    select(app, scene, REGENERATE)
    app.step([ENTER])
    finish(app, scene)
    assert fake.calls == [("medium", 5), ("medium", None)]
    assert scene.seed_text == ""


def test_failure_shows_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_preset: str, _seed: int | None, _stop: object) -> GeneratedLevel:
        raise GenerationFailed("no level")

    app, _ctx, scene, fake = make_app(tmp_path, monkeypatch, FakeGenerator(fail))
    generate_now(app, scene)
    assert not scene.busy
    assert scene.result is None
    assert scene.failed
    assert "No level" in scene.status
    assert scene.menu.selected == GENERATE
    assert scene.menu.items[GENERATE].text == "Try again"
    app.step([ENTER])  # retry
    finish(app, scene)
    assert len(fake.calls) == 2


def test_unexpected_error_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def crash(_preset: str, _seed: int | None, _stop: object) -> GeneratedLevel:
        raise MemoryError

    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch, FakeGenerator(crash))
    generate_now(app, scene)
    assert not scene.busy
    assert scene.failed
    assert scene.status


def blocking_generator(started: threading.Event) -> FakeGenerator:
    def wait_for_stop(_preset: str, _seed: int | None, should_stop: Callable[[], bool]) -> GeneratedLevel:
        started.set()
        while not should_stop():
            threading.Event().wait(0.005)
        raise GenerationCancelled("cancelled")

    return FakeGenerator(wait_for_stop)


def test_back_cancels_a_running_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch, blocking_generator(started))
    select(app, scene, GENERATE)
    app.step([ENTER])
    assert started.wait(5)
    assert scene.busy
    assert scene.menu.items[GENERATE].text == "Cancel"
    assert not scene.menu.items[PRESET].enabled
    app.step([ESCAPE])
    assert names(app) == ["main_menu", "generate"]  # first Esc only cancels
    finish(app, scene)
    assert not scene.busy
    assert "cancelled" in scene.status
    app.step([ESCAPE])
    assert names(app) == ["main_menu"]


def test_leaving_the_scene_stops_the_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch, blocking_generator(started))
    select(app, scene, GENERATE)
    app.step([ENTER])
    assert started.wait(5)
    worker = scene.worker
    assert worker is not None
    app.quit()
    worker.join(timeout=5)
    assert not worker.is_alive()


def test_a_stale_result_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cancelled job that still returns a level must not overwrite the next job's state."""
    release = threading.Event()

    def late(preset: str, seed: int | None, _stop: object) -> GeneratedLevel:
        release.wait(5)
        par = Par(pushes=2, moves=4, lurd="rRR", solver="push-astar/1")
        return GeneratedLevel(LevelEntry(f"{preset}-{seed}", LEVEL, par=par, seed=seed), attempts=1)

    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch, FakeGenerator(late))
    app.step([digit("1")])
    select(app, scene, GENERATE)
    app.step([ENTER])
    old = scene.worker
    app.step([ESCAPE])  # cancel: the fake ignores should_stop and will still return a level
    release.set()
    assert old is not None
    old.join(5)
    app.step([])
    assert scene.result is None
    assert not scene.busy


def test_back_returns_when_idle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch)
    select(app, scene, BACK)
    app.step([ENTER])
    assert names(app) == ["main_menu"]


def test_real_generator_easy_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alexvolkihar_sokoban.generator.api import generate

    app, ctx, scene, _fake = make_app(
        tmp_path, monkeypatch, FakeGenerator(lambda p, s, stop: generate(p, s, should_stop=stop))
    )
    app.step([LEFT])  # medium -> easy
    app.step([digit("4"), digit("2")])
    generate_now(app, scene)
    assert scene.result is not None
    entry = scene.result.entry
    assert entry.id == "easy-42"
    assert entry.par is not None
    assert entry.par.pushes >= PRESETS["easy"].min_pushes
    select(app, scene, PLAY)
    app.step([ENTER])
    assert ctx.pack(GENERATED_ID).entry("easy-42").level == entry.level


def test_play_and_save_disabled_without_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from alexvolkihar_sokoban.persistence.settings import Settings

    monkeypatch.setattr(generate_module, "generate_level", FakeGenerator())
    app = App(Settings(), headless=True)
    scene = app.push("generate")
    assert isinstance(scene, GenerateScene)
    generate_now(app, scene)
    assert scene.result is not None
    assert not scene.menu.items[PLAY].enabled
    assert not scene.menu.items[SAVE].enabled
    assert scene.menu.items[REGENERATE].enabled


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("language", ["en", "fr"])
def test_draws_every_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int], language: str
) -> None:
    started = threading.Event()
    gate = threading.Event()

    def slow(preset: str, seed: int | None, should_stop: Callable[[], bool]) -> GeneratedLevel:
        started.set()
        gate.wait(5)
        if should_stop():
            raise GenerationCancelled("cancelled")
        return FakeGenerator()(preset, seed)

    app, _ctx, scene, _fake = make_app(tmp_path, monkeypatch, FakeGenerator(slow), language=language)
    app.settings.window = size
    app.apply_display_settings()
    app.step([])  # idle
    select(app, scene, GENERATE)
    app.step([ENTER])
    assert started.wait(5)
    app.step([], 700)  # busy
    gate.set()
    finish(app, scene)  # result
    assert scene.result is not None
    scene.status = "x" * 300  # a long status must not break the layout
    app.step([])
