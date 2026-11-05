from typing import Any

import pytest

from alexvolkihar_sokoban.persistence.settings import (
    ACTIONS,
    DEFAULT_KEYBINDINGS,
    SETTINGS_FORMAT,
    SETTINGS_VERSION,
    Settings,
    default_language,
)


def test_settings_roundtrip_and_defaults() -> None:
    s = Settings(language="fr", theme="neon")
    assert Settings.from_dict(s.to_dict()) == s
    assert Settings.from_dict({"animation": "wild", "theme": 3}).animation == "normal"
    assert Settings.from_dict({"keybindings": {"up": ["key:k"]}}).keybindings["down"] == (
        "key:down",
        "scan:22",
    )


def test_defaults() -> None:
    s = Settings()
    assert (s.language, s.theme, s.fullscreen, s.window, s.animation, s.show_timer) == (
        "en",
        "kenney",
        False,
        (1024, 768),
        "normal",
        True,
    )
    assert s.keybindings == dict(DEFAULT_KEYBINDINGS)
    assert set(ACTIONS) == set(DEFAULT_KEYBINDINGS)
    assert DEFAULT_KEYBINDINGS["up"] == ("key:up", "scan:26")
    assert DEFAULT_KEYBINDINGS["undo"] == ("key:u", "key:backspace", "ctrl+key:z")
    assert DEFAULT_KEYBINDINGS["back"] == ("key:escape",)
    assert (SETTINGS_FORMAT, SETTINGS_VERSION) == ("alexvolkihar-sokoban/settings", 1)


def test_default_keybindings_are_not_shared_between_instances() -> None:
    a, b = Settings(), Settings()
    a.keybindings["up"] = ("key:k",)
    assert b.keybindings["up"] == ("key:up", "scan:26") and DEFAULT_KEYBINDINGS["up"] == ("key:up", "scan:26")


def test_to_dict_is_plain_json_without_format() -> None:
    d = Settings().to_dict()
    assert "format" not in d and "version" not in d
    assert d["window"] == [1024, 768]
    assert d["keybindings"] == {k: list(v) for k, v in DEFAULT_KEYBINDINGS.items()}
    assert set(d) == {"language", "theme", "fullscreen", "window", "animation", "show_timer", "keybindings"}


def test_custom_values_survive() -> None:
    data: dict[str, Any] = {
        "format": SETTINGS_FORMAT,
        "version": 1,
        "language": "fr",
        "theme": "contrast",
        "fullscreen": True,
        "window": [1280, 720],
        "animation": "off",
        "show_timer": False,
        "keybindings": {"up": ["key:k", "ctrl+scan:26"], "jump": ["key:j"]},
        "unknown": 1,
    }
    s = Settings.from_dict(data)
    assert (s.language, s.theme, s.fullscreen, s.window, s.animation, s.show_timer) == (
        "fr",
        "contrast",
        True,
        (1280, 720),
        "off",
        False,
    )
    assert s.keybindings["up"] == ("key:k", "ctrl+scan:26") and "jump" not in s.keybindings
    assert set(s.keybindings) == set(ACTIONS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("language", "de"),
        ("language", None),
        ("theme", ""),
        ("theme", 3),
        ("fullscreen", "yes"),
        ("fullscreen", 1),
        ("window", [800]),
        ("window", "1024x768"),
        ("window", [100, 100]),
        ("window", [True, 600]),
        ("animation", "wild"),
        ("show_timer", None),
        ("keybindings", "up"),
    ],
)
def test_each_invalid_field_falls_back_to_its_default(field: str, value: Any) -> None:
    s = Settings.from_dict({field: value, "language": "fr"} if field != "language" else {field: value})
    assert getattr(s, field) == getattr(Settings(), field)


@pytest.mark.parametrize("binding", [[], ["up"], ["key:"], ["scan:x"], ["alt+key:a"], [3], "key:k"])
def test_invalid_bindings_fall_back_per_action(binding: Any) -> None:
    s = Settings.from_dict({"keybindings": {"up": binding, "down": ["key:j"]}})
    assert s.keybindings["up"] == DEFAULT_KEYBINDINGS["up"] and s.keybindings["down"] == ("key:j",)


def test_default_language() -> None:
    assert default_language("fr_FR") == "fr" and default_language(None) == "en"
    assert default_language("FR-ca") == "fr" and default_language("en_US.UTF-8") == "en"
    assert default_language("") == "en" and default_language("de_DE") == "en"
