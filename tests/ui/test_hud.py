import pygame
import pytest

from alexvolkihar_sokoban.core.pack import Par
from alexvolkihar_sokoban.persistence.settings import DEFAULT_KEYBINDINGS, Settings
from alexvolkihar_sokoban.ui.app import App
from alexvolkihar_sokoban.ui.hud import (
    HudData,
    draw_hud,
    draw_toast,
    format_time,
    hud_stats,
    key_hints,
    par_text,
)
from alexvolkihar_sokoban.ui.i18n import get_language, set_language

PAR = Par(pushes=8, moves=30, lurd="", solver="push-astar/1")


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def test_format_time() -> None:
    assert format_time(0) == "0:00"
    assert format_time(999) == "0:00"
    assert format_time(61_000) == "1:01"
    assert format_time(10 * 60_000 + 5_000) == "10:05"
    assert format_time(3_600_000 + 2 * 60_000 + 3_000) == "1:02:03"


def test_par_text() -> None:
    assert par_text(PAR) == "8/30"
    assert par_text(None) == "—"


def test_hud_stats_in_english() -> None:
    set_language("en")
    stats = hud_stats(moves=12, pushes=3, elapsed_ms=65_000, par=PAR)
    assert [(s.label, s.value) for s in stats] == [
        ("Moves", "12"),
        ("Pushes", "3"),
        ("Time", "1:05"),
        ("Par pushes/moves", "8/30"),
    ]


def test_hud_texts_in_french() -> None:
    set_language("fr")
    stats = hud_stats(moves=12, pushes=3, elapsed_ms=65_000, par=None)
    assert [(s.label, s.value) for s in stats] == [
        ("Pas", "12"),
        ("Poussées", "3"),
        ("Temps", "1:05"),
        ("Par poussées/pas", "—"),
    ]
    hints = key_hints(DEFAULT_KEYBINDINGS)
    assert "U annuler" in hints and "Y rétablir" in hints
    assert "R ×2 recommencer" in hints and "Escape pause" in hints


def test_hidden_timer_drops_the_time_stat() -> None:
    set_language("en")
    labels = [s.label for s in hud_stats(moves=0, pushes=0, elapsed_ms=None, par=PAR)]
    assert labels == ["Moves", "Pushes", "Par pushes/moves"]


def test_key_hints_follow_rebinding_and_skip_unbound_actions() -> None:
    set_language("en")
    bindings = {**DEFAULT_KEYBINDINGS, "undo": ("ctrl+key:z",), "redo": ()}
    hints = key_hints(bindings)
    assert "Ctrl+Z undo" in hints
    assert not any("redo" in h for h in hints)


@pytest.mark.parametrize("size", [(640, 480), (1024, 768), (1920, 1080)])
def test_draw_hud_leaves_a_board_area_inside_the_screen(size: tuple[int, int]) -> None:
    set_language("fr")
    app = App(Settings(window=size), headless=True)
    data = HudData(
        title="Boxoban (difficile) — Niveau 100 avec un titre vraiment très long qui ne tient pas",
        stats=hud_stats(moves=1234, pushes=567, elapsed_ms=3_600_000, par=PAR),
        hints=key_hints(DEFAULT_KEYBINDINGS),
    )
    area = draw_hud(app.screen, app.fonts, app.theme.palette, data)
    screen = app.screen.get_rect()
    assert screen.contains(area)
    draw_toast(app.screen, app.fonts, app.theme.palette, area, "Appuyez encore sur R pour recommencer")
    assert area.height >= screen.height // 2 and area.width >= screen.width * 9 // 10
    assert isinstance(area, pygame.Rect)
