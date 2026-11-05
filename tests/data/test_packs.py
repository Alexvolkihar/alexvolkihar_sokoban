"""Bundled level packs (spec 8) and the ``annotate`` command."""

import json
from importlib.resources import files
from pathlib import Path

import jsonschema
import pytest

from alexvolkihar_sokoban.cli import main
from alexvolkihar_sokoban.commands import annotate
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.lurd import replay
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par
from alexvolkihar_sokoban.formats import FormatError, jsonfmt, legacy
from alexvolkihar_sokoban.formats.detect import load_any
from alexvolkihar_sokoban.solver.api import SOLVER_ID, SolveLimits, SolveResult, SolveStatus

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "pack.schema.json").read_text(encoding="utf-8"))
LEGACY_LEVELS = ROOT / "legacy" / "level"
FIXTURES = ROOT / "tests" / "fixtures" / "formats"
LEVELS_DIR = files("alexvolkihar_sokoban.data") / "levels"
LAMA = "Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN, Martin PACARY"


def _raw_packs() -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for item in sorted(LEVELS_DIR.iterdir(), key=lambda i: i.name):
        if item.name.endswith(".json"):
            out[item.name] = json.loads(item.read_text(encoding="utf-8"))
    return out


RAW = _raw_packs()
PACKS = {data["id"]: jsonfmt.pack_from_dict(data) for data in RAW.values()}


def test_lama_packs_are_bundled() -> None:
    assert {"lama-original", "lama-unsolvable"} <= set(PACKS)


@pytest.mark.parametrize("name", sorted(RAW))
def test_bundled_packs_validate_against_schema(name: str) -> None:
    jsonschema.Draft202012Validator(SCHEMA).validate(RAW[name])
    assert RAW[name]["id"] == name.removesuffix(".json")


@pytest.mark.parametrize("name", sorted(RAW))
def test_bundled_packs_load_without_warnings(name: str) -> None:
    pack, warnings = load_any(Path(str(LEVELS_DIR / name)))
    assert warnings == [] and len(pack.levels) == len(RAW[name]["levels"])


def test_pack_and_level_ids_are_unique() -> None:
    assert len(PACKS) == len(RAW)
    for data in RAW.values():
        ids = [level["id"] for level in data["levels"]]
        assert len(ids) == len(set(ids)), data["id"]


def test_frozen_lama_ids() -> None:
    assert [e.id for e in PACKS["lama-original"].levels] == [f"test{i}" for i in range(1, 12)]
    assert [e.id for e in PACKS["lama-unsolvable"].levels] == ["test12", "test13", "test14"]


@pytest.mark.parametrize("pack_id", ["lama-original", "lama-unsolvable"])
def test_lama_levels_are_the_original_files(pack_id: str) -> None:
    for entry in PACKS[pack_id].levels:
        text = (LEGACY_LEVELS / f"{entry.id}.txt").read_text(encoding="utf-8")
        original = legacy.parse(text, pack_id=entry.id).levels[0].level
        assert entry.level.canonical_hash() == original.canonical_hash(), entry.id


def test_every_par_replays_to_solved() -> None:
    checked = 0
    for pack in PACKS.values():
        for entry in pack.levels:
            if entry.par is None:
                continue
            state = replay(entry.level, entry.par.lurd)
            assert state.is_solved, f"{pack.id}/{entry.id}"
            assert (state.moves, state.pushes) == (entry.par.moves, entry.par.pushes), f"{pack.id}/{entry.id}"
            checked += 1
    assert checked >= 11


def test_lama_original_has_a_par_for_every_level() -> None:
    assert all(e.par is not None and e.par.solver == SOLVER_ID for e in PACKS["lama-original"].levels)


def test_lama_unsolvable_has_no_par_and_is_hidden() -> None:
    pack = PACKS["lama-unsolvable"]
    assert pack.hidden and all(e.par is None for e in pack.levels)
    assert not PACKS["lama-original"].hidden


@pytest.mark.parametrize("pack_id", ["lama-original", "lama-unsolvable"])
def test_lama_packs_credit_the_group(pack_id: str) -> None:
    pack = PACKS[pack_id]
    assert LAMA in pack.author and "groupe LAMA" in pack.author
    assert pack.license and pack.source.startswith("https://")


def test_microban_credit() -> None:
    if "microban-1" not in PACKS:
        pytest.skip("Microban is not bundled (licence notice not found, see the pack notes)")
    pack = PACKS["microban-1"]
    assert pack.author == "David W. Skinner" and "Skinner" in pack.license
    assert pack.source.startswith(("http://", "https://"))


def test_test_performance_fixture_is_an_invalid_level() -> None:
    with pytest.raises(FormatError, match="12 boxes but 14 goals"):
        load_any(FIXTURES / "legacy_test_performance.txt")


# --- annotate -----------------------------------------------------------------------------------------

TEST1 = ["######", "#.  .#", "#    #", "# $$ #", "#@   #", "######"]
ONE_PUSH = ["#####", "#@$.#", "#####"]
STUCK = ["#####", "#$  #", "#@ .#", "#####"]  # box in a corner, off goal
LONG_PAR = Par(pushes=1, moves=3, lurd="udR", solver="by-hand")


def _pack(*entries: LevelEntry) -> Pack:
    return Pack(id="mini", title="Mini", levels=entries, author="me", license="CC0", source="here")


def _write(path: Path, pack: Pack) -> None:
    path.write_text(json.dumps(jsonfmt.pack_to_dict(pack)), encoding="utf-8")


def _read(path: Path) -> Pack:
    return jsonfmt.pack_from_dict(json.loads(path.read_text(encoding="utf-8")))


def test_annotate_pack_fills_missing_par_and_reports_each_level() -> None:
    pack = _pack(
        LevelEntry("a", Level.from_rows(TEST1)),
        LevelEntry("b", Level.from_rows(["#####", "#   #", "#@$.#", "#####"]), par=LONG_PAR),
        LevelEntry("c", Level.from_rows(STUCK)),
    )
    seen: list[tuple[str, SolveStatus]] = []
    out = annotate.annotate_pack(
        pack, SolveLimits(time_s=5), on_level=lambda e, r: seen.append((e.id, r.status))
    )
    assert seen == [("a", SolveStatus.SOLVED), ("c", SolveStatus.UNSOLVABLE)]
    a, b, c = out.levels
    assert a.par is not None and a.par.solver == SOLVER_ID and replay(a.level, a.par.lurd).is_solved
    assert (a.par.pushes, a.par.moves) == (sum(ch.isupper() for ch in a.par.lurd), len(a.par.lurd))
    assert b.par == LONG_PAR and c.par is None
    assert (out.id, out.title, out.author, out.license, out.source) == ("mini", "Mini", "me", "CC0", "here")


def test_annotate_pack_force_recomputes_but_keeps_par_when_the_solver_fails() -> None:
    pack = _pack(
        LevelEntry("b", Level.from_rows(["#####", "#   #", "#@$.#", "#####"]), par=LONG_PAR),
        LevelEntry("big", Level.from_rows(TEST1), par=Par(4, 99, "x", "old")),
    )
    out = annotate.annotate_pack(pack, SolveLimits(time_s=5), only_missing=False)
    assert out.levels[0].par is not None and out.levels[0].par.lurd == "R"
    out = annotate.annotate_pack(pack, SolveLimits(max_nodes=1), only_missing=False)
    assert out.levels[1].par == Par(4, 99, "x", "old")


def test_annotate_fills_missing_par(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "mini.json"
    _write(path, _pack(LevelEntry("a", Level.from_rows(ONE_PUSH)), LevelEntry("c", Level.from_rows(STUCK))))
    assert main(["annotate", str(path), "--time-limit", "5"]) == 0
    a, c = _read(path).levels
    assert a.par == Par(pushes=1, moves=1, lurd="R", solver=SOLVER_ID) and c.par is None
    out = capsys.readouterr().out
    assert "a: solved" in out and "c: unsolvable" in out and "1 of 2 levels have a par" in out


def test_annotate_skips_levels_with_par_unless_forced(tmp_path: Path) -> None:
    path = tmp_path / "mini.json"
    _write(path, _pack(LevelEntry("b", Level.from_rows(["#####", "#   #", "#@$.#", "#####"]), par=LONG_PAR)))
    assert main(["annotate", str(path)]) == 0
    assert _read(path).levels[0].par == LONG_PAR
    assert main(["annotate", str(path), "--force"]) == 0
    assert _read(path).levels[0].par == Par(1, 1, "R", SOLVER_ID)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"format": "alexvolkihar-sokoban/level", "version": 1, "id": "1", "rows": ONE_PUSH}),
        json.dumps(
            {
                "format": "alexvolkihar-sokoban/pack",
                "version": 1,
                "id": "p",
                "title": "",
                "levels": [{"id": "1", "rows": ONE_PUSH}, {"id": "2", "rows": ["#@#"]}],
            }
        ),
    ],
)
def test_annotate_refuses_files_it_cannot_rewrite_faithfully(
    tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "p.json"
    path.write_text(content, encoding="utf-8")
    assert main(["annotate", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == content
    assert "annotate" in capsys.readouterr().err


def test_annotate_missing_file(tmp_path: Path) -> None:
    assert main(["annotate", str(tmp_path / "none.json")]) == 2


def test_annotate_interrupted_keeps_finished_levels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "mini.json"
    _write(path, _pack(LevelEntry("a", Level.from_rows(ONE_PUSH)), LevelEntry("b", Level.from_rows(TEST1))))
    real_solve = annotate.solve
    calls = 0

    def fake_solve(level: Level, **kwargs: object) -> SolveResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return real_solve(level, **kwargs)

    monkeypatch.setattr(annotate, "solve", fake_solve)
    assert main(["annotate", str(path)]) == 130
    a, b = _read(path).levels
    assert a.par == Par(1, 1, "R", SOLVER_ID) and b.par is None
