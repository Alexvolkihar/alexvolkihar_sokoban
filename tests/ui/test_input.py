from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.persistence.settings import ACTIONS, DEFAULT_KEYBINDINGS
from alexvolkihar_sokoban.ui.i18n import set_language
from alexvolkihar_sokoban.ui.input import Action, InputMapper, describe_binding


@pytest.fixture(autouse=True)
def _pygame() -> Iterator[None]:
    pygame.init()
    yield


def key(k: int, scancode: int = 0, mod: int = pygame.KMOD_NONE) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, mod=mod, unicode="")


def test_action_enum_matches_settings() -> None:
    assert [a.value for a in Action] == list(ACTIONS)
    assert Action.UP == "up"


def test_wasd_bound_by_scancode() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    # The physical W key of a QWERTY board is Z on AZERTY: same scancode, different key.
    assert mapper.actions_for(key(pygame.K_z, scancode=26)) == [Action.UP]
    assert mapper.actions_for(key(pygame.K_w, scancode=26)) == [Action.UP]
    assert mapper.actions_for(key(pygame.K_q, scancode=4)) == [Action.LEFT]


def test_named_keys() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    assert mapper.actions_for(key(pygame.K_UP, scancode=82)) == [Action.UP]
    assert mapper.actions_for(key(pygame.K_RETURN, scancode=40)) == [Action.CONFIRM]
    # Escape is both pause and back, in ACTIONS order.
    assert mapper.actions_for(key(pygame.K_ESCAPE, scancode=41)) == [Action.PAUSE, Action.BACK]


def test_ctrl_binding_requires_ctrl() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    assert mapper.actions_for(key(pygame.K_z, scancode=29, mod=pygame.KMOD_LCTRL)) == [Action.UNDO]
    assert mapper.actions_for(key(pygame.K_z, scancode=29)) == []
    # A plain binding does not fire while Ctrl is held (Ctrl+Z on AZERTY is the physical W key).
    assert mapper.actions_for(key(pygame.K_z, scancode=26, mod=pygame.KMOD_RCTRL)) == [Action.UNDO]
    assert mapper.actions_for(key(pygame.K_u, scancode=24, mod=pygame.KMOD_LCTRL)) == []


def test_non_key_events_give_no_action() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    assert mapper.actions_for(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=1)) == []
    assert mapper.actions_for(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP, scancode=82, mod=0)) == []


def test_set_bindings_replaces_and_ignores_invalid() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    mapper.set_bindings({"up": ["key:k", "key:no-such-key", "garbage"], "hint": ["scan:11"]})
    assert mapper.actions_for(key(pygame.K_k, scancode=14)) == [Action.UP]
    assert mapper.actions_for(key(pygame.K_UP, scancode=82)) == []
    assert mapper.actions_for(key(pygame.K_h, scancode=11)) == [Action.HINT]


def test_binding_from_event() -> None:
    mapper = InputMapper(DEFAULT_KEYBINDINGS)
    assert mapper.binding_from_event(key(pygame.K_k, scancode=14)) == "key:k"
    assert mapper.binding_from_event(key(pygame.K_z, scancode=29, mod=pygame.KMOD_LCTRL)) == "ctrl+key:z"
    assert mapper.binding_from_event(key(pygame.K_UNKNOWN, scancode=100)) == "scan:100"
    assert mapper.binding_from_event(key(pygame.K_LCTRL, scancode=224, mod=pygame.KMOD_LCTRL)) is None
    assert (
        mapper.binding_from_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_k, scancode=14, mod=0))
        is None
    )
    # What binding_from_event returns, the mapper understands.
    mapper.set_bindings({"hint": [mapper.binding_from_event(key(pygame.K_F1, scancode=58)) or ""]})
    assert mapper.actions_for(key(pygame.K_F1, scancode=58)) == [Action.HINT]


def test_describe_binding() -> None:
    assert describe_binding("scan:26") == "W"
    assert describe_binding("scan:4") == "A"
    assert describe_binding("ctrl+key:z") == "Ctrl+Z"
    assert describe_binding("key:up") == "Up"
    assert describe_binding("key:return") == "Return"
    assert describe_binding("key:left ctrl") == "Left Ctrl"
    assert describe_binding("scan:250") == "Scan 250"


def test_describe_binding_names_keys_in_french() -> None:
    set_language("fr")
    try:
        assert describe_binding("scan:41") == "Échap"
        assert describe_binding("key:return") == "Entrée"
        assert describe_binding("scan:44") == "Espace"
        assert describe_binding("scan:42") == "Retour arrière"
        arrows = [describe_binding(f"scan:{c}") for c in (82, 81, 80, 79)]
        assert arrows == ["Haut", "Bas", "Gauche", "Droite"]
        assert describe_binding("key:delete") == "Suppr"
        assert describe_binding("ctrl+key:z") == "Ctrl+Z" and describe_binding("scan:26") == "W"
        assert describe_binding("key:left ctrl") == "Left Ctrl"  # rare keys keep pygame's English name
    finally:
        set_language("en")
    assert describe_binding("scan:41") == "Escape"
