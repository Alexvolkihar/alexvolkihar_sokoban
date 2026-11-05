# alexvolkihar_sokoban Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking. Tasks inside one **parallel group** touch disjoint files and may run at the same time in separate
> agents (one git worktree or branch per agent, merged back to `main` when the group is done).

**Goal:** Turn the Sokoban-LAMA student prototype into a finished, tested pygame-ce game with menus, level
packs, a bounded push-based solver, benchmark mode, themes, saves and scores, using portable JSON formats
for a later Godot port.

**Architecture:** `src/alexvolkihar_sokoban/` package. Pure, pygame-free layers (`core`, `formats`,
`solver`, `scoring`, `persistence`, `benchmark`, `generator`) under TDD; `ui/` is the only pygame layer,
made of scenes loaded by name. Cross-task contracts are frozen in Phase 1 (Task 3) so Phase 2 agents can
work in parallel.

**Tech Stack:** Python ≥ 3.11, pygame-ce ≥ 2.5, platformdirs ≥ 4, pytest, ruff, mypy, jsonschema, hatchling;
optional `media` extra: imageio + imageio-ffmpeg.

**Spec:** `docs/superpowers/specs/2026-11-05-alexvolkihar-sokoban-design.md` (read it with this plan; section
numbers below such as "spec 7.4" refer to it).

## Global Constraints

- Python `>=3.11`; CI tests on 3.11, 3.12, 3.13, 3.14 (Ubuntu) and 3.13 (Windows, macOS).
- Runtime dependencies: `pygame-ce>=2.5`, `platformdirs>=4` — nothing else.
- Only `alexvolkihar_sokoban.ui.*` may import `pygame` (Ruff banned-api + `tests/test_layering.py`).
- Coordinates are `(row, col)`, row 0 at the top. Never transpose.
- JSON files: top-level `"format": "alexvolkihar-sokoban/<kind>"`, integer `"version": 1`; durations integer
  ms, sizes integer bytes, timestamps ISO-8601 UTC (`2026-11-05T14:03:22Z`).
- Level identity in saves = `Level.canonical_hash()` = `"sha256:<hex>"` (spec 7.2).
- Package `alexvolkihar_sokoban`, command `alexvolkihar-sokoban`, data dir name `alexvolkihar-sokoban`,
  env override `ALEXVOLKIHAR_SOKOBAN_HOME`, window title `Alexvolkihar Sokoban`.
- UI strings only through `t(en, fr)` from `ui/i18n.py`; no shared string catalogue.
- Credit "Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN, Martin PACARY (groupe LAMA)" wherever the project
  presents itself (README FR/EN, credits scene, pack `lama-original`, `pyproject.toml` authors).
- **No AI attribution anywhere**: no `Co-Authored-By` trailer, no "Generated with" line, no assistant name
  in code, docs or commits. Commit with the repository's configured identity; never override `user.email`.
- No new asset or level without a recorded licence allowing redistribution.
- Every task ends green on: `ruff check . && ruff format --check . && mypy && pytest -q`.

## Review Focus

1. `.xsb`/`.sok`/legacy files with CRLF line endings, a UTF-8 BOM, tabs or trailing spaces must load exactly
   like clean files → test in Task 4.
2. A broken file dropped in `<data dir>/levels/` (binary, invalid level, a `.sok` mixing valid and invalid
   levels) must never crash the game: valid levels load, the rest becomes a warning → test in Task 11.
3. An unwritable data directory (read-only, disk full) must not crash the game: saving returns `False`, a
   warning is shown, play continues → test in Task 6.
4. A huge custom level (60×60) in the minimum 640×480 window, and window resizes mid-game, must render
   without exception (tile size floor 4 px) → tests in Task 9 and Task 13.
5. A hint result that arrives after the player moved again must be discarded, never drawn on the wrong
   position → test in Task 18.

---

## Dispatch map

| Phase | Group | Tasks (run together) | Starts after |
|---|---|---|---|
| 1 | sequential | 1 → 2 → 3 | — |
| 2 | **A** (parallel ×6) | 4 formats · 5 solver · 6 persistence · 7 scoring · 8 themes · 9 UI shell | Task 3 |
| 2 | sequential | 10 app context + `play` command | group A |
| 2 | **B** (parallel ×6) | 11 level packs · 12 benchmark core · 13 game scene · 14 level select · 15 settings/themes/keys scenes · 16 generator | Task 10 |
| 2 | **C** (parallel ×4) | 17 credits scene · 18 hint + solver replay · 19 benchmark scene · 20 random-level scene | group B |
| 3 | **D** (parallel ×3) | 21 formats doc + changelog · 22 media capture · 23 packaging + release check | group C |
| 3 | sequential | 24 README FR/EN with media → 25 licence (blocked on the group's consent) → 26 final review | group D |
| 4 | follow-up | Godot remake (not planned here, spec 14) | — |

File ownership is exclusive inside a group. If an agent needs a change in a file owned by another task of
the same group, it stops and reports instead of editing it.

Test command used everywhere: `pytest -q` (UI tests run headless: `tests/conftest.py` sets
`SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`).

---

## Phase 1 — foundation (sequential)

### Task 1: Scaffold, tooling and CI

**Files:**
- Move (git mv): `main.py sokoban.py aStar.py PriorityQueue.py README.md README.txt level/ img/` → `legacy/`
- Create: `pyproject.toml`, `README.md`, `README.en.md` (short stubs), `src/alexvolkihar_sokoban/__init__.py`,
  `__main__.py`, `cli.py`, `commands/{__init__,play,solve,convert,annotate,bench,generate}.py`,
  empty `__init__.py` in `core formats solver generator scoring persistence benchmark ui ui/themes ui/scenes`
- Create: `src/alexvolkihar_sokoban/data/themes/kenney/` (copy of the 6 PNGs from `legacy/img/`) +
  `LICENSE.txt`, `data/levels/.gitkeep`, `data/benchmarks/.gitkeep`
- Create: `tests/conftest.py`, `tests/test_smoke.py`, `tests/test_layering.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `alexvolkihar_sokoban.__version__ = "0.1.0"`; `cli.main(argv: list[str] | None = None) -> int`;
  each `commands/<name>.py` exposes `add_arguments(parser: argparse.ArgumentParser) -> None` and
  `run(args: argparse.Namespace) -> int` (stubs print `not implemented yet` to stderr and return 2).
  Global options `--data-dir PATH`, `--version`. No subcommand → `commands.play.run` with `path=None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_smoke.py
def test_version_flag(capsys):
    from alexvolkihar_sokoban.cli import main
    with pytest.raises(SystemExit) as e: main(["--version"])
    assert e.value.code == 0 and "0.1.0" in capsys.readouterr().out

def test_all_subcommands_registered():
    from alexvolkihar_sokoban.cli import build_parser
    sub = {"play", "solve", "convert", "annotate", "bench", "generate"}
    assert sub <= set(build_parser()._subparsers._group_actions[0].choices)

# tests/test_layering.py
NON_UI = ["core", "formats", "solver", "scoring", "persistence", "benchmark", "generator"]
def test_non_ui_packages_import_without_pygame(monkeypatch):
    # put None in sys.modules["pygame"], drop cached alexvolkihar_sokoban.* modules,
    # import every module under each NON_UI package with pkgutil.walk_packages → no ImportError
```

- [ ] **Step 2: Run** `pip install -e '.[dev]'` then `pytest -q` → FAIL (package missing).
- [ ] **Step 3: Implement.** `pyproject.toml`: hatchling, `requires-python = ">=3.11"`, dependencies
  `pygame-ce>=2.5`, `platformdirs>=4`; extras `dev = [pytest, pytest-cov, ruff, mypy, jsonschema]`,
  `media = [imageio, imageio-ffmpeg]`; script `alexvolkihar-sokoban = "alexvolkihar_sokoban.cli:main"`;
  authors = the four LAMA members; package data includes `data/**`. Ruff: line length 110, rules
  `E F W I UP B SIM TID`, `[tool.ruff.lint.flake8-tidy-imports.banned-api] "pygame".msg = "pygame only in ui/"`,
  per-file-ignores `src/alexvolkihar_sokoban/ui/** = ["TID251"]`, `tests/ui/** = ["TID251"]`,
  `scripts/** = ["TID251"]`; exclude `legacy/`. mypy: `strict = true` for the seven non-UI packages,
  `ignore_missing_imports` for pygame, `files = src`. pytest: `testpaths = ["tests"]`.
  `tests/conftest.py` sets `os.environ.setdefault("SDL_VIDEODRIVER", "dummy")` and the audio one.
  `LICENSE.txt` for Kenney: "Sokoban pack by Kenney (www.kenney.nl), CC0 1.0 Universal".
  CI: job `lint` (3.13: ruff check, ruff format --check, mypy) and job `test` (matrix from Global
  Constraints, `pip install -e '.[dev]'`, `pytest -q --cov=alexvolkihar_sokoban`).
  README stubs: one paragraph + credit to the LAMA group + "licence pending".
- [ ] **Step 4: Run** `ruff check . && ruff format --check . && mypy && pytest -q` → PASS;
  `cd legacy && python main.py play level/test1.txt` still opens the original game (manual, optional).
- [ ] **Step 5: Commit** `git commit -m "Restructure into the alexvolkihar_sokoban package with tooling and CI"`

### Task 2: Core rules (`core/`)

**Files:**
- Create: `src/alexvolkihar_sokoban/core/{geometry,level,state,lurd}.py`
- Create: `tests/core/{test_geometry,test_level,test_state,test_lurd,test_vectors}.py`,
  `tests/vectors/moves.json`, `tests/vectors/hash.json`

**Interfaces:**
- Produces (`core.geometry`): `Pos = tuple[int, int]`; `class Direction(Enum)` members `UP=(-1,0)`,
  `DOWN=(1,0)`, `LEFT=(0,-1)`, `RIGHT=(0,1)` with properties `dr`, `dc`, `char` (`"u" "d" "l" "r"`) and
  `@classmethod from_char(c: str) -> Direction` (case-insensitive); `def step(pos: Pos, d: Direction) -> Pos`.
- Produces (`core.level`): `class InvalidLevelError(ValueError)`;
  `@dataclass(frozen=True) class Level` with `width: int, height: int, walls: frozenset[Pos],
  goals: frozenset[Pos], boxes: frozenset[Pos], player: Pos, floor: frozenset[Pos], title: str = "",
  author: str = "", comment: str = ""`; `Level.from_rows(rows: Sequence[str], *, title="", author="",
  comment="") -> Level`; `Level.to_rows(boxes: frozenset[Pos] | None = None, player: Pos | None = None)
  -> tuple[str, ...]`; `Level.canonical_hash() -> str`; `Level.is_wall(pos: Pos) -> bool`;
  `Level.is_floor(pos: Pos) -> bool`.
- Produces (`core.state`): `class MoveOutcome(Enum): MOVED, PUSHED, BLOCKED`;
  `@dataclass(frozen=True) class Step: direction: Direction; pushed: bool`;
  `class GameState(level: Level)` with attributes `level`, `player: Pos`, `boxes: frozenset[Pos]`,
  properties `moves: int`, `pushes: int`, `is_solved: bool`, `history: tuple[Step, ...]`,
  `can_undo: bool`, `can_redo: bool`, `lurd: str`, `redo_lurd: str` (next redo first); methods
  `move(d: Direction) -> MoveOutcome`, `undo() -> Step | None`, `redo() -> Step | None`,
  `restart() -> None`, `signature() -> tuple[Pos, frozenset[Pos]]`.
- Produces (`core.lurd`): `class LurdError(ValueError)`; `step_char(step: Step) -> str`;
  `encode(steps: Iterable[Step]) -> str`; `replay(level: Level, text: str, *, strict_case: bool = True)
  -> GameState`; `restore(level: Level, lurd: str, redo_lurd: str) -> GameState`.

- [ ] **Step 1: Write the failing tests** (rows in XSB; `TEST1 = ["######","#.  .#","#    #","# $$ #","#@   #","######"]`)

```python
def test_from_rows_reads_walls_goals_boxes_player():
    lv = Level.from_rows(TEST1)
    assert lv.player == (4, 1) and lv.boxes == {(3, 2), (3, 3)} and lv.goals == {(1, 1), (1, 4)}
    assert (0, 0) in lv.walls and lv.width == 6 and lv.height == 6

def test_plus_and_star_mean_player_and_box_on_goal():
    lv = Level.from_rows(["######", "#+*$ #", "#   .#", "######"])
    assert lv.player == (1, 1) and (1, 1) in lv.goals and (1, 2) in lv.boxes & lv.goals
@pytest.mark.parametrize("rows,reason", [
    (["#####", "#@$ #", "#####"], "goals"),          # 1 box, 0 goals
    (["#####", "# $.#", "#####"], "player"),         # no player
    (["#####", "#@@$.", "#####"], "player"),         # two players
    (["@$.", "###"], "enclosed"),                    # player walks off the grid
    (["####", "#@*#", "####"], "solved"),            # already solved at start
])
def test_invalid_levels(rows, reason):
    with pytest.raises(InvalidLevelError, match=reason): Level.from_rows(rows)

def test_floor_excludes_cells_outside_the_walls():  # leading spaces of a row are not floor

def test_canonical_hash_ignores_trailing_spaces_and_dash_floor():
    a = Level.from_rows(["#####", "#@$.#", "#####"]); b = Level.from_rows(["#####  ", "#@$.#", "#####", ""])
    c = Level.from_rows(["#####", "#@$.#", "#####"]); d = Level.from_rows(["#####", "#@$.#-", "#####"])
    assert a.canonical_hash() == b.canonical_hash() == d.canonical_hash()
    assert a.canonical_hash().startswith("sha256:") and len(a.canonical_hash()) == 7 + 64

def test_push_moves_box_and_counts():
    s = GameState(Level.from_rows(TEST1)); assert s.move(Direction.RIGHT) is MoveOutcome.MOVED
    assert s.move(Direction.UP) is MoveOutcome.PUSHED and s.boxes == {(2, 2), (3, 3)}
    assert (s.moves, s.pushes) == (2, 1)

def test_blocked_by_wall_or_double_box_changes_nothing():  # outcome BLOCKED, moves unchanged
def test_undo_redo_roundtrip_and_new_move_clears_redo():
def test_restart_clears_history_and_redo():
def test_is_solved_when_every_box_on_goal():
def test_lurd_encode_and_replay():
    s = replay(Level.from_rows(TEST1), "rU"); assert s.lurd == "rU" and s.pushes == 1
def test_replay_rejects_case_mismatch():  # "ru" (u would push) → LurdError; strict_case=False accepts it
def test_restore_rebuilds_redo_stack():
    s = restore(lv, "rU", "Dl"); assert s.lurd == "rU" and s.redo_lurd == "Dl"; s.redo(); assert s.lurd == "rUD"
def test_conformance_vectors():  # load tests/vectors/moves.json and hash.json, assert every case
```

`tests/vectors/moves.json`: ≥ 8 cases (walk, push, push onto goal, push off goal, blocked by wall, blocked by
two boxes, win, input with blocked steps) — each `{"name", "rows", "input", "expected": {"player": [r, c],
"boxes": [[r, c], ...] (sorted), "moves", "pushes", "solved", "blocked_steps"}}`; `input` is plain
`udlr` keys (blocked steps are skipped and counted). `hash.json`: ≥ 3 `{"rows", "hash"}` cases computed once
by the implementation and checked by hand against `sha256sum` of the canonical text.

- [ ] **Step 2: Run** `pytest tests/core -q` → FAIL (modules missing).
- [ ] **Step 3: Implement** the four modules. Validation order and messages: player count → `"player"`,
  boxes vs goals count → `"goals"` (message `"N boxes but M goals"`), at least one box, flood fill from the
  player through non-wall cells leaving the grid → `"enclosed"`, any box or goal not on floor → `"floor"`,
  all boxes on goals → `"already solved"`. Canonical text = `to_rows()` of the initial state with each row
  right-stripped, leading/trailing empty rows dropped, joined by `\n`; hash = `sha256` of UTF-8.
- [ ] **Step 4: Run** `pytest tests/core -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add the engine-agnostic core rules with conformance vectors"`

### Task 3: Frozen cross-task contracts

**Files:**
- Create: `src/alexvolkihar_sokoban/core/pack.py`, `solver/api.py`, `solver/search.py` (stub),
  `persistence/settings.py`, `ui/themes/base.py`, `ui/themes/fallback.py`, `ui/themes/registry.py` (stub)
- Create: `tests/core/test_pack.py`, `tests/solver/test_api.py`, `tests/persistence/test_settings.py`,
  `tests/ui/test_theme_contract.py`

**Interfaces:**
- Produces (`core.pack`): `@dataclass(frozen=True) class Par: pushes: int; moves: int; lurd: str;
  solver: str`; `@dataclass(frozen=True) class LevelEntry: id: str; level: Level; par: Par | None = None;
  seed: int | None = None` with property `title -> str` (level title or `id`);
  `@dataclass(frozen=True) class Pack: id: str; title: str; levels: tuple[LevelEntry, ...]; author: str = "";
  license: str = ""; source: str = ""; hidden: bool = False` with `entry(level_id: str) -> LevelEntry`
  (KeyError), `index_of(level_id: str) -> int`, `next_id(level_id: str) -> str | None`.
- Produces (`solver.api`): `class SolveStatus(StrEnum)`: `SOLVED="solved"`, `UNSOLVABLE="unsolvable"`,
  `LIMIT_TIME="limit_time"`, `LIMIT_NODES="limit_nodes"`, `CANCELLED="cancelled"`, `INVALID="invalid"`;
  `@dataclass(frozen=True) class SolveLimits: time_s: float = 10.0; max_nodes: int = 1_000_000`;
  `@dataclass(frozen=True) class SolveResult: status: SolveStatus; lurd: str | None; pushes: int | None;
  moves: int | None; nodes_expanded: int; nodes_generated: int; elapsed_ms: int`;
  `SOLVER_ID = "push-astar/1"`; `Mode = Literal["optimal", "fast"]`;
  `ProgressCallback = Callable[[int, int], None]` (nodes_expanded, elapsed_ms);
  `solve(level: Level, *, boxes: frozenset[Pos] | None = None, player: Pos | None = None,
  limits: SolveLimits = SolveLimits(), mode: Mode = "optimal", should_stop: Callable[[], bool] | None = None,
  on_progress: ProgressCallback | None = None) -> SolveResult` — validates (`INVALID` when box count ≠ goal
  count or a box/player is off-floor), then delegates to
  `solver.search.run_search(level, boxes, player, limits, mode, should_stop, on_progress) -> SolveResult`
  (stub raises `NotImplementedError`; Task 5 owns `search.py`).
- Produces (`persistence.settings`): `Language = Literal["fr", "en"]`;
  `Animation = Literal["off", "normal", "fast"]`; `ACTIONS: tuple[str, ...] = ("up", "down", "left", "right",
  "undo", "redo", "restart", "hint", "pause", "confirm", "back")`;
  `DEFAULT_KEYBINDINGS: Mapping[str, tuple[str, ...]]` = up `("key:up", "scan:26")`, down
  `("key:down", "scan:22")`, left `("key:left", "scan:4")`, right `("key:right", "scan:7")`, undo
  `("key:u", "key:backspace", "ctrl+key:z")`, redo `("key:y", "ctrl+key:y")`, restart `("key:r",)`, hint
  `("key:h",)`, pause `("key:escape", "key:p")`, confirm `("key:return", "key:space")`, back `("key:escape",)`;
  `@dataclass class Settings: language: Language = "en"; theme: str = "kenney"; fullscreen: bool = False;
  window: tuple[int, int] = (1024, 768); animation: Animation = "normal"; show_timer: bool = True;
  keybindings: dict[str, tuple[str, ...]]` (default copy of `DEFAULT_KEYBINDINGS`), methods
  `to_dict() -> dict[str, object]` (without format/version) and `@classmethod from_dict(data: Mapping[str,
  object]) -> Settings` (unknown keys ignored, each invalid field falls back to its default, missing actions
  get default bindings); `default_language(locale_name: str | None) -> Language` (`"fr"` when it starts
  with `fr`); `SETTINGS_FORMAT = "alexvolkihar-sokoban/settings"`, `SETTINGS_VERSION = 1`.
- Produces (`ui.themes.base`): `class TileKind(Enum)`: `FLOOR, WALL, GOAL, BOX, BOX_ON_GOAL, PLAYER,
  PLAYER_ON_GOAL, OUTSIDE`; `RGB = tuple[int, int, int]`; `@dataclass(frozen=True) class UiPalette: text,
  muted, accent, panel, good, bad: RGB`; `class Theme(Protocol)`: `id: str`, `name: str`, `background: RGB`,
  `palette: UiPalette`, `tile(kind: TileKind, size: int) -> pygame.Surface`; `class CachedTheme(ABC)`
  implementing `tile()` with a `(kind, size)` cache over abstract `_draw(kind: TileKind, size: int) ->
  pygame.Surface`.
- Produces (`ui.themes.registry`): `DEFAULT_THEME_ID = "kenney"`; `available_themes() -> list[Theme]`;
  `get_theme(theme_id: str) -> Theme` (unknown id → default; stub returns `FallbackTheme` from
  `fallback.py`, id `"fallback"`, flat colours, for every id until Task 8).

- [ ] **Step 1: Write the failing tests**

```python
def test_pack_navigation():  # entry(), index_of(), next_id() of the last level is None
def test_solve_rejects_mismatched_state():
    r = solve(LV, boxes=frozenset({(1, 1), (1, 2)})); assert r.status is SolveStatus.INVALID
def test_settings_roundtrip_and_defaults():
    s = Settings(language="fr", theme="neon"); assert Settings.from_dict(s.to_dict()) == s
    assert Settings.from_dict({"animation": "wild", "theme": 3}).animation == "normal"
    assert Settings.from_dict({"keybindings": {"up": ["key:k"]}}).keybindings["down"] == ("key:down", "scan:22")
def test_default_language():
    assert default_language("fr_FR") == "fr" and default_language(None) == "en"
def test_fallback_theme_draws_every_tile_kind():
    for k in TileKind: assert get_theme("anything").tile(k, 32).get_size() == (32, 32)
```

- [ ] **Step 2: Run** `pytest -q` → FAIL.
- [ ] **Step 3: Implement** the files above exactly as listed in Interfaces.
- [ ] **Step 4: Run** `pytest -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Freeze the shared contracts: packs, solver API, settings, themes"`

---

## Phase 2 — group A (6 agents in parallel, after Task 3)

### Task 4: Level formats (`formats/`) and `convert` command

**Files:**
- Create: `src/alexvolkihar_sokoban/formats/{xsb,legacy,jsonfmt,detect}.py`, `schemas/level.schema.json`,
  `schemas/pack.schema.json`, `tests/formats/{test_xsb,test_legacy,test_jsonfmt,test_detect,test_convert}.py`,
  `tests/fixtures/formats/*` (incl. `crlf_bom.sok`, `multi.sok`, `rle.xsb`, `legacy_test1.txt`)
- Modify: `src/alexvolkihar_sokoban/commands/convert.py`

**Interfaces:**
- Consumes: `Level.from_rows`, `Level.to_rows`, `Pack`, `LevelEntry`, `Par` (Tasks 2–3).
- Produces: `class FormatError(ValueError)` (carries `path`, `line`); `xsb.parse(text: str, *, pack_id: str,
  pack_title: str = "") -> tuple[Pack, list[str]]` (pack of valid levels + warnings for invalid ones);
  `xsb.dump(pack: Pack) -> str`; `legacy.parse(text: str, *, pack_id: str) -> Pack`;
  `jsonfmt.PACK_FORMAT = "alexvolkihar-sokoban/pack"`, `LEVEL_FORMAT = "alexvolkihar-sokoban/level"`,
  `jsonfmt.pack_from_dict(data: Mapping[str, object]) -> Pack`, `jsonfmt.pack_to_dict(pack: Pack) ->
  dict[str, object]`; `detect.load_any(path: Path, *, fmt: Literal["auto", "xsb", "legacy", "json"] =
  "auto") -> tuple[Pack, list[str]]`; `detect.save_any(pack: Pack, path: Path) -> None` (format from the
  extension: `.json`, `.xsb`/`.sok`/`.txt`).

- [ ] **Step 1: Write the failing tests** — `test_parse_multi_level_sok_with_titles` (3 levels, titles from
  `Title:` lines, ids `"1" "2" "3"`), `test_rle_and_pipe_rows` (`"4#|#@$.#|4#"` equals the expanded level),
  `test_crlf_bom_tabs_trailing_spaces_load_like_clean_file` (same `canonical_hash()`), `test_invalid_level_in
  _collection_becomes_warning`, `test_legacy_symbols` (`X`→wall, `*`→box), `test_detect_legacy_vs_xsb`,
  `test_json_pack_roundtrip_with_par`, `test_pack_json_validates_against_schema` (jsonschema Draft 2020-12),
  `test_convert_legacy_to_json_cli(tmp_path)` (`main(["convert", in, out])` returns 0 and the JSON reloads).
- [ ] **Step 2: Run** `pytest tests/formats -q` → FAIL.
- [ ] **Step 3: Implement.** Board line = only characters `#@+$*.-_ ` and digits/`|` (RLE); any other line
  ends the current level and may be metadata (`Title:`, `Author:`, `Comment:` case-insensitive) or a
  comment (`;`). Single-level files: pack id = file stem, level id `"1"`. Strip a leading BOM, normalise
  CRLF, expand tabs to spaces. Pack JSON shape exactly as spec 9.2.
- [ ] **Step 4: Run** `pytest tests/formats -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add XSB/SOK, legacy and JSON level formats with convert command"`

### Task 5: Push-based solver and `solve` command

**Files:**
- Create: `src/alexvolkihar_sokoban/solver/{reachability,distances,deadlocks,heuristics}.py`
- Modify: `src/alexvolkihar_sokoban/solver/search.py` (replace stub), `commands/solve.py`
- Create: `tests/solver/{levels.py,test_reachability,test_deadlocks,test_search,test_limits,test_cli}.py`

**Interfaces:**
- Consumes: `solver.api` (Task 3), `core` (Task 2). Must not modify `solver/api.py`.
- Produces: `run_search(...) -> SolveResult` per Task 3; `deadlocks.dead_squares(level: Level) ->
  frozenset[Pos]`; `deadlocks.is_frozen(level: Level, boxes: frozenset[Pos], moved: Pos) -> bool`;
  `reachability.reachable(level: Level, boxes: frozenset[Pos], start: Pos) -> tuple[frozenset[Pos], Pos]`
  (cells, normalised top-left cell). `solve` command prints status, pushes, moves, nodes, time and the LURD;
  exit code 0 solved, 1 unsolvable, 3 limit/cancelled.

- [ ] **Step 1: Write the failing tests.** `tests/solver/levels.py` holds the original LAMA levels as XSB rows
  (convert `legacy/level/test*.txt` by hand: `X`→`#`, `*`→`$`).

```python
@pytest.mark.parametrize("name", SOLVABLE)   # test1..test11
def test_solves_original_levels_and_solution_replays(name):
    r = solve(LEVELS[name], limits=SolveLimits(time_s=5))
    assert r.status is SolveStatus.SOLVED and replay(LEVELS[name], r.lurd).is_solved
    assert r.pushes == sum(c.isupper() for c in r.lurd) and r.moves == len(r.lurd)
@pytest.mark.parametrize("name", ["test12", "test13", "test14"])
def test_detects_unsolvable(name): assert solve(LEVELS[name], limits=SolveLimits(time_s=5)).status is SolveStatus.UNSOLVABLE
def test_push_optimal_on_known_level():  # a corridor level whose optimum is 3 pushes → r.pushes == 3
def test_node_limit_is_enforced():  # big level, SolveLimits(max_nodes=500) → LIMIT_NODES, nodes_expanded <= 500
def test_time_limit_is_enforced():  # SolveLimits(time_s=0.05) on a hard level → LIMIT_TIME, elapsed_ms < 1000
def test_should_stop_cancels():  # should_stop=lambda: True → CANCELLED
def test_solve_from_mid_game_state():  # boxes/player after "rU" on test1 → SOLVED and replay from that state wins
def test_dead_squares_include_corners_off_goal():
def test_initial_deadlock_is_unsolvable_immediately():  # nodes_expanded <= 1
def test_fast_mode_returns_valid_solution():
def test_progress_callback_called():
```

- [ ] **Step 2: Run** `pytest tests/solver -q` → FAIL (`NotImplementedError`).
- [ ] **Step 3: Implement** per spec 7.4. State key = `(boxes_bitmask, normalised_player_index)` with
  `boxes_bitmask` updated by XOR; store `parent` pointers and the push (box cell, direction) per state in a
  dict, never full paths. Priority `(g_pushes + h, g_moves)`; `fast` mode uses `(h, g_pushes)`. Heuristic:
  sum over boxes of the minimum push distance to any goal (distances by reverse pull BFS from each goal);
  minimum-cost matching is allowed if it stays admissible. Reconstruct the LURD by BFS walks between pushes.
  Check `should_stop` and limits every 1,000 expansions and before returning a limit status.
- [ ] **Step 4: Run** `pytest tests/solver -q && mypy` → PASS; `alexvolkihar-sokoban solve legacy/level/test3.txt`
  prints `solved` once Task 4 is merged (skip this check if run before).
- [ ] **Step 5: Commit** `git commit -m "Add the bounded push-based A* solver with deadlock detection"`

### Task 6: Persistence (`persistence/`)

**Files:**
- Create: `src/alexvolkihar_sokoban/persistence/{paths,store,migrations,session}.py`,
  `schemas/settings.schema.json`, `schemas/session.schema.json`,
  `tests/persistence/{test_paths,test_store,test_migrations,test_session}.py`

**Interfaces:**
- Consumes: `Settings`, `SETTINGS_FORMAT/VERSION` (Task 3).
- Produces: `paths.APP_NAME = "alexvolkihar-sokoban"`, `paths.ENV_HOME = "ALEXVOLKIHAR_SOKOBAN_HOME"`,
  `paths.data_dir(override: Path | None = None) -> Path` (override > env > platformdirs; creates the dir);
  `migrations.MigrationRegistry` with `register(format_id: str, from_version: int, fn: Callable[[dict[str,
  object]], dict[str, object]]) -> None` and `upgrade(format_id, data, from_version, to_version) -> dict`
  (raises `MigrationError` for a missing step); `store.LoadStatus = Literal["ok", "missing", "corrupt",
  "too_new", "migrated"]`; `@dataclass class LoadResult: data: dict[str, object] | None; status: LoadStatus;
  backup_path: Path | None = None`; `class JsonStore(root: Path, migrations: MigrationRegistry | None = None)`
  with `load(name: str, *, format_id: str, version: int) -> LoadResult` (returns the payload without
  `format`/`version`), `save(name: str, payload: Mapping[str, object], *, format_id: str, version: int) ->
  bool`, `delete(name: str) -> None`, `is_read_only(name: str) -> bool`; file name = `f"{name}.json"`, `name`
  may contain `/` for sub-directories (`benchmarks/<run_id>`); `session.SavedSession` frozen dataclass with
  `pack_id, level_id, level_hash, lurd, redo_lurd: str`, `elapsed_ms: int`, `assisted: bool`, `saved_at: str`,
  `to_dict()`, `from_dict()`, `SESSION_FORMAT = "alexvolkihar-sokoban/session"`, `SESSION_VERSION = 1`.

- [ ] **Step 1: Write the failing tests** — `test_data_dir_precedence(monkeypatch, tmp_path)`,
  `test_save_is_atomic_and_load_roundtrips`, `test_missing_file_status`, `test_corrupt_file_is_backed_up`
  (garbage bytes → status `"corrupt"`, `backup_path.name` matches `settings.corrupt-*.json`, original gone),
  `test_wrong_format_id_is_corrupt`, `test_too_new_file_untouched_and_save_refused` (version 99 →
  `"too_new"`, `save()` returns `False`, file bytes unchanged), `test_migration_chain_applied` (v1→v2→v3,
  status `"migrated"`), `test_unwritable_dir_save_returns_false(monkeypatch)` (patch `os.replace` to raise
  `OSError` → `False`, no exception, no `*.tmp` left behind), `test_session_roundtrip`,
  `test_settings_and_session_dicts_validate_against_schemas`.
- [ ] **Step 2: Run** `pytest tests/persistence -q` → FAIL.
- [ ] **Step 3: Implement.** Atomic write: `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)`,
  write, `flush`, `os.fsync`, `os.replace`; on `OSError` delete the temp file, log with `logging`, return
  `False`. Backup name `f"{name}.corrupt-{UTC %Y%m%dT%H%M%SZ}.json"`.
- [ ] **Step 4: Run** `pytest tests/persistence -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add versioned atomic JSON persistence, migrations and sessions"`

### Task 7: Scores and progress (`scoring/`)

**Files:**
- Create: `src/alexvolkihar_sokoban/scoring/{stars,records}.py`, `schemas/progress.schema.json`,
  `tests/scoring/{test_stars,test_records}.py`

**Interfaces:**
- Consumes: `Par` (Task 3).
- Produces: `stars.compute_stars(moves: int, pushes: int, par: Par | None) -> int` (1–3);
  `stars.beats_par_moves(moves: int, par: Par | None) -> bool`; `records.RunResult(moves: int, pushes: int,
  elapsed_ms: int, lurd: str, assisted: bool, finished_at: str)`; `records.BestSolution(moves: int,
  pushes: int, lurd: str)`; `records.LevelRecord(pack_id: str, level_id: str, completed: bool = False,
  stars: int = 0, plays: int = 0, first_completed_at: str | None = None, best_moves: BestSolution | None =
  None, best_pushes: BestSolution | None = None, best_time_ms: int | None = None)`;
  `records.RecordUpdate(record: LevelRecord, stars_earned: int, new_best_moves: bool, new_best_pushes: bool,
  new_best_time: bool, beats_par_moves: bool)`; `records.LastPlayed(pack_id: str, level_id: str,
  level_hash: str)`; `class Progress` with `levels: dict[str, LevelRecord]`, `last_played: LastPlayed | None`,
  `get(level_hash) -> LevelRecord | None`, `record_run(level_hash: str, pack_id: str, level_id: str,
  run: RunResult, par: Par | None) -> RecordUpdate`, `set_last_played(lp: LastPlayed) -> None`,
  `completed_count(level_hashes: Iterable[str]) -> int`, `reset() -> None`, `to_dict()`, `from_dict()`;
  `PROGRESS_FORMAT = "alexvolkihar-sokoban/progress"`, `PROGRESS_VERSION = 1`. All dataclasses frozen.

- [ ] **Step 1: Write the failing tests**

```python
PAR = Par(pushes=8, moves=30, lurd="", solver="push-astar/1")
def test_stars():
    assert compute_stars(30, 8, PAR) == 3 and compute_stars(31, 8, PAR) == 2
    assert compute_stars(99, 10, PAR) == 2 and compute_stars(99, 11, PAR) == 1   # ceil(1.25*8) = 10
    assert compute_stars(5, 1, None) == 1
def test_first_completion_sets_all_bests():
def test_bests_tracked_independently():  # run A fewer moves, run B fewer pushes → both kept
def test_tie_breaks():  # same moves, fewer pushes → new best_moves
def test_assisted_run_only_marks_completed():  # stars 0→1? no: completed True, stars unchanged, bests None
def test_stars_keep_maximum():
def test_progress_roundtrip_and_schema():
```

  Assisted rule (spec 7.5): an assisted run sets `completed=True`, increments `plays`, sets
  `first_completed_at` if unset, and changes nothing else (`stars_earned` = 0 when the level had no stars).
- [ ] **Step 2–4:** run → FAIL, implement, run `pytest tests/scoring -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add stars, per-level records and progress model"`

### Task 8: Themes (`ui/themes/`)

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/themes/{_draw,kenney,classic,neon,contrast}.py`
- Modify: `src/alexvolkihar_sokoban/ui/themes/registry.py` (replace stub; keep `fallback.py`)
- Create: `tests/ui/test_themes.py`

**Interfaces:**
- Consumes: `CachedTheme`, `TileKind`, `UiPalette` (Task 3).
- Produces: `KenneyTheme`, `ClassicTheme`, `NeonTheme`, `ContrastTheme` (ids `kenney`, `classic`, `neon`,
  `contrast`; names via `t()` are not used here — `name` is a plain English string, scenes translate);
  `registry.THEME_IDS = ("kenney", "classic", "neon", "contrast")`; `available_themes()` returns them in
  that order; `get_theme()` unchanged signature.

- [ ] **Step 1: Write the failing tests** — `test_every_theme_draws_every_kind_at_sizes` (sizes 4, 16, 48,
  64 → surface size `(s, s)`), `test_unknown_theme_falls_back_to_kenney`, `test_tiles_are_cached`
  (`tile(k, 32) is tile(k, 32)`), `test_contrast_theme_is_shape_coded` (convert BOX/BOX_ON_GOAL and
  FLOOR/GOAL to greyscale; differing pixels > 5 % in both pairs), `test_kenney_assets_load_via_importlib
  _resources`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Kenney sprites loaded with `importlib.resources.files(
  "alexvolkihar_sokoban.data") / "themes/kenney/<file>.png"` and `pygame.image.load` (no `convert()`, so it
  works before a display exists); scale with `pygame.transform.smoothscale`. `BOX_ON_GOAL` = crate with a
  green tint + goal ring; `PLAYER_ON_GOAL` = goal sprite under the player; `OUTSIDE` = transparent.
  Contrast palette Okabe–Ito: background `(0, 0, 0)`, wall `(86, 180, 233)` outline blocks, box `(230, 159, 0)`
  with an X, goal ring `(240, 228, 66)`, box on goal `(0, 158, 115)` with a check mark, player `(255, 255, 255)`
  circle.
- [ ] **Step 4: Run** `pytest tests/ui/test_themes.py -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add Kenney, classic, neon and colour-blind-safe themes"`

### Task 9: UI shell — app loop, input, i18n, renderer, main menu, basic game scene

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/{app,scene,input,i18n,widgets,board_renderer}.py`,
  `ui/scenes/__init__.py`, `ui/scenes/{placeholder,main_menu,game}.py`
- Create: `tests/ui/{test_input,test_i18n,test_widgets,test_board_renderer,test_app,test_main_menu,
  test_game_basic}.py`

**Interfaces:**
- Consumes: `core`, `Settings`, `ACTIONS`, `Theme`, `registry.get_theme`, `Pack`, `LevelEntry`.
- Produces (`ui.i18n`): `set_language(lang: Language) -> None`, `get_language() -> Language`,
  `t(en: str, fr: str) -> str`.
- Produces (`ui.input`): `class Action(StrEnum)` with one member per `ACTIONS` value (`Action.UP = "up"`, …);
  `class InputMapper(bindings: Mapping[str, Sequence[str]])` with `actions_for(event: pygame.event.Event) ->
  list[Action]`, `set_bindings(bindings) -> None`, `binding_from_event(event) -> str | None`;
  `describe_binding(binding: str) -> str` (e.g. `"scan:26"` → `"W"`, `"ctrl+key:z"` → `"Ctrl+Z"`).
  Binding grammar: `["ctrl+"] ("key:" <pygame.key.name> | "scan:" <int>)`.
- Produces (`ui.scene`): `class Scene` with `__init__(self, app: App)`, `on_enter(self, **params: object) ->
  None`, `on_exit(self) -> None`, `handle_action(self, action: Action) -> None`, `handle_event(self, event:
  pygame.event.Event) -> None`, `update(self, dt_ms: int) -> None`, `draw(self, surface: pygame.Surface) ->
  None`, class attribute `is_overlay: bool = False` (overlays draw on top of the scene below).
- Produces (`ui.scenes`): `load_scene_class(name: str) -> type[Scene]` — imports
  `alexvolkihar_sokoban.ui.scenes.<name>` and returns its module-level `SCENE`; if that module does not exist
  returns `PlaceholderScene` ("coming soon", Back returns). **Every scene module defines `SCENE = <Class>`**.
  Scene names used by the app: `main_menu, level_select, game, pause, victory, settings, themes, keybindings,
  benchmark, generate, credits, replay`.
- Produces (`ui.app`): `class App(settings: Settings, *, context: object | None = None, headless: bool =
  False)` with attributes `screen`, `settings`, `theme`, `input`, `context`, `fonts` (`small`, `normal`,
  `title` from `pygame.font.Font(None, size)`), methods `push(name: str, **params) -> Scene`,
  `replace(name: str, **params) -> Scene`, `pop() -> None`, `quit() -> None`, `set_theme(theme_id: str) ->
  None`, `apply_display_settings() -> None` (window size / fullscreen from `settings`), `step(events: Sequence[pygame.event.Event], dt_ms: int = 16) -> None` (dispatch to the top scene,
  update, draw the stack), `run() -> None` (60 fps loop calling `step`). Window title `Alexvolkihar Sokoban`,
  icon `data/themes/kenney/icon.png`, resizable, minimum 640×480 (smaller sizes are clamped).
- Produces (`ui.widgets`): `MenuItem(label: str | Callable[[], str], on_select: Callable[[], None],
  enabled: bool = True)`; `MenuList(items: list[MenuItem])` with `selected: int`, `handle_action(action) ->
  bool`, `handle_event(event) -> bool` (mouse hover/click), `draw(surface, rect, font, palette) -> None`.
- Produces (`ui.board_renderer`): `tile_kind_at(level: Level, pos: Pos, player: Pos, boxes: frozenset[Pos])
  -> TileKind`; `@dataclass(frozen=True) class BoardLayout: tile: int; origin: tuple[int, int]` with
  `cell_rect(pos: Pos) -> pygame.Rect`; `class BoardRenderer(theme: Theme)` with `layout(level, area:
  pygame.Rect) -> BoardLayout` (integer tile, `max(4, ...)`, centred) and `draw(surface, level, player,
  boxes, area, *, highlight: Iterable[Pos] = (), arrow: tuple[Pos, Direction] | None = None) -> BoardLayout`.
- Produces (`ui.scenes.game`, basic version): `GameScene.on_enter(pack: Pack, level_id: str, **kw)`; maps
  movement actions to `GameState.move`, draws the board, on win returns to the previous scene. Task 13 owns
  and extends it.
- Produces (`ui.scenes.main_menu`): items Continue, Level select, Random level, Benchmark, Themes, Settings,
  Credits, Quit, pushing scenes `level_select`, `generate`, `benchmark`, `themes`, `settings`, `credits`;
  Continue is disabled until Task 10 wires it. Subtitle `t("remake of Sokoban-LAMA", "remake de
  Sokoban-LAMA")`.

- [ ] **Step 1: Write the failing tests** — `test_wasd_bound_by_scancode` (KEYDOWN with `scancode=26` and
  `key=pygame.K_z` → `[Action.UP]`), `test_ctrl_binding_requires_ctrl`, `test_describe_binding`,
  `test_t_follows_language`, `test_menu_wraps_and_skips_disabled`, `test_tile_kind_at` (box on goal →
  `BOX_ON_GOAL`, cell outside floor → `OUTSIDE`), `test_layout_fits_and_centres`,
  `test_huge_level_in_min_window` (60×60 level, area 640×440 → `tile >= 4`, draw raises nothing),
  `test_unknown_scene_gives_placeholder`, `test_app_step_push_pop`, `test_main_menu_navigation_pushes
  _level_select` (dispatch `Action.DOWN`, `Action.CONFIRM` → top scene name), `test_game_basic_win_pops`
  (play `"rU..."` solution of a 1-box level via actions → scene popped), `test_window_resize_clamped`.
- [ ] **Step 2: Run** `pytest tests/ui -q` → FAIL.
- [ ] **Step 3: Implement** the modules. Key repeat: `pygame.key.set_repeat(180, 60)` for movement.
  `App.step` handles `VIDEORESIZE` (clamp, re-create the screen) and `QUIT` (calls `on_exit()` on every
  scene of the stack, top first, then stops — this is how the game scene saves its session on window close).
- [ ] **Step 4: Run** `pytest tests/ui -q && ruff check .` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add the pygame shell: scenes, input mapping, i18n, renderer, main menu"`

---

## Phase 2 — sequential bridge

### Task 10: App context and `play` command

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/context.py`, `tests/ui/test_context.py`, `tests/commands/test_play.py`
- Modify: `src/alexvolkihar_sokoban/commands/play.py`, `ui/scenes/main_menu.py` (Continue),
  `ui/app.py` (save settings on quit)

**Interfaces:**
- Consumes: Tasks 4, 6, 7, 8, 9.
- Produces: `class AppContext` (dataclass) with `data_dir: Path`, `store: JsonStore`, `settings: Settings`,
  `progress: Progress`, `packs: list[Pack]` (visible, order: `lama-original`, `microban-1`, other bundled
  packs alphabetically, `generated`, `custom`), `hidden_packs: list[Pack]`, `session: SavedSession | None`,
  `warnings: list[str]`; `@classmethod load(cls, data_dir: Path) -> AppContext`; `pack(pack_id: str) ->
  Pack`; `all_packs() -> list[Pack]`; `save_settings() -> bool`; `save_progress() -> bool`;
  `save_session(session: SavedSession | None) -> bool` (None deletes the file);
  `add_generated_level(entry: LevelEntry) -> Pack`; `reload_custom() -> None`; `pop_warnings() -> list[str]`.
  Bundled packs = every `data/levels/*.json` read with `importlib.resources`. Custom pack = every
  `.xsb .sok .txt .json` in `<data dir>/levels/` merged into one pack id `custom` (level ids
  `<file stem>/<id>`), failures appended to `warnings`. First run (`settings` missing) sets
  `language = default_language(locale.getlocale()[0])`.
- Produces (`commands.play`): `play [PATH] [--level ID]`: no PATH → GUI on the main menu; with PATH →
  `load_any`, open `game` directly on that level (default the first), Esc returns to the main menu.
- Produces (main menu): shows `context.pop_warnings()` as a dismissable message (corrupt save backed up,
  broken custom file, too-new save file). `i18n.set_language(settings.language)` at startup.
  Continue enabled when `context.session` or `progress.last_played` exists; resumes the
  session (`game` with `resume=session`) or opens the last played level.

- [ ] **Step 1: Write the failing tests** — `test_load_on_empty_dir_uses_defaults(tmp_path)`,
  `test_custom_levels_dir_tolerates_broken_files` (binary file, invalid level, `.sok` with one valid and one
  invalid level → one custom level, two warnings, no exception), `test_generated_level_persisted`,
  `test_corrupt_settings_warns_and_defaults`, `test_play_command_opens_game_headless(monkeypatch)` (patch
  `App.run` to run 3 frames; top scene is `game`).
- [ ] **Step 2–4:** run → FAIL, implement, `pytest -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Wire the app context: packs, saves, settings and play command"`

---

## Phase 2 — group B (6 agents in parallel, after Task 10)

### Task 11: Bundled level packs and `annotate` command

**Files:**
- Create: `src/alexvolkihar_sokoban/data/levels/{lama-original,lama-unsolvable,microban-1}.json`,
  `tests/data/test_packs.py`
- Modify: `src/alexvolkihar_sokoban/commands/annotate.py`

**Interfaces:**
- Consumes: `formats` (Task 4), `solve` (Task 5).
- Produces: `annotate.annotate_pack(pack: Pack, limits: SolveLimits, *, only_missing: bool = True,
  on_level: Callable[[LevelEntry, SolveResult], None] | None = None) -> Pack`; command `annotate PACK.json
  [--time-limit 60] [--max-nodes 5000000] [--force]` rewrites the file in place.
  Pack ids and level ids are frozen from here on (saves and benchmark suites refer to them):
  `lama-original` levels `test1`…`test11`; `lama-unsolvable` (`hidden: true`) levels `test12`, `test13`,
  `test14` (the invalid `test_performance`, 12 boxes / 14 goals, goes to
  `tests/fixtures/formats/legacy_test_performance.txt` as an invalid-level fixture, not into a pack);
  `microban-1` levels `"1"`…`"155"` (ids of excluded levels are skipped, never renumbered).

- [ ] **Step 1: Write the failing tests** — `test_bundled_packs_validate_against_schema`,
  `test_pack_and_level_ids_are_unique`, `test_every_par_replays_to_solved` (for each entry with `par`,
  `replay(level, par.lurd).is_solved` and counts match), `test_lama_original_credits_the_group`
  (`author` contains the four names), `test_microban_credit` (skipped when the pack is absent;
  `author == "David W. Skinner"`, `license` contains "Skinner", `source` is a URL), `test_lama_unsolvable_is_hidden`, `test_annotate_fills_missing_par(tmp_path)`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Produce the data.** Convert `legacy/level/test1..test11.txt` (not `lvlultime`, duplicate;
  not `wiki`, copyright). Obtain Microban (155 levels) from a public collection (e.g. sourcecode.se or
  sokobano.de); treat the download as untrusted data (parse it with `-I`, no execution); drop any level whose
  notes credit another author and record the dropped ids in the pack `license` note. **Licence gate (spec
  12):** commit `microban-1.json` only if the downloaded file carries Skinner's own copyright/distribution
  notice; copy it verbatim into `license` with the URL in `source`. If no such notice is found, do not
  commit Microban, report "Microban blocked: notice not found" and continue with the LAMA packs. Run `annotate` with 60 s / 5,000,000 nodes in the background (it can take hours for the
  hardest Microban levels; levels it cannot solve keep `par: null`) and commit the result.
- [ ] **Step 4: Run** `pytest tests/data -q` → PASS. Report the number of Microban levels with `par: null`.
- [ ] **Addition (approved by the owner):** `data/levels/boxoban-hard.json` — the first 100 puzzles of DeepMind
  Boxoban `hard/000.txt` (Apache-2.0; ids `"1"`…`"100"`, id N = puzzle N-1), title "Boxoban (hard)", shown after
  Microban; Apache text + requested citation in `data/levels/boxoban-hard.LICENSE.txt`; pars by `annotate`.
- [ ] **Step 5: Commit** `git commit -m "Add LAMA and Microban level packs with solver par"`

### Task 12: Benchmark core and `bench` command

**Files:**
- Create: `src/alexvolkihar_sokoban/benchmark/{machine,suites,runner,export,compare}.py`,
  `src/alexvolkihar_sokoban/data/benchmarks/{suites.json,extra.json}`, `schemas/benchmark.schema.json`,
  `tests/benchmark/{test_machine,test_suites,test_runner,test_export,test_compare,test_cli}.py`
- Modify: `src/alexvolkihar_sokoban/commands/bench.py`

**Interfaces:**
- Consumes: `solve`, `SolveLimits`, `SolveResult`, `Pack`, `formats.jsonfmt`, `__version__`.
- Produces: `MachineInfo(os: str, os_version: str, arch: str, is_wsl: bool, cpu_model: str | None,
  cpu_count_logical: int | None, ram_total_bytes: int | None, python: str, pygame_ce: str | None,
  app_version: str)`, `collect_machine_info() -> MachineInfo`; `Suite(id: str, title: str, limits:
  SolveLimits, items: tuple[str, ...])` where an item is `"<pack_id>"` (whole pack) or
  `"<pack_id>/<level_id>"`; `load_suites() -> dict[str, Suite]`; `resolve(suite: Suite, packs: Mapping[str,
  Pack]) -> tuple[list[tuple[Pack, LevelEntry]], list[str]]` (resolved items, missing items — a missing
  pack or level is skipped and reported, never an exception, so an absent Microban pack only shrinks a
  suite); `extra.json` is pack
  `bench-extra` (hidden) holding the repaired `test_performance` (two goals removed, row padded; its
  `license` notes the modification); `LevelResult(pack_id, level_id, level_hash, status: SolveStatus,
  pushes: int | None, moves: int | None, nodes_expanded: int, nodes_generated: int, elapsed_ms: int,
  peak_mem_bytes: int)`; `Summary(solved: int, total: int, total_ms: int, nodes_per_s: int)`;
  `BenchmarkRun(run_id: str, created_at: str, app_version: str, solver: dict[str, str], machine:
  MachineInfo, suite_id: str, limits: SolveLimits, results: tuple[LevelResult, ...], summary: Summary)`;
  `run_suite(items: Sequence[tuple[Pack, LevelEntry]], *, suite_id: str, limits: SolveLimits,
  solve_fn: Callable[..., SolveResult] = solve, on_level_start: Callable[[int, int, LevelEntry], None] |
  None = None, on_level_done: Callable[[int, LevelResult], None] | None = None, should_stop: Callable[[],
  bool] | None = None, now: Callable[[], datetime] | None = None) -> BenchmarkRun`;
  `export.run_to_dict(run) -> dict`, `export.run_from_dict(d) -> BenchmarkRun`, `write_json(run, path)`,
  `write_csv(run, path)`, `read_json(path) -> BenchmarkRun`; `compare.compare(a, b) -> Comparison`,
  `compare.format_comparison(c: Comparison) -> str`. `run_id` = `created_at` with `:` replaced by `-` plus
  4 random hex chars.
  Suites: `quick` = `lama-original` (limits 10 s / 1,000,000); `standard` = `lama-original` + `microban-1/1`
  … `microban-1/40` (30 s / 3,000,000); `stress` = `lama-unsolvable` + `bench-extra` + `microban-1`
  (60 s / 5,000,000).
- Command: `bench [--suite quick] [--out FILE] [--csv FILE] [--data-dir]` (default output
  `<data dir>/benchmarks/<run_id>.json`), prints a table and the machine block; `bench compare A B`.

- [ ] **Step 1: Write the failing tests** — `test_machine_info_has_no_hostname` (no field equals
  `socket.gethostname()`), `test_wsl_detection(tmp_path)` (fake `/proc/version` content via a parameter),
  `test_suites_load_and_items_parse`, `test_resolve_reports_missing_items`, `test_runner_with_fake_solver`
  (fixed `SolveResult`s, injected `now` → deterministic `BenchmarkRun`; `summary.nodes_per_s ==
  total_nodes * 1000 // total_ms`), `test_runner_stops_on_should_stop`, `test_json_roundtrip_and_schema`,
  `test_csv_has_one_row_per_level_and_header`, `test_compare_reports_time_delta_and_status_change`,
  `test_bench_cli_quick_on_fixture_pack(tmp_path)`.
- [ ] **Step 2–4:** run → FAIL, implement (peak memory: `tracemalloc.start()`/`reset_peak()` around each
  solve, `get_traced_memory()[1]`), `pytest tests/benchmark -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add the solver benchmark: machine info, suites, runner, export, compare"`

### Task 13: Full game scene — HUD, undo/redo, restart, pause, victory, saves, scores

**Files:**
- Modify: `src/alexvolkihar_sokoban/ui/scenes/game.py`
- Create: `src/alexvolkihar_sokoban/ui/hud.py`, `ui/scenes/pause.py`, `ui/scenes/victory.py`,
  `tests/ui/{test_game_scene,test_pause,test_victory,test_hud}.py`

**Interfaces:**
- Consumes: `AppContext` (Task 10), `GameState`, `lurd.restore`, `Progress.record_run`, `RunResult`,
  `SavedSession`, `compute_stars`.
- Produces: `GameScene.on_enter(pack: Pack, level_id: str, resume: SavedSession | None = None)`; public
  attributes `state: GameState`, `elapsed_ms: int`, `assisted: bool`, `paused: bool`; method
  `save_session() -> None`; `PauseScene` (overlay) items Resume, Restart, Watch solution (pushes `replay`;
  Task 18 implements that scene), Level select, Main menu; `VictoryScene.on_enter(pack: Pack, level_id: str,
  update: RecordUpdate, run: RunResult, par: Par | None)` items Next level (absent on the last level),
  Replay, Level select. HUD shows pack/level title, moves, pushes, time (if `show_timer`), par
  `pushes/moves` or `—`, and key hints via `describe_binding`.
- Rules: move animation follows `settings.animation` (off = instant, normal = 120 ms, fast = 60 ms per
  step, tweening the player and the pushed box); at most 2 inputs are queued during an animation. Timer
  counts only while the game scene is on top and not paused (and stops on
  `WINDOWFOCUSLOST`/`ACTIVEEVENT` loss); restart only on a second `restart` action within 1,500 ms (first
  press shows `t("Press R again to restart", "Appuyez encore sur R pour recommencer")`); session saved on
  pause, on leaving, on `QUIT`, and every 10,000 ms of play; on win: `record_run`, `save_progress`, delete
  the session, push `victory`; leaving via Level select/Main menu deletes the session only if `moves == 0`
  (otherwise it is kept for Continue); `last_played` updated on enter.

- [ ] **Step 1: Write the failing tests** — `test_undo_redo_actions`, `test_restart_needs_double_press`
  (second press after 1,600 ms of `update` does not restart), `test_timer_pauses_with_pause_overlay`,
  `test_win_records_progress_and_shows_victory` (stars from par), `test_session_saved_and_resumed`
  (enter, move, leave → `context.session.lurd == "r"`; re-enter with `resume` → same state),
  `test_resume_with_stale_hash_starts_fresh`, `test_victory_next_level`, `test_resize_mid_game_relayouts`
  (post `VIDEORESIZE` 700×500 → no exception, tile size changes), `test_hud_texts_in_french`.
- [ ] **Step 2–4:** run → FAIL, implement, `pytest tests/ui -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Complete the game scene with HUD, pause, victory, saves and scores"`

### Task 14: Level select scene

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/scenes/level_select.py`, `ui/thumbnails.py`,
  `tests/ui/{test_level_select,test_thumbnails}.py`

**Interfaces:**
- Consumes: `AppContext.packs`, `Progress.get`, `Level.canonical_hash`, `BoardRenderer`, theme.
- Produces: `thumbnails.render_thumbnail(level: Level, theme: Theme, max_size: tuple[int, int]) ->
  pygame.Surface` (memoised per `(level hash, theme id, max_size)`); `LevelSelectScene.on_enter(pack_id:
  str | None = None)` — left column packs with "completed X / N", right grid of tiles (thumbnail, id/title,
  check mark, 0–3 stars, best moves/pushes), Left/Right/Up/Down navigate the grid, `back` returns,
  Tab or Left at column 0 moves focus to the pack list, `confirm` pushes `game` with `(pack, level_id)`.
  Empty `custom` pack shows the path of `<data dir>/levels/` to drop files into.

- [ ] **Step 1: Write the failing tests** — `test_lists_visible_packs_only`, `test_completed_count_and
  _stars_from_progress`, `test_grid_navigation_and_confirm_opens_game`, `test_empty_custom_pack_shows_hint`,
  `test_thumbnail_fits_max_size_and_is_cached`.
- [ ] **Step 2–4:** run → FAIL, implement, `pytest tests/ui -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add the level select scene with thumbnails, stars and bests"`

### Task 15: Settings, theme selector and keybinding scenes

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/scenes/{settings,themes,keybindings}.py`,
  `tests/ui/{test_settings_scene,test_themes_scene,test_keybindings_scene}.py`

**Interfaces:**
- Consumes: `AppContext.settings/save_settings/progress/save_progress`, `available_themes`,
  `App.set_theme`, `InputMapper.binding_from_event`, `describe_binding`, `i18n.set_language`.
- Produces: Settings items Language (fr/en), Animation (off/normal/fast), Show timer, Fullscreen,
  Keybindings → `keybindings`, Reset progress (asks "press confirm again"), Back; every change applies
  immediately and calls `save_settings()`. Themes scene: theme list + live preview of a fixed 7×7 sample
  board (one goal, one box, one box on goal, player) rendered with the highlighted theme; `confirm` applies
  and saves. Keybindings scene: one row per action with its bindings; `confirm` enters capture mode, next
  KEYDOWN becomes the only binding of that action (Esc cancels capture), `Delete` restores that action's
  defaults, an item "Reset all" restores `DEFAULT_KEYBINDINGS`; binding a key already used by another
  movement action shows a warning and swaps them.

- [ ] **Step 1: Write the failing tests** — `test_language_switch_saves_and_translates`,
  `test_theme_selection_applies_and_saves`, `test_preview_uses_highlighted_theme`,
  `test_rebind_action_captures_next_key`, `test_rebind_conflict_swaps`, `test_reset_progress_requires
  _confirmation`.
- [ ] **Step 2–4:** run → FAIL, implement, `pytest tests/ui -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add settings, theme selector and key rebinding scenes"`

### Task 16: Procedural generator and `generate` command

**Files:**
- Create: `src/alexvolkihar_sokoban/generator/{presets,carve,reverse,api}.py`,
  `tests/generator/{test_carve,test_reverse,test_api,test_cli}.py`
- Modify: `src/alexvolkihar_sokoban/commands/generate.py`

**Interfaces:**
- Consumes: `solve`, `SolveLimits`, `Level`, `LevelEntry`, `Par`, `SOLVER_ID`, `formats.detect.save_any`.
- Produces: `Preset(id: str, width: int, height: int, boxes: int, min_pushes: int, pull_steps: int,
  limits: SolveLimits, max_attempts: int)`; `PRESETS: Mapping[str, Preset]` = `easy` (7, 7, 2, 6, 60,
  2 s/200,000, 50), `medium` (8, 8, 3, 12, 120, 4 s/400,000, 50), `hard` (10, 9, 4, 20, 200, 8 s/800,000, 50);
  `carve.carve_room(rng: random.Random, width: int, height: int) -> frozenset[Pos]` (connected floor, at
  least 60 % of the interior); `reverse.reverse_play(rng, floor: frozenset[Pos], goals: frozenset[Pos],
  player: Pos, steps: int) -> tuple[frozenset[Pos], Pos]`; `api.GeneratedLevel(entry: LevelEntry,
  attempts: int)`; `api.generate(preset: Preset | str, seed: int | None = None, *, solve_fn=solve,
  should_stop: Callable[[], bool] | None = None) -> GeneratedLevel` (entry id `f"{preset.id}-{seed}"`,
  `entry.seed == seed`, `entry.par` from the solver), raises `GenerationFailed` after `max_attempts`.
  Command: `generate [--preset medium] [--seed N] [--out FILE]` (prints XSB when no `--out`).

- [ ] **Step 1: Write the failing tests** — `test_carve_is_connected_and_enclosed`, `test_reverse_play_
  keeps_box_count_and_floor`, `test_generate_is_deterministic_for_a_seed` (same seed → same
  `canonical_hash()`), `test_generated_level_is_valid_and_meets_min_pushes` (easy preset, seeds 1–5),
  `test_generation_failure_raises` (fake `solve_fn` always UNSOLVABLE), `test_generate_cli_prints_xsb`.
- [ ] **Step 2–4:** run → FAIL, implement, `pytest tests/generator -q && mypy` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add the solver-validated procedural level generator"`

---

## Phase 2 — group C (4 agents in parallel, after group B)

### Task 17: Credits scene

**Files:** Create `src/alexvolkihar_sokoban/ui/scenes/credits.py`, `tests/ui/test_credits.py`

**Interfaces:** Produces `CreditsScene` (scrollable with up/down, `back` returns). Content: original game
"Sokoban-LAMA" by Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN, Martin PACARY (groupe LAMA, L1) and its
GitHub URL; remake by Alexis MABANZA; sprites Kenney (CC0); Microban levels David W. Skinner; deadlock
patterns of the original solver inspired by KnightofLuna; pygame-ce (LGPL). Text pulled from each bundled
pack's `author`/`license` so new packs appear automatically.

- [ ] **Step 1:** test `test_credits_list_lama_members_and_pack_authors` (all four names and
  `"David W. Skinner"` in the rendered text lines) → **Step 2** FAIL → **Step 3** implement → **Step 4** PASS
  → **Step 5** `git commit -m "Add the credits scene"`

### Task 18: Hint and "watch the solver" replay

**Files:**
- Create: `src/alexvolkihar_sokoban/ui/solver_worker.py`, `ui/scenes/replay.py`,
  `tests/ui/{test_solver_worker,test_hint,test_replay}.py`
- Modify: `src/alexvolkihar_sokoban/ui/scenes/game.py`, `ui/scenes/pause.py`

**Interfaces:**
- Consumes: `solve`, `GameState.signature()`, `BoardRenderer.draw(highlight=, arrow=)`.
- Produces: `class SolverWorker` with `start(level: Level, boxes: frozenset[Pos], player: Pos, limits:
  SolveLimits, mode: Mode = "optimal", tag: object = None) -> None` (cancels a running job first),
  `cancel() -> None`, `poll() -> tuple[object, SolveResult] | None` (tag, result), property `busy: bool`;
  thread + `threading.Event` as `should_stop`. Hint (action `hint`): limits 3 s / 500,000 nodes, `optimal`,
  falling back to `fast` once on a limit status; tag = `state.signature()`; on result with the same
  signature show the walk cells (`highlight`) and the next push (`arrow`) until the next move; `UNSOLVABLE`
  → message `t("Dead end — undo some moves", "Impasse — annulez quelques coups")`; any hint marks the run
  `assisted`. `ReplayScene.on_enter(pack: Pack, level_id: str)` plays `par.lurd` (or solves with 30 s /
  3,000,000 in the worker, showing "Solving…") from the initial state: `confirm` play/pause, left/right
  step back/forward, up/down speed (1, 2, 4, 8 steps per second), `back` returns; entering it marks the
  calling game run `assisted` (pass `on_watch` callback from the pause menu).

- [ ] **Step 1: Write the failing tests** — `test_worker_returns_result_and_cancel`, `test_hint_highlights
  _next_push`, `test_stale_hint_is_discarded` (start hint, move before `poll()` returns → no highlight),
  `test_hint_on_dead_end_shows_message`, `test_hint_marks_run_assisted`, `test_replay_plays_par_to_solved`
  (advance time → state solved), `test_replay_speed_and_step_controls`.
- [ ] **Step 2–4:** run → FAIL, implement, `pytest tests/ui -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Add solver hints and the watch-the-solver replay"`

### Task 19: Benchmark scene

**Files:** Create `src/alexvolkihar_sokoban/ui/scenes/benchmark.py`, `tests/ui/test_benchmark_scene.py`,
`tests/benchmark/test_bundled_suites_resolve.py`

**Interfaces:** Consumes `load_suites`, `resolve`, `run_suite`, `collect_machine_info`, `write_json`,
`write_csv`, `read_json`, `compare`, `AppContext.store/data_dir`. Produces `BenchmarkScene`: suite picker →
Run (in a background thread; live "level i/N, name, elapsed"; `back` cancels via `should_stop`) → results
table (level, status, pushes, moves, nodes, ms, peak KiB) with the machine panel and summary; actions
Export JSON (auto-saved to `<data dir>/benchmarks/<run_id>.json` anyway), Export CSV, Compare with a
previous run (list of saved runs, shows per-level time delta % and status changes).

- [ ] **Step 1:** tests `test_bundled_suites_resolve` (the `quick` suite has no missing item; other suites
  may miss only `microban-1` items, and only when that pack is not bundled; the scene shows missing items as
  a warning line), `test_scene_runs_quick_suite_with_fake_solver` (monkeypatch `solve`), `test_cancel_stops_run`,
  `test_results_saved_and_comparable` → **Step 2** FAIL → **Step 3** implement → **Step 4** `pytest -q` PASS
  → **Step 5** `git commit -m "Add the benchmark scene"`

### Task 20: Random level scene

**Files:** Create `src/alexvolkihar_sokoban/ui/scenes/generate.py`, `tests/ui/test_generate_scene.py`

**Interfaces:** Consumes `generator.api.generate`, `PRESETS`, `AppContext.add_generated_level`.
Produces `GenerateScene`: preset choice (easy/medium/hard), optional seed (digits typed, empty = random),
Generate (background thread, "Generating…", cancellable) → `add_generated_level(entry)` → `replace("game",
pack=generated_pack, level_id=entry.id)`; `GenerationFailed` → message and retry option.

- [ ] **Step 1:** tests `test_generate_adds_to_generated_pack_and_opens_game` (fake generator),
  `test_seed_input_digits_only`, `test_failure_shows_message` → **Step 2** FAIL → **Step 3** implement →
  **Step 4** PASS → **Step 5** `git commit -m "Add the random level scene"`

---

## Phase 3 — group D (3 agents in parallel, after group C)

### Task 21: Format reference for the Godot port and changelog

**Files:** Create `docs/formats.md`, `CHANGELOG.md`, `tests/test_schemas.py`

- [ ] **Step 1:** `tests/test_schemas.py`: every file in `schemas/` is a valid Draft 2020-12 schema; every
  example JSON block in `docs/formats.md` (fenced ```json) validates against the schema named in the line
  above it (`<!-- schema: pack -->`).
- [ ] **Step 2:** run → FAIL. **Step 3:** write `docs/formats.md`: XSB symbols and legacy mapping, canonical
  hash algorithm with a worked example, LURD, each JSON format (pack, level, settings, progress, session,
  benchmark) with an example, versioning/migration rules, conformance vectors and how a port must use
  them, stars formula, solver par semantics (push-optimal). `CHANGELOG.md` (Keep a Changelog) with
  `1.0.0` listing the features and `0.0.0 — Sokoban-LAMA (2022)` crediting the group.
- [ ] **Step 4:** `pytest tests/test_schemas.py -q` → PASS. **Step 5:** `git commit -m "Document the portable
  data formats and add the changelog"`

### Task 22: README media capture (screenshots, MP4, GIF)

**Files:** Create `scripts/capture.py`, `scripts/storyboard.json`, `docs/media/{menu,level-select,gameplay,
themes,benchmark,victory}.png`, `docs/media/demo.mp4`, `docs/media/demo.gif`, `tests/test_capture.py`

**Interfaces:** Consumes the whole app (`App.step` with synthetic events, `headless=True`). Produces
`python scripts/capture.py --out docs/media [--only screenshots|video]`, deterministic (window 1280×720,
seed 42, fixed fake clock, benchmark screenshot from a fake `BenchmarkRun` fixture with a neutral
machine name, data dir in a temp folder).

- [ ] **Step 1:** `tests/test_capture.py`: `capture.render_storyboard(storyboard, frames=10)` returns 10
  surfaces of size 1280×720 headless (skips if `imageio` missing for the encode test).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement. Storyboard (follow the owner's starred skill `latent-spaces/brag`, brag-slim
  variant, if available in the session; otherwise this order): 0–3 s hook (last push of a level, boxes
  snap onto goals, stars appear) → main menu → level select browsing → play a level with one undo → hint
  arrow → pause → watch the solver at speed 4 → theme switch cycling the four themes on the same board →
  benchmark results table → end card "alexvolkihar_sokoban — remake of Sokoban-LAMA by the LAMA group".
  ≤ 30 s at 30 fps. MP4 via `imageio.v3.imwrite(..., fps=30, codec="libx264", pixelformat="yuv420p")`
  (≤ 8 MB); GIF 640 px wide, 12 fps, ≤ 5 MB (drop frames/colours until it fits).
- [ ] **Step 4:** `pip install -e '.[media]' && python scripts/capture.py --out docs/media` → files exist
  within size limits; open two PNGs and the GIF to check them visually. `pytest tests/test_capture.py -q` PASS.
- [ ] **Step 5:** `git commit -m "Add the headless capture script and README media"`

### Task 23: Packaging and release check

**Files:** Modify `pyproject.toml` (version `1.0.0`, classifiers, URLs to
`https://github.com/Alexvolkihar/alexvolkihar_sokoban`), `src/alexvolkihar_sokoban/__init__.py`,
`.github/workflows/ci.yml` (add a `build` job: `python -m build`, install the wheel in a fresh venv, run
`alexvolkihar-sokoban --version` and `alexvolkihar-sokoban bench --suite quick --out /tmp/b.json`).
Create `tests/test_package_data.py`.

- [ ] **Step 1:** `test_package_data.py`: `importlib.resources` finds the three level packs, `suites.json`,
  `extra.json` and the six Kenney PNGs + `LICENSE.txt`. **Step 2:** run (should pass if earlier tasks were
  right; if FAIL, fix `pyproject.toml` includes). **Step 3:** build locally, install the wheel in
  `python -m venv /tmp/avs-venv`, run the two commands. **Step 4:** all green.
  **Step 5:** `git commit -m "Prepare the 1.0.0 package"` (no tag, no push — the owner tags).

---

## Phase 3 — sequential end

### Task 24: Polished README in French and English

**Files:** Modify `README.md` (French), `README.en.md` (English); keep `legacy/README.md` untouched.

- [ ] **Step 1:** write both READMEs with the same structure: title + language switch link; inline
  `docs/media/demo.gif`; link to `docs/media/demo.mp4` (plus a note for the owner: to get an inline player on
  GitHub, drag the MP4 into the README editor on github.com and paste the generated `user-attachments` URL);
  one-paragraph pitch; **credits first**: remake of Sokoban-LAMA by Antoine LAROCHE, Alexis MABANZA, Logan
  VIVIEN, Martin PACARY (link to the original repo); features with the five screenshots; installation
  (`pipx install git+https://github.com/Alexvolkihar/alexvolkihar_sokoban` and from source); usage of every
  CLI command; controls table (default keys, rebinding); level formats and where to drop custom levels;
  benchmark (how to run, how to compare, what is measured, privacy note); saves location per OS;
  "What changed since Sokoban-LAMA" (spec section 2 findings); development (tests, ruff, mypy, capture
  script); asset and level credits with licences; licence section ("pending agreement of the original
  authors" until Task 25).
- [ ] **Step 2:** check every relative link and image path exists: `python -c` script or
  `grep -o '](docs/[^)]*' README*.md` → all files present.
- [ ] **Step 3:** `git commit -m "Write the French and English READMEs with screenshots and demo"`

### Task 25: Licence (BLOCKED until the owner confirms the group's consent)

- [ ] Add `LICENSE` (MIT proposed: "Copyright (c) 2022 Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN,
  Martin PACARY" and "Copyright (c) 2026 Alexis MABANZA"), set `license = "MIT"` in `pyproject.toml`,
  update the licence section of both READMEs; commit `"Add the MIT licence agreed by the LAMA group"`.
  If the group chooses another licence, use it instead.

### Task 26: Final whole-branch review

- [ ] Run `ruff check . && ruff format --check . && mypy && pytest -q --cov=alexvolkihar_sokoban`; coverage of
  non-UI packages ≥ 85 %.
- [ ] Play-test manually: menu → level select → play `lama-original/test3` with undo, hint, pause, replay →
  victory → theme switch → settings language FR/EN → quick benchmark → random level; quit and relaunch:
  Continue resumes, stars kept.
- [ ] `git log` contains no `Co-Authored-By` and no AI attribution:
  `git log --format=%B | grep -i -E 'co-authored|claude|anthropic|generated with'` → no output;
  same grep over the tree excluding `.git` and `docs/superpowers/` (which name the rule itself) → no output.
- [ ] Review against the spec's goals list and the Review Focus items; fix or file issues.

---

## Phase 4 — follow-up (not scheduled)

Godot remake (spec 14): reimplement `core` in GDScript/C# against `tests/vectors/*.json` and
`docs/formats.md`, reuse `data/levels/*.json` and the save formats; keep the Python solver as the par
reference.
