import json
import os
from pathlib import Path

import pytest

from alexvolkihar_sokoban.persistence import store as store_module
from alexvolkihar_sokoban.persistence.migrations import MigrationRegistry
from alexvolkihar_sokoban.persistence.store import JsonStore

FMT = "alexvolkihar-sokoban/settings"


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_save_is_atomic_and_load_roundtrips(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    payload: dict[str, object] = {"language": "fr", "nested": {"a": [1, 2]}, "accent": "é"}
    assert st.save("settings", payload, format_id=FMT, version=1) is True
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk == {"format": FMT, "version": 1, **payload}
    assert list(on_disk)[:2] == ["format", "version"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]  # no *.tmp left behind
    res = st.load("settings", format_id=FMT, version=1)
    assert res.status == "ok"
    assert res.data == payload
    assert res.backup_path is None


def test_save_overwrites_previous_file(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1)
    assert st.save("settings", {"a": 2}, format_id=FMT, version=1)
    assert st.load("settings", format_id=FMT, version=1).data == {"a": 2}


def test_payload_cannot_override_format_or_version(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert st.save("settings", {"format": "x", "version": 7, "a": 1}, format_id=FMT, version=1)
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk == {"format": FMT, "version": 1, "a": 1}


def test_subdirectory_names(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert st.save("benchmarks/run-1", {"x": 1}, format_id=FMT, version=1)
    assert (tmp_path / "benchmarks" / "run-1.json").is_file()
    assert st.load("benchmarks/run-1", format_id=FMT, version=1).data == {"x": 1}


@pytest.mark.parametrize("name", ["", "../escape", "/abs", "a/../../b", "a/./b", "a//b", "a\\b"])
def test_unsafe_names_are_rejected(tmp_path: Path, name: str) -> None:
    st = JsonStore(tmp_path)
    with pytest.raises(ValueError):
        st.save(name, {}, format_id=FMT, version=1)
    with pytest.raises(ValueError):
        st.load(name, format_id=FMT, version=1)


def test_missing_file_status(tmp_path: Path) -> None:
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=1)
    assert res.status == "missing"
    assert res.data is None
    assert res.backup_path is None


def test_missing_root_directory_is_missing_status(tmp_path: Path) -> None:
    res = JsonStore(tmp_path / "nope").load("settings", format_id=FMT, version=1)
    assert res.status == "missing"


def test_corrupt_file_is_backed_up(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_bytes(b"\x00\xff{not json")
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=1)
    assert res.status == "corrupt"
    assert res.data is None
    assert res.backup_path is not None
    assert res.backup_path.parent == tmp_path
    assert res.backup_path.match("settings.corrupt-*.json")
    assert res.backup_path.read_bytes() == b"\x00\xff{not json"
    assert not target.exists()


def test_backup_name_has_utc_timestamp(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("[]", encoding="utf-8")
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=1)
    assert res.backup_path is not None
    stamp = res.backup_path.name.removeprefix("settings.corrupt-").removesuffix(".json")
    assert len(stamp) == 16 and stamp[8] == "T" and stamp.endswith("Z")


def test_two_corrupt_backups_in_same_second_do_not_clash(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    target = tmp_path / "settings.json"
    target.write_text("first", encoding="utf-8")
    first = st.load("settings", format_id=FMT, version=1).backup_path
    target.write_text("second", encoding="utf-8")
    second = st.load("settings", format_id=FMT, version=1).backup_path
    assert first is not None and second is not None and first != second
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


def test_corrupt_backup_in_subdirectory(tmp_path: Path) -> None:
    _write(tmp_path / "benchmarks" / "r.json", "nope")
    res = JsonStore(tmp_path).load("benchmarks/r", format_id=FMT, version=1)
    assert res.status == "corrupt"
    assert res.backup_path is not None
    assert res.backup_path.parent == tmp_path / "benchmarks"
    assert res.backup_path.match("r.corrupt-*.json")


def test_wrong_format_id_is_corrupt(tmp_path: Path) -> None:
    _write(tmp_path / "settings.json", {"format": "alexvolkihar-sokoban/progress", "version": 1})
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=1)
    assert res.status == "corrupt"
    assert res.backup_path is not None


@pytest.mark.parametrize(
    "content",
    [
        [1, 2],
        {"version": 1},
        {"format": FMT},
        {"format": FMT, "version": "1"},
        {"format": FMT, "version": True},
        {"format": FMT, "version": 0},
        {"format": FMT, "version": 1.0},
    ],
)
def test_bad_envelope_is_corrupt(tmp_path: Path, content: object) -> None:
    _write(tmp_path / "settings.json", content)
    assert JsonStore(tmp_path).load("settings", format_id=FMT, version=1).status == "corrupt"


def test_utf8_bom_is_accepted(tmp_path: Path) -> None:
    text = json.dumps({"format": FMT, "version": 1, "a": "é"}, ensure_ascii=False)
    (tmp_path / "settings.json").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=1)
    assert res.status == "ok"
    assert res.data == {"a": "é"}


def test_too_new_file_untouched_and_save_refused(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    _write(target, {"format": FMT, "version": 99, "future": True})
    before = target.read_bytes()
    st = JsonStore(tmp_path)
    res = st.load("settings", format_id=FMT, version=1)
    assert res.status == "too_new"
    assert res.data is None
    assert res.backup_path is None
    assert st.is_read_only("settings") is True
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1) is False
    assert target.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]


def test_save_refuses_to_clobber_too_new_file_even_without_load(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    _write(target, {"format": FMT, "version": 99})
    before = target.read_bytes()
    st = JsonStore(tmp_path)
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1) is False
    assert target.read_bytes() == before
    assert st.is_read_only("settings") is True


def test_is_read_only_false_by_default(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert st.is_read_only("settings") is False
    st.load("settings", format_id=FMT, version=1)
    assert st.is_read_only("settings") is False


def test_migration_chain_applied(tmp_path: Path) -> None:
    reg = MigrationRegistry()
    reg.register(FMT, 1, lambda d: {**d, "b": d["a"]})
    reg.register(FMT, 2, lambda d: {**d, "c": 3})
    target = tmp_path / "settings.json"
    _write(target, {"format": FMT, "version": 1, "a": 1})
    before = target.read_bytes()
    res = JsonStore(tmp_path, reg).load("settings", format_id=FMT, version=3)
    assert res.status == "migrated"
    assert res.data == {"a": 1, "b": 1, "c": 3}
    assert target.read_bytes() == before  # the next save writes the new version


def test_missing_migration_step_is_corrupt(tmp_path: Path) -> None:
    _write(tmp_path / "settings.json", {"format": FMT, "version": 1})
    res = JsonStore(tmp_path).load("settings", format_id=FMT, version=2)
    assert res.status == "corrupt"
    assert res.backup_path is not None


def test_failing_migration_is_corrupt(tmp_path: Path) -> None:
    reg = MigrationRegistry()

    def broken(d: dict[str, object]) -> dict[str, object]:
        raise KeyError("missing")

    reg.register(FMT, 1, broken)
    _write(tmp_path / "settings.json", {"format": FMT, "version": 1})
    assert JsonStore(tmp_path, reg).load("settings", format_id=FMT, version=2).status == "corrupt"


def test_unwritable_dir_save_returns_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(src: object, dst: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store_module.os, "replace", boom)
    st = JsonStore(tmp_path)
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1) is False
    assert list(tmp_path.iterdir()) == []


def test_save_failure_keeps_previous_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1)

    def boom(fd: int) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(store_module.os, "fsync", boom)
    assert st.save("settings", {"a": 2}, format_id=FMT, version=1) is False
    assert st.load("settings", format_id=FMT, version=1).data == {"a": 1}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]


def test_save_into_uncreatable_root_returns_false(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    st = JsonStore(blocker / "data")
    assert st.save("settings", {"a": 1}, format_id=FMT, version=1) is False


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="POSIX permissions, non-root")
def test_read_only_directory_save_returns_false(tmp_path: Path) -> None:
    root = tmp_path / "ro"
    root.mkdir()
    root.chmod(0o500)
    try:
        assert JsonStore(root).save("settings", {"a": 1}, format_id=FMT, version=1) is False
    finally:
        root.chmod(0o700)


def test_delete(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    st.save("session", {"a": 1}, format_id=FMT, version=1)
    st.delete("session")
    assert not (tmp_path / "session.json").exists()
    st.delete("session")  # missing file: no error


def test_delete_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    st.save("session", {"a": 1}, format_id=FMT, version=1)

    def boom(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "unlink", boom)
    st.delete("session")


def test_unreadable_file_is_corrupt_without_backup_and_not_overwritten(tmp_path: Path) -> None:
    (tmp_path / "settings.json").mkdir()  # reading a directory raises OSError on every platform
    st = JsonStore(tmp_path)
    res = st.load("settings", format_id=FMT, version=1)
    assert res.status == "corrupt"
    assert res.backup_path is None
    assert st.is_read_only("settings") is True
    assert (tmp_path / "settings.json").is_dir()
