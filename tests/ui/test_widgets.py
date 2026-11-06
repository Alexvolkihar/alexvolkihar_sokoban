from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.themes.fallback import FallbackTheme
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList, ScrollList, draw_row_bar, fit_text, wrap_text


@pytest.fixture(autouse=True)
def _pygame() -> Iterator[None]:
    pygame.init()
    yield


def make_menu(chosen: list[str]) -> MenuList:
    return MenuList(
        [
            MenuItem("a", lambda: chosen.append("a")),
            MenuItem("b", lambda: chosen.append("b"), enabled=False),
            MenuItem(lambda: "c", lambda: chosen.append("c")),
        ]
    )


def test_menu_wraps_and_skips_disabled() -> None:
    chosen: list[str] = []
    menu = make_menu(chosen)
    assert menu.selected == 0
    assert menu.handle_action(Action.DOWN)
    assert menu.selected == 2
    menu.handle_action(Action.DOWN)
    assert menu.selected == 0
    menu.handle_action(Action.UP)
    assert menu.selected == 2
    assert menu.handle_action(Action.CONFIRM)
    assert chosen == ["c"]
    assert not menu.handle_action(Action.HINT)


def test_menu_starts_on_first_enabled_item() -> None:
    menu = MenuList([MenuItem("x", lambda: None, enabled=False), MenuItem("y", lambda: None)])
    assert menu.selected == 1


def test_menu_with_nothing_enabled_does_nothing() -> None:
    chosen: list[str] = []
    menu = MenuList([MenuItem("x", lambda: chosen.append("x"), enabled=False)])
    menu.handle_action(Action.DOWN)
    menu.handle_action(Action.CONFIRM)
    assert chosen == []


def test_menu_item_label_can_be_dynamic() -> None:
    name = ["one"]
    item = MenuItem(lambda: name[0], lambda: None)
    assert item.text == "one"
    name[0] = "two"
    assert item.text == "two"


def test_menu_mouse_hover_and_click() -> None:
    chosen: list[str] = []
    menu = make_menu(chosen)
    surface = pygame.Surface((300, 300))
    theme = FallbackTheme()
    menu.draw(surface, pygame.Rect(0, 0, 300, 300), pygame.font.Font(None, 30), theme.palette)
    rects = menu.item_rects
    assert len(rects) == 3 and all(surface.get_rect().contains(r) for r in rects)
    assert menu.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=rects[2].center, rel=(0, 0), buttons=())
    )
    assert menu.selected == 2
    # Disabled items ignore the mouse.
    assert not menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rects[1].center, button=1))
    assert chosen == []
    assert menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rects[0].center, button=1))
    assert chosen == ["a"] and menu.selected == 0
    assert not menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(299, 299), button=1))


def test_fit_text_keeps_text_that_fits() -> None:
    font = pygame.font.Font(None, 24)
    assert fit_text("short", font, 500) == "short"


def test_fit_text_cuts_with_an_ellipsis_within_the_width() -> None:
    font = pygame.font.Font(None, 24)
    text = "a rather long line of text that cannot fit"
    cut = fit_text(text, font, 120)
    assert cut.endswith("…") and font.size(cut)[0] <= 120
    assert text.startswith(cut[:-1].rstrip())
    assert fit_text(text, font, 1) == "…"


def test_wrap_text_keeps_every_word_and_the_width() -> None:
    font = pygame.font.Font(None, 24)
    text = "the quick brown fox jumps over the lazy dog " * 3
    lines = wrap_text(text, font, 150)
    assert len(lines) > 1 and all(font.size(line)[0] <= 150 for line in lines)
    assert " ".join(lines).split() == text.split()


def test_wrap_text_cuts_a_word_longer_than_a_line() -> None:
    font = pygame.font.Font(None, 24)
    word = "x" * 60
    lines = wrap_text(word, font, 100)
    assert len(lines) > 1 and "".join(lines) == word
    assert all(font.size(line)[0] <= 100 for line in lines)
    assert wrap_text("", font, 100) == []


def test_scroll_list_wraps_and_clamps() -> None:
    lst = ScrollList(5)
    lst.move(-1)
    assert lst.selected == 4
    rows = lst.layout(pygame.Rect(0, 0, 100, 60), 20)
    assert [i for i, _ in rows] == [2, 3, 4] and lst.first == 2
    assert lst.more_above and not lst.more_below
    lst.move(1)
    assert [i for i, _ in lst.layout(pygame.Rect(0, 0, 100, 60), 20)] == [0, 1, 2]
    assert lst.more_below and not lst.more_above
    lst.move(-3, wrap=False)
    assert lst.selected == 0
    empty = ScrollList(0)
    empty.move(1)
    assert empty.selected == 0 and empty.layout(pygame.Rect(0, 0, 100, 60), 20) == []


def test_scroll_list_mouse_hover_wheel_and_click() -> None:
    lst = ScrollList(10)
    rows = lst.layout(pygame.Rect(0, 0, 100, 60), 20)
    hover = pygame.event.Event(pygame.MOUSEMOTION, pos=rows[1][1].center)
    assert lst.handle_event(hover) is None and lst.selected == 1
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rows[2][1].center, button=1)
    assert lst.handle_event(click) == 2
    lst.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3))
    assert lst.selected == 5
    assert lst.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 500))) is None


def test_draw_row_bar_outlines_the_row_with_the_accent() -> None:
    palette = FallbackTheme().palette
    surface = pygame.Surface((100, 40))
    surface.fill((0, 0, 0))
    rect = pygame.Rect(10, 10, 80, 20)
    draw_row_bar(surface, rect, palette)
    assert surface.get_at((rect.centerx, rect.top))[:3] == palette.accent
    assert surface.get_at(rect.center)[:3] == palette.panel
