from pathlib import Path

import pytest

from alexvolkihar_sokoban.persistence import paths


def test_constants() -> None:
    assert paths.APP_NAME == "alexvolkihar-sokoban"
    assert paths.ENV_HOME == "ALEXVOLKIHAR_SOKOBAN_HOME"


def test_data_dir_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    platform_dir = tmp_path / "platform"
    monkeypatch.setattr(paths, "user_data_dir", lambda *a, **k: str(platform_dir))
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    assert paths.data_dir() == platform_dir
    assert platform_dir.is_dir()

    env_dir = tmp_path / "env"
    monkeypatch.setenv(paths.ENV_HOME, str(env_dir))
    assert paths.data_dir() == env_dir
    assert env_dir.is_dir()

    override = tmp_path / "override" / "nested"
    assert paths.data_dir(override) == override
    assert override.is_dir()


def test_platformdirs_called_with_app_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []

    def fake(*args: object, **kwargs: object) -> str:
        calls.append((*args, kwargs))
        return str(tmp_path / "p")

    monkeypatch.setattr(paths, "user_data_dir", fake)
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    paths.data_dir()
    assert calls == [("alexvolkihar-sokoban", {"appauthor": False})]


def test_empty_env_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "user_data_dir", lambda *a, **k: str(tmp_path / "p"))
    monkeypatch.setenv(paths.ENV_HOME, "")
    assert paths.data_dir() == tmp_path / "p"


def test_env_expands_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv(paths.ENV_HOME, "~/sok")
    assert paths.data_dir() == tmp_path / "sok"


def test_uncreatable_dir_does_not_raise(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    # A regular file stands where a parent directory should be: mkdir fails with OSError.
    assert paths.data_dir(blocker / "data") == blocker / "data"
