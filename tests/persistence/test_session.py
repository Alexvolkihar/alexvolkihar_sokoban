import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from alexvolkihar_sokoban.persistence.session import SESSION_FORMAT, SESSION_VERSION, SavedSession
from alexvolkihar_sokoban.persistence.settings import SETTINGS_FORMAT, SETTINGS_VERSION, Settings
from alexvolkihar_sokoban.persistence.store import JsonStore

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"

HASH = "sha256:" + "ab" * 32

SESSION = SavedSession(
    pack_id="lama-original",
    level_id="1",
    level_hash=HASH,
    lurd="rrUld",
    redo_lurd="Dl",
    elapsed_ms=12_345,
    assisted=False,
    saved_at="2026-11-05T14:03:22Z",
)


def test_constants() -> None:
    assert SESSION_FORMAT == "alexvolkihar-sokoban/session"
    assert SESSION_VERSION == 1


def test_session_roundtrip() -> None:
    d = SESSION.to_dict()
    assert d == {
        "pack_id": "lama-original",
        "level_id": "1",
        "level_hash": HASH,
        "lurd": "rrUld",
        "redo_lurd": "Dl",
        "elapsed_ms": 12_345,
        "assisted": False,
        "saved_at": "2026-11-05T14:03:22Z",
    }
    assert SavedSession.from_dict(d) == SESSION


def test_session_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        SESSION.lurd = "x"  # type: ignore[misc]


def test_empty_histories_are_valid() -> None:
    s = replace(SESSION, lurd="", redo_lurd="", elapsed_ms=0)
    assert SavedSession.from_dict(s.to_dict()) == s


def test_unknown_keys_ignored() -> None:
    assert SavedSession.from_dict({**SESSION.to_dict(), "extra": 1}) == SESSION


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pack_id", ""),
        ("pack_id", 3),
        ("level_id", None),
        ("level_hash", "md5:abc"),
        ("level_hash", "sha256:" + "AB" * 32),
        ("lurd", "rrx"),
        ("lurd", 5),
        ("redo_lurd", "r r"),
        ("elapsed_ms", -1),
        ("elapsed_ms", 1.5),
        ("elapsed_ms", True),
        ("assisted", "no"),
        ("assisted", 0),
        ("saved_at", "yesterday"),
        ("saved_at", "2026-11-05 14:03:22"),
    ],
)
def test_invalid_field_raises(key: str, value: Any) -> None:
    with pytest.raises(ValueError, match=key):
        SavedSession.from_dict({**SESSION.to_dict(), key: value})


def test_missing_field_raises() -> None:
    d = SESSION.to_dict()
    del d["lurd"]
    with pytest.raises(ValueError, match="lurd"):
        SavedSession.from_dict(d)


# --- JSON Schemas (schemas/*.schema.json) describe the files the store writes ---


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _written(tmp_path: Path, name: str, payload: dict[str, object], fmt: str, version: int) -> Any:
    assert JsonStore(tmp_path).save(name, payload, format_id=fmt, version=version)
    return json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "settings",
    [Settings(), Settings(language="fr", theme="neon", fullscreen=True, window=(640, 480), animation="off")],
)
def test_settings_files_validate_against_schema(tmp_path: Path, settings: Settings) -> None:
    doc = _written(tmp_path, "settings", settings.to_dict(), SETTINGS_FORMAT, SETTINGS_VERSION)
    _validator("settings").validate(doc)


def test_session_file_validates_against_schema(tmp_path: Path) -> None:
    doc = _written(tmp_path, "session", SESSION.to_dict(), SESSION_FORMAT, SESSION_VERSION)
    _validator("session").validate(doc)


@pytest.mark.parametrize(
    "patch",
    [
        {"format": "alexvolkihar-sokoban/session"},
        {"version": 2},
        {"language": "de"},
        {"window": [320, 200]},
        {"animation": "wild"},
        {"keybindings": {"up": ["nonsense"]}},
        {"unknown": 1},
    ],
)
def test_settings_schema_rejects_invalid_files(patch: dict[str, object]) -> None:
    doc = {"format": SETTINGS_FORMAT, "version": SETTINGS_VERSION, **Settings().to_dict(), **patch}
    assert not _validator("settings").is_valid(doc)


@pytest.mark.parametrize(
    "patch",
    [
        {"format": "alexvolkihar-sokoban/settings"},
        {"level_hash": "sha256:xyz"},
        {"lurd": "abc"},
        {"elapsed_ms": -5},
        {"assisted": "yes"},
        {"saved_at": "2026-11-05"},
        {"unknown": 1},
    ],
)
def test_session_schema_rejects_invalid_files(patch: dict[str, object]) -> None:
    doc = {"format": SESSION_FORMAT, "version": SESSION_VERSION, **SESSION.to_dict(), **patch}
    assert not _validator("session").is_valid(doc)


def test_session_schema_and_from_dict_agree_on_rejections() -> None:
    bad = {**SESSION.to_dict(), "lurd": "abc"}
    with pytest.raises(ValueError):
        SavedSession.from_dict(bad)
    assert not _validator("session").is_valid({"format": SESSION_FORMAT, "version": SESSION_VERSION, **bad})


def test_settings_schema_lists_exactly_the_actions() -> None:
    from alexvolkihar_sokoban.persistence.settings import ACTIONS

    schema = json.loads((SCHEMAS / "settings.schema.json").read_text(encoding="utf-8"))
    keybindings = schema["properties"]["keybindings"]
    assert sorted(keybindings["required"]) == sorted(ACTIONS)
    assert sorted(keybindings["properties"]) == sorted(ACTIONS)
