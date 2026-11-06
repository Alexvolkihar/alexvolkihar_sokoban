import json
import locale
from pathlib import Path

import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.persistence.session import SavedSession
from alexvolkihar_sokoban.persistence.settings import SETTINGS_FORMAT, Settings
from alexvolkihar_sokoban.scoring.records import LastPlayed, Progress
from alexvolkihar_sokoban.ui.context import FIRST_PACKS, AppContext, load_bundled_packs
from alexvolkihar_sokoban.ui.i18n import get_language, set_language

ROWS_A = ["#####", "#@$.#", "#####"]
ROWS_B = ["######", "#@ $.#", "######"]
XSB_A = "\n".join(ROWS_A) + "\n"
XSB_B = "\n".join(ROWS_B) + "\n"
INVALID_XSB = "#####\n#@$ #\n#####\n"  # one box, no goal


@pytest.fixture(autouse=True)
def _restore_language():
    before = get_language()
    yield
    set_language(before)


def entry(level_id: str, rows: list[str] = ROWS_A, **kw: object) -> LevelEntry:
    return LevelEntry(level_id, Level.from_rows(rows), **kw)  # type: ignore[arg-type]


def pack(pack_id: str, *, hidden: bool = False, n: int = 1) -> Pack:
    return Pack(pack_id, pack_id.title(), tuple(entry(str(i + 1)) for i in range(n)), hidden=hidden)


def load(tmp_path: Path, bundled: list[Pack] | None = None) -> AppContext:
    return AppContext.load(tmp_path, bundled=[] if bundled is None else bundled)


def write_file(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# -- loading ---------------------------------------------------------------------------------------------


def test_load_on_empty_dir_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("en_US", "UTF-8"))
    ctx = load(tmp_path)
    assert ctx.data_dir == tmp_path and ctx.store.root == tmp_path
    assert ctx.settings == Settings()
    assert ctx.progress == Progress()
    assert ctx.session is None
    assert ctx.warnings == []
    assert [p.id for p in ctx.packs] == ["generated", "custom"]
    assert ctx.pack("generated").levels == () and ctx.pack("custom").levels == ()
    assert ctx.hidden_packs == []
    assert (tmp_path / "levels").is_dir()  # ready for drop-in files


def test_first_run_language_follows_the_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("fr_FR", "UTF-8"))
    ctx = load(tmp_path)
    assert ctx.settings.language == "fr"
    assert get_language() == "fr"


def test_unknown_locale_gives_english(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*a: object) -> tuple[str | None, str | None]:
        raise ValueError("unknown locale")

    monkeypatch.setattr(locale, "getlocale", broken)
    assert load(tmp_path).settings.language == "en"


def test_saved_settings_win_over_the_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("fr_FR", "UTF-8"))
    write_file(
        tmp_path / "settings.json",
        {"format": SETTINGS_FORMAT, "version": 1, "language": "en", "theme": "neon"},
    )
    ctx = load(tmp_path)
    assert ctx.settings.language == "en" and ctx.settings.theme == "neon"
    assert get_language() == "en"


def test_corrupt_settings_warns_and_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("en_US", "UTF-8"))
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    ctx = load(tmp_path)
    assert ctx.settings == Settings()
    assert len(ctx.warnings) == 1 and "settings" in ctx.warnings[0]
    backups = list(tmp_path.glob("settings.corrupt-*.json"))
    assert len(backups) == 1 and backups[0].name in ctx.warnings[0]
    assert not (tmp_path / "settings.json").exists()


def test_too_new_progress_warns_and_is_never_overwritten(tmp_path: Path) -> None:
    newer = {"format": "alexvolkihar-sokoban/progress", "version": 99, "levels": {}}
    write_file(tmp_path / "progress.json", newer)
    ctx = load(tmp_path)
    assert ctx.progress == Progress()
    assert len(ctx.warnings) == 1 and "progress" in ctx.warnings[0]
    assert ctx.save_progress() is False
    assert json.loads((tmp_path / "progress.json").read_text(encoding="utf-8")) == newer


def test_warnings_follow_the_saved_language(tmp_path: Path) -> None:
    write_file(tmp_path / "settings.json", {"format": SETTINGS_FORMAT, "version": 1, "language": "fr"})
    (tmp_path / "progress.json").write_text("garbage", encoding="utf-8")
    ctx = load(tmp_path)
    assert len(ctx.warnings) == 1 and "progression" in ctx.warnings[0]


def test_pop_warnings_empties_the_list(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text("garbage", encoding="utf-8")
    ctx = load(tmp_path)
    first = ctx.pop_warnings()
    assert len(first) == 1 and ctx.warnings == [] and ctx.pop_warnings() == []


# -- packs -----------------------------------------------------------------------------------------------


def test_visible_pack_order_and_hidden_packs(tmp_path: Path) -> None:
    bundled = [
        pack("zeta"),
        pack("boxoban-hard"),
        pack("bench-hidden", hidden=True),
        pack("alpha"),
        pack("first-steps"),
    ]
    ctx = load(tmp_path, bundled)
    assert FIRST_PACKS == ("first-steps",)  # only the bundled starter pack jumps the queue
    assert [p.id for p in ctx.packs] == [
        "first-steps",
        "alpha",
        "boxoban-hard",
        "zeta",
        "generated",
        "custom",
    ]
    assert [p.id for p in ctx.hidden_packs] == ["bench-hidden"]
    assert [p.id for p in ctx.all_packs()] == [p.id for p in ctx.packs] + ["bench-hidden"]
    assert ctx.pack("bench-hidden").hidden
    with pytest.raises(KeyError):
        ctx.pack("nope")


def test_load_bundled_packs_reads_json_and_reports_broken_files(tmp_path: Path) -> None:
    good = {
        "format": "alexvolkihar-sokoban/pack",
        "version": 1,
        "id": "good",
        "title": "Good",
        "levels": [{"id": "1", "rows": ROWS_A}, {"id": "2", "rows": ["#"]}],
    }
    write_file(tmp_path / "good.json", good)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "README.txt").write_text("not a pack", encoding="utf-8")
    packs, warnings = load_bundled_packs(tmp_path)
    assert [p.id for p in packs] == ["good"] and [e.id for e in packs[0].levels] == ["1"]
    assert len(warnings) == 2
    assert any("broken.json" in w for w in warnings)


def test_the_package_data_loads_without_warnings() -> None:
    packs, warnings = load_bundled_packs()
    assert warnings == []
    assert len({p.id for p in packs}) == len(packs)


def test_custom_levels_dir_tolerates_broken_files(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    (levels / "binary.xsb").write_bytes(b"\x00\x01\x02\xff")
    (levels / "invalid.txt").write_text(INVALID_XSB, encoding="utf-8")
    (levels / "mixed.sok").write_text(XSB_A + "\n" + INVALID_XSB, encoding="utf-8")
    (levels / "notes.md").write_text(XSB_B, encoding="utf-8")  # not a level extension: ignored
    ctx = load(tmp_path)
    custom = ctx.pack("custom")
    assert [e.id for e in custom.levels] == ["mixed/1"]
    assert len(ctx.warnings) == 3  # binary file, invalid file, invalid level inside mixed.sok
    assert any("binary.xsb" in w for w in ctx.warnings)
    assert not any(str(levels) in w for w in ctx.warnings)  # file names only, the folder is known
    assert any("invalid.txt" in w for w in ctx.warnings)
    assert any("mixed" in w for w in ctx.warnings)


def test_custom_pack_merges_files_in_name_order(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    (levels / "b.XSB").write_text(XSB_B, encoding="utf-8")
    (levels / "a.xsb").write_text(XSB_A + "\n" + XSB_B, encoding="utf-8")
    write_file(
        levels / "c.json", {"format": "alexvolkihar-sokoban/level", "version": 1, "id": "x", "rows": ROWS_A}
    )
    ctx = load(tmp_path)
    assert [e.id for e in ctx.pack("custom").levels] == ["a/1", "a/2", "b/1", "c/x"]
    assert ctx.warnings == []


def test_custom_files_with_the_same_stem_do_not_clash(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    (levels / "same.sok").write_text(XSB_A, encoding="utf-8")
    (levels / "same.xsb").write_text(XSB_B, encoding="utf-8")
    ctx = load(tmp_path)
    assert [e.id for e in ctx.pack("custom").levels] == ["same/1"]
    assert len(ctx.warnings) == 1 and "same.xsb" in ctx.warnings[0]


def test_reload_custom_picks_up_new_files(tmp_path: Path) -> None:
    ctx = load(tmp_path)
    (tmp_path / "levels" / "new.xsb").write_text(XSB_A, encoding="utf-8")
    ctx.reload_custom()
    assert [e.id for e in ctx.pack("custom").levels] == ["new/1"]
    assert [p.id for p in ctx.packs][-1] == "custom"


def test_generated_level_persisted(tmp_path: Path) -> None:
    ctx = load(tmp_path)
    par = Par(pushes=1, moves=1, lurd="R", solver="push-astar/1")
    first = entry("easy-1", ROWS_A, par=par, seed=1)
    updated = ctx.add_generated_level(first)
    assert updated.id == "generated" and [e.id for e in updated.levels] == ["easy-1"]
    assert ctx.pack("generated") is updated
    ctx.add_generated_level(entry("easy-2", ROWS_B, seed=2))
    ctx.add_generated_level(entry("easy-1", ROWS_A, par=par, seed=1))  # same id again: replaced, not doubled

    again = load(tmp_path)
    gen = again.pack("generated")
    assert [e.id for e in gen.levels] == ["easy-1", "easy-2"]
    assert gen.levels[0].par == par and gen.levels[0].seed == 1
    assert gen.levels[0].level.canonical_hash() == first.level.canonical_hash()
    assert again.warnings == []


# -- saving ----------------------------------------------------------------------------------------------


def session(**kw: object) -> SavedSession:
    fields: dict[str, object] = {
        "pack_id": "custom",
        "level_id": "a/1",
        "level_hash": Level.from_rows(ROWS_A).canonical_hash(),
        "lurd": "",
        "redo_lurd": "",
        "elapsed_ms": 1200,
        "assisted": False,
        "saved_at": "2026-11-05T14:03:22Z",
    }
    fields.update(kw)
    return SavedSession(**fields)  # type: ignore[arg-type]


def test_settings_progress_and_session_roundtrip(tmp_path: Path) -> None:
    ctx = load(tmp_path)
    ctx.settings.theme = "neon"
    ctx.progress.set_last_played(LastPlayed("custom", "a/1", Level.from_rows(ROWS_A).canonical_hash()))
    s = session()
    assert ctx.save_settings() and ctx.save_progress() and ctx.save_session(s)
    assert ctx.session == s

    again = load(tmp_path)
    assert again.settings.theme == "neon"
    assert again.progress == ctx.progress
    assert again.session == s

    assert again.save_session(None) is True
    assert again.session is None and not (tmp_path / "session.json").exists()
    assert load(tmp_path).session is None


def test_invalid_session_is_ignored_with_a_warning(tmp_path: Path) -> None:
    payload = {"format": "alexvolkihar-sokoban/session", "version": 1, "pack_id": "x"}
    write_file(tmp_path / "session.json", payload)
    ctx = load(tmp_path)
    assert ctx.session is None and len(ctx.warnings) == 1


def test_failed_save_returns_false_and_warns_once(tmp_path: Path) -> None:
    ctx = load(tmp_path)
    (tmp_path / "settings.json").mkdir()  # a directory where the file should go: os.replace fails
    assert ctx.save_settings() is False
    assert ctx.save_settings() is False
    assert len(ctx.warnings) == 1 and "settings" in ctx.warnings[0]


def test_continue_target_prefers_the_session(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    (levels / "a.xsb").write_text(XSB_A + "\n" + XSB_B, encoding="utf-8")
    ctx = load(tmp_path)
    assert ctx.continue_target() is None
    hash_b = Level.from_rows(ROWS_B).canonical_hash()
    ctx.progress.set_last_played(LastPlayed("custom", "a/2", hash_b))
    target = ctx.continue_target()
    assert target is not None and (target.pack.id, target.level_id, target.session) == ("custom", "a/2", None)
    s = session()
    ctx.session = s
    target = ctx.continue_target()
    assert target is not None and (target.pack.id, target.level_id, target.session) == ("custom", "a/1", s)


def test_continue_target_finds_a_moved_level_by_hash(tmp_path: Path) -> None:
    ctx = load(tmp_path, [pack("first-steps", n=1)])
    ctx.progress.set_last_played(LastPlayed("old-pack", "old-id", Level.from_rows(ROWS_A).canonical_hash()))
    target = ctx.continue_target()
    assert target is not None and (target.pack.id, target.level_id) == ("first-steps", "1")


def test_continue_target_skips_a_session_whose_level_is_gone(tmp_path: Path) -> None:
    ctx = load(tmp_path, [pack("first-steps", n=1)])
    ctx.session = session(level_hash="sha256:" + "0" * 64)
    assert ctx.continue_target() is None
    ctx.progress.set_last_played(LastPlayed("first-steps", "1", Level.from_rows(ROWS_A).canonical_hash()))
    target = ctx.continue_target()
    assert target is not None and target.session is None and target.level_id == "1"
