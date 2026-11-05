from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.themes.fallback import FallbackTheme
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList


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
