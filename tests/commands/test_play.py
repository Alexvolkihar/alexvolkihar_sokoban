import argparse
from pathlib import Path

import pygame
import pytest

from alexvolkihar_sokoban import cli
from alexvolkihar_sokoban.commands import play
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.context import AppContext
from alexvolkihar_sokoban.ui.i18n import get_language, set_language

REPO = Path(__file__).resolve().parents[2]
ROOM = REPO / "tests" / "fixtures" / "formats" / "legacy_room.txt"
XSB_TWO = "#####\n#@$.#\n#####\n\n######\n#@ $.#\n######\n"


def _key(k: int, scancode: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=0, unicode="")


ESCAPE = _key(pygame.K_ESCAPE, 41)
UP = _key(pygame.K_UP, 82)
ENTER = _key(pygame.K_RETURN, 40)


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


class Frames:
    """Replaces ``App.run``: a few frames, then remembers the stack and the context."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, frames: int = 3) -> None:
        self.frames = frames
        self.stack: list[str] = []
        self.apps: list[App] = []
        frames_ref = self

        def fake_run(app: App) -> None:
            if not app.stack:
                app.push("main_menu")
            for _ in range(frames_ref.frames):
                app.step([])
            frames_ref.apps.append(app)
            frames_ref.stack = [s.name for s in app.stack]

        monkeypatch.setattr(App, "run", fake_run)


def run_play(tmp_path: Path, *argv: str) -> int:
    return cli.main(["--data-dir", str(tmp_path / "data"), "play", *argv])


def test_play_command_opens_game_headless(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    assert run_play(tmp_path, str(ROOM)) == 0
    assert frames.stack == ["main_menu", "game"]
    app = frames.apps[0]
    assert isinstance(app.context, AppContext)
    assert app.context.data_dir == tmp_path / "data"
    assert app.settings is app.context.settings


def test_play_without_path_opens_the_main_menu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    assert run_play(tmp_path) == 0
    assert frames.stack == ["main_menu"]


def test_no_subcommand_opens_the_main_menu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    assert cli.main(["--data-dir", str(tmp_path)]) == 0
    assert frames.stack == ["main_menu"]


def test_play_level_option_picks_the_level(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    path = tmp_path / "two.xsb"
    path.write_text(XSB_TWO, encoding="utf-8")
    assert run_play(tmp_path, str(path), "--level", "2") == 0
    game = frames.apps[0].stack[-1]
    assert game.name == "game" and game.entry.id == "2"  # type: ignore[attr-defined]


def test_escape_in_the_game_returns_to_the_main_menu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    assert run_play(tmp_path, str(ROOM)) == 0
    app = frames.apps[0]
    app.step([ESCAPE])  # opens the pause menu
    app.step([UP, ENTER])  # Up wraps to its last item: Main menu
    assert [s.name for s in app.stack] == ["main_menu"] and app.running


def test_unreadable_file_exits_2_without_a_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frames = Frames(monkeypatch)
    assert run_play(tmp_path, str(tmp_path / "missing.xsb")) == 2
    assert frames.apps == []
    assert "missing.xsb" in capsys.readouterr().err


def test_unknown_level_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frames = Frames(monkeypatch)
    assert run_play(tmp_path, str(ROOM), "--level", "42") == 2
    assert frames.apps == []
    assert "42" in capsys.readouterr().err


def test_file_warnings_reach_the_main_menu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    path = tmp_path / "mixed.xsb"
    path.write_text(XSB_TWO + "\n#####\n#@$ #\n#####\n", encoding="utf-8")
    assert run_play(tmp_path, str(path)) == 0
    app = frames.apps[0]
    assert app.context is not None
    app.step([ESCAPE])  # pause menu, then its last item: back to the main menu, which shows the skipped level
    app.step([UP, ENTER])
    menu = app.top
    assert menu is not None and menu.name == "main_menu"
    assert any("mixed" in m for m in menu.messages)  # type: ignore[attr-defined]


def test_play_args_without_data_dir_use_the_env_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frames = Frames(monkeypatch)
    monkeypatch.setenv("ALEXVOLKIHAR_SOKOBAN_HOME", str(tmp_path / "home"))
    assert play.run(argparse.Namespace(path=None, level=None)) == 0
    assert frames.apps[0].context is not None
    assert frames.apps[0].context.data_dir == tmp_path / "home"
