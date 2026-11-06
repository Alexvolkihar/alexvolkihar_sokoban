# alexvolkihar_sokoban — design

Date: 2026-11-05
Status: draft, written without a live conversation with the owner (see "Decisions made without the user").
Update 2026-11-06: the repository now ships only its author's own work. The copy of the original project
(`legacy/`), its levels and everything derived from them were removed; the bundled packs are `first-steps`
(hand-made) and `boxoban-hard`, the benchmark extras are generated and hand-made levels, and the code is
under the MIT licence. The sections below are updated accordingly.
Implementation plan: completed, then removed from the repository (it stays in the git history). "Phase
1/2/3" in this document are the plan's phases (1 = foundation and frozen contracts, 2 = features, 3 = release); the Godot
remake is the separate follow-up of section 14.

## 1. Intent

**alexvolkihar_sokoban** (GitHub: <https://github.com/Alexvolkihar/alexvolkihar_sokoban>, public) is an
improved remake of **Sokoban-LAMA**, the owner's first-year university project (2022), original
repository: <https://github.com/Alexvolkihar/Sokoban-LAMA>. The remake names it as its origin in the
READMEs, the credits screen and the main menu subtitle.

The owner's wish, in his words: *"améliore le projet, menu, sélection de niveaux, niveaux etc, pourquoi pas
une partie benchmark de machine, un sélecteur de thèmes, un système de sauvegarde, de score"*. A later phase
will remake the game in **Godot**, so the game rules and every data format must be engine-agnostic and
documented well enough to be reimplemented.

What makes it worth doing: it turns a ~545-line student prototype (single level from the command line, no
menu, a solver that can exhaust RAM) into a small, finished, well-tested game that the owner can show
publicly, and that doubles as a machine benchmark thanks to its solver.

## 2. Current state (the original code)

Python 3 + pygame, four files: `main.py` (CLI `play`/`solve`), `sokoban.py` (pygame view + game logic mixed),
`aStar.py` (level parsing + "A*" solver), `PriorityQueue.py`. 17 level files in `level/`, 6 sprites in
`img/`.

Findings from reading it (they shape the redesign and are worth mentioning in the README "What changed"):

- **The "A*" is not A\***: `PriorityQueue.pop()` does `queue.pop(0)` and ignores priorities, so the search is
  a breadth-first search over moves that stores the full path in every node. That is why it can "loop" and
  eat RAM on larger levels. The heuristic also pairs boxes with goals in arbitrary set order and the cost
  function counts only non-push moves.
- **The board is drawn transposed**: cell `(row, col)` is blitted at `x = row * SIZE, y = col * SIZE`, so
  every level appears mirrored along its diagonal, and the solver replay remaps `u/d/l/r` to compensate.
- **Import-time side effects**: `PygView.WIDTH` instantiates `Grid()`, which reads `sys.argv[2]` and the
  level file when `sokoban.py` is imported.
- Images are reloaded on every cell move and rescaled on every frame; files are opened without being closed.
- Level format: `X` wall, space floor, `*` box, `.` goal, `@` player. No "box on goal" or "player on goal"
  symbol. **The `*` symbol conflicts with the standard XSB format, where `*` means box on goal.**
- Level data: the original levels stay in the original repository; none of them is shipped here (section 8).
- The solver of this remake is written from scratch; nothing of the original search code is reused.
- No licence file; this repository is under the MIT licence (section 12).

## 3. Goals

1. A complete game loop: main menu → level select → play → victory → next level, with pause, undo/redo,
   restart, hint, "watch the solver" replay and settings.
2. More content: hand-made levels plus at least one freely licensed classic set (Boxoban), standard
   `.xsb`/`.sok` import, and a procedural generator whose levels are validated by the solver.
3. A real solver: push-based A* with deadlock detection, compact state hashing, and hard time/node limits so
   it can never exhaust memory. It reports "unsolvable" with proof when the search space is exhausted.
4. A benchmark mode: run the solver over a level suite, measure time, nodes and memory per level, show machine
   information, export JSON/CSV and compare two runs.
5. Themes: a theme selector with Kenney sprites plus procedurally drawn themes, including a
   colour-blind-safe one; the choice is persisted.
6. Saves and scores: settings, progress, per-level best scores and the in-progress level survive restarts;
   stars are given relative to the solver's par.
7. Quality: engine-agnostic core with a pytest suite, CI on GitHub Actions (lint + type check + tests),
   README in French and English.
8. A polished README (French `README.md`, English `README.en.md`) with an inline demo (short MP4 plus a GIF
   fallback) and screenshots of the main menu, level select, gameplay, themes and benchmark, all captured
   from the game itself (section 11.1).
9. Portability: every persisted or exchanged format is versioned JSON (or plain XSB text), documented, and
   backed by JSON Schemas and conformance test vectors that a Godot port can reuse.

## 4. Non-goals (for this phase)

- The Godot remake itself (follow-up phase, section 14).
- Sound and music.
- A level editor (import of `.xsb` files covers custom levels for now).
- Web/mobile builds (pygbag, Android).
- Online features: leaderboards, accounts, telemetry. Benchmark results are shared by exporting files.
- Level progression locks: every level is playable from the start.

## 5. Anti-goals (would make the project a failure even if it "works")

- Shipping code or levels that are not the owner's own work, other than the credited third-party assets.
- Shipping any asset or level whose licence does not allow redistribution in a public repository.
- Game rules that only exist inside pygame code (the Godot port must not need to reverse-engineer them).
- A solver that can still freeze the game or exhaust memory.
- A save system that silently loses progress (corrupt file → backup and warning, never a crash or a wipe).
- Any mention of an AI assistant as an author or contributor (commits, docs, code, metadata).

## 6. Constraints

- **Language/runtime**: Python ≥ 3.11 (CI matrix 3.11, 3.12, 3.13, 3.14).
- **Graphics library**: `pygame-ce` ≥ 2.5 (2.5.8 published 2026-08-09, wheels for CPython 3.10–3.15 on
  Windows, Linux and macOS). Upstream `pygame` 2.6.1 (2024-09-29) has no CPython 3.14 wheel, which is the
  exact problem the original README warns about. `pygame-ce` is a drop-in replacement (`import pygame`),
  licence LGPL-2.1-or-later.
- **Runtime dependencies**: `pygame-ce` and `platformdirs` only. Everything else is standard library.
- **Dev dependencies**: `pytest`, `pytest-cov`, `ruff`, `mypy`, `jsonschema`; optional `media` extra:
  `imageio`, `imageio-ffmpeg` (README video only).
- **Layering rule (enforced)**: only `alexvolkihar_sokoban.ui` and `alexvolkihar_sokoban.commands.play` may import `pygame`.
  Enforced by Ruff `flake8-tidy-imports` banned-api with per-file ignores, and by a test that imports every
  non-UI module with `pygame` blocked in `sys.modules`.
- **Coordinates**: `(row, col)`, row 0 at the top, col 0 at the left, everywhere (fixes the transposition).
- **No AI attribution** anywhere; commits are authored by the owner's git identity only.

## 7. Architecture

### 7.1 Repository layout

```
alexvolkihar_sokoban/
├── src/alexvolkihar_sokoban/
│   ├── __init__.py             # __version__
│   ├── __main__.py             # python -m alexvolkihar_sokoban → cli.main()
│   ├── cli.py                  # argparse dispatcher; each subcommand lives in commands/<name>.py
│   ├── commands/               # play.py, solve.py, convert.py, bench.py, generate.py, annotate.py
│   ├── core/                   # pure rules, no I/O
│   │   ├── geometry.py         # Direction, Pos helpers
│   │   ├── level.py            # Level (immutable), Level.from_rows(), validation, canonical hash
│   │   ├── state.py            # GameState: moves, pushes, undo/redo, solved check
│   │   ├── lurd.py             # LURD notation encode/decode/replay
│   │   └── pack.py             # Pack, LevelEntry, Par (data model only)
│   ├── formats/                # xsb.py, legacy.py, jsonfmt.py, detect.py (load_any(path) → Pack)
│   ├── solver/                 # api.py (SolveLimits, SolveResult, SolveStatus, solve()), deadlocks.py,
│   │                           # distances.py, heuristics.py, search.py, reachability.py
│   ├── generator/              # reverse-play generator validated by the solver
│   ├── scoring/                # stars.py, records.py (LevelRecord, Progress, merge rules)
│   ├── persistence/            # paths.py, store.py (atomic versioned JSON), migrations.py,
│   │                           # settings.py (Settings), session.py (SavedSession)
│   ├── benchmark/              # machine.py, suites.py, runner.py, export.py, compare.py
│   ├── ui/                     # the only pygame package
│   │   ├── app.py, scene.py, context.py, widgets.py, input.py, i18n.py, board_renderer.py, hud.py,
│   │   │   thumbnails.py, solver_worker.py
│   │   ├── themes/             # base.py (Theme protocol, TileKind), registry.py, kenney.py, classic.py,
│   │   │                       # neon.py, contrast.py
│   │   └── scenes/             # main_menu, level_select, game, pause, victory, settings, themes,
│   │                           # keybindings, benchmark, generate, credits, placeholder
│   └── data/
│       ├── levels/             # first-steps.json, boxoban-hard.json (pack JSON)
│       ├── benchmarks/         # suites.json, extra.json (hidden bench-extra pack)
│       └── themes/kenney/      # four Kenney PNGs + LICENSE.txt (CC0)
├── schemas/                    # JSON Schemas: level, pack, settings, progress, session, benchmark
├── tests/                      # mirrors src; tests/vectors/*.json are cross-engine conformance vectors
├── docs/formats.md             # human-readable format reference for the Godot port
├── scripts/capture.py          # headless screenshots, MP4 and GIF for the README (11.1)
├── docs/media/                 # README screenshots, demo.mp4, demo.gif
├── .github/workflows/ci.yml
├── pyproject.toml              # hatchling build, entry point `alexvolkihar-sokoban`
├── README.md (FR) and README.en.md (EN)
└── LICENSE                     # MIT (section 12)
```

### 7.2 Core rules (`core/`)

- `Level` is immutable: `width`, `height`, `walls: frozenset[Pos]`, `goals: frozenset[Pos]`,
  `boxes: frozenset[Pos]` (initial), `player: Pos`, plus optional `title`, `author`, `comment`.
- `Level.from_rows(rows: Sequence[str])` understands standard XSB characters only (`#`, `@`, `+`, `$`, `*`,
  `.`, space, `-`, `_`). File formats (RLE, multi-level `.sok`, legacy, JSON) are the job of `formats/`.
- Validation (raises `InvalidLevelError` with a human-readable reason): exactly one player; at least one box;
  number of boxes == number of goals; the player's walkable region (flood fill through non-wall cells) never
  leaves the grid; every box and goal lies inside that region or is a wall-free cell reachable by pushing
  (simplification allowed: every box and goal must be inside the bounding grid and not on a wall).
- Floor = every non-wall cell inside the player's walkable region; cells outside it are "outside" and
  rendered as background.
- `GameState` holds the level, the current player position, the current box set, and a history stack of
  steps (`direction`, `pushed: bool`) plus a redo stack. Operations: `move(direction) -> MoveOutcome`
  (`MOVED`, `PUSHED`, `BLOCKED`), `undo()`, `redo()`, `restart()`, properties `moves`, `pushes`,
  `is_solved`, `lurd` (history as LURD). A new move after an undo clears the redo stack. A blocked move
  changes nothing and is not counted.
- Counters follow the standard convention: `moves` = steps in the current history (undo decreases it),
  `pushes` = pushing steps in the current history.
- Win: every box is on a goal.
- LURD: `l u r d` for walking steps, `L U R D` for pushes. `lurd.replay(level, text)` returns the final state
  or raises on an illegal or mismatched step (a lowercase step that would push, or uppercase that would not).
- Canonical level hash (used as the save key, see 9.1): rows converted to XSB, `-`/`_` → space, trailing
  spaces stripped from every row, leading and trailing empty rows removed, joined with `\n`, UTF-8 encoded,
  SHA-256, written as `"sha256:<hex>"`. Defined in `docs/formats.md` so Godot computes the same value.

### 7.3 Formats (`formats/`)

- **XSB/SOK reader**: one or many levels per file; levels separated by non-board lines; `Title:`/`Author:`/
  `Comment:` metadata lines; `;` comments; run-length encoding (`4#`, `3-`) and `|` row separators accepted.
- **XSB writer**: plain XSB, one level or a collection with `Title:` lines.
- **Legacy reader** (the text format of Sokoban-LAMA): `X` → `#`, `*` → `$`, `.`, `@`, space. Auto-detection treats
  a file as legacy when it contains `X` and no `#`; `--format legacy|xsb|json` overrides detection.
- **JSON pack** (canonical bundled format, section 9.2), reader and writer.
- `load_any(path) -> Pack`: single entry point used by the CLI, the game and the benchmark. A single-level
  file becomes a one-level pack whose id is derived from the file name.
- `alexvolkihar-sokoban convert IN OUT` converts between the three formats.

### 7.4 Solver (`solver/`)

- Public API (frozen in plan Phase 1, Task 3): `solve(level, *, boxes=None, player=None, limits=SolveLimits(),
  mode="optimal", should_stop=None, on_progress=None) -> SolveResult`. Starting `boxes`/`player` allow
  solving from a mid-game state (hints).
- `SolveLimits(time_s: float = 10.0, max_nodes: int = 1_000_000)`; both limits are always enforced.
- `SolveResult(status, lurd, pushes, moves, nodes_expanded, nodes_generated, elapsed_ms)` with
  `SolveStatus = SOLVED | UNSOLVABLE | LIMIT_TIME | LIMIT_NODES | CANCELLED | INVALID`.
- Search: **push-based** A*. A state is the box set plus the player's normalised position (the top-left-most
  cell of the region the player can reach without pushing). Successors are single pushes the player can
  reach. Cost is pushes; ties are broken by walking moves; the reconstructed LURD includes the walks.
  `mode="optimal"` uses an admissible heuristic and returns a push-optimal solution (moves are not
  guaranteed minimal). `mode="fast"` uses weighted A* (or greedy best-first) for quick non-optimal answers.
- Heuristic: lower bound from per-goal push distances (precomputed by reverse BFS of pulls). Minimum-cost
  box–goal matching is the target; sum of per-box minimum distances is the acceptable first version.
- Deadlocks: dead squares (cells from which a box can never reach any goal, precomputed), freeze deadlocks
  (a box blocked on both axes off a goal, including 2×2 blocks of boxes/walls). A start state that is already
  deadlocked returns `UNSOLVABLE` immediately.
- State keys: the box set as an integer bitmask (bit = cell index) updated incrementally with XOR on each push,
  combined with the normalised player cell. This is exact Zobrist-style hashing (see decisions). Parent
  pointers are stored per state rather than full paths, so memory grows with states, not with path length.
- Exhausting the open set returns `UNSOLVABLE` (a proof under the deadlock rules, which are sound).
- `should_stop()` is polled at least every 1,000 expansions for cancellation from the UI thread.
- Acceptance: every First steps level is solved and every hand-made unsolvable test level (`sealed`,
  `divide`, `bend`) is reported `UNSOLVABLE`, each within 5 s on CI; solutions replay to a solved state through `core.lurd`.

### 7.5 Scoring (`scoring/`)

- `Par` per level: `pushes`, `moves`, `lurd`, from the solver's push-optimal solution, precomputed and stored
  in the pack JSON (`par` may be `null` when the solver hit its limits).
- Stars for a non-assisted completed run:
  - 3 stars: `pushes <= par.pushes` and `moves <= par.moves`;
  - 2 stars: `pushes <= ceil(1.25 * par.pushes)`;
  - 1 star: otherwise, or when `par` is `null`.
  Beating `par.moves` is possible (the par is push-optimal, not move-optimal) and earns a "better than par"
  badge.
- A run is **assisted** when a hint was used or the solver replay was watched during it. Assisted
  completions mark the level completed but do not update bests or stars.
- `LevelRecord` keeps `completed`, `stars` (max ever), `best_moves` (moves, pushes, lurd), `best_pushes`
  (pushes, moves, lurd), `best_time_ms`, `plays`, `first_completed_at`. Bests are tracked independently.

### 7.6 Persistence (`persistence/`)

- Data directory: `platformdirs.user_data_dir("alexvolkihar-sokoban", appauthor=False)`, overridable with the
  environment variable `ALEXVOLKIHAR_SOKOBAN_HOME` or the CLI flag `--data-dir`.
- Files: `settings.json`, `progress.json`, `session.json`, `generated.json` (user's generated levels, a pack),
  `benchmarks/<run_id>.json|.csv`, `levels/` (drop-in `.xsb`/`.sok`/`.json` files shown as a "Custom" pack).
- Every file carries `"format"` and `"version"`. Loading runs registered migrations `vN → vN+1` up to the
  current version. A file with a newer version than the app understands is left untouched and the app runs
  with defaults (read-only for that file) and a warning.
- Writes are atomic (write to `*.tmp` in the same directory, `fsync`, `os.replace`).
- A corrupt or schema-invalid file is renamed `<name>.corrupt-<UTC timestamp>.json`, a warning is logged and
  shown once, and defaults are used.
- The in-progress session is saved on pause, on quitting the game scene, on window close, and every 10 s of
  play. It stores the move history as LURD plus the redo stack, so resuming replays it through `core`.

### 7.7 Benchmark (`benchmark/`)

- Suites in `data/benchmarks/suites.json`: `quick` (the 12 First steps levels, a few seconds on a laptop),
  `standard` (First steps, 8 generated medium levels and the first 40 Boxoban hard levels), `stress`
  (`bench-extra`: generated hard, unsolvable and very large levels, plus all 100 Boxoban levels; limit hits
  are expected results, not failures). Each suite fixes its `SolveLimits`.
- The runner solves levels sequentially in-process with `tracemalloc` on (peak bytes per level), and records
  status, pushes, moves, nodes expanded/generated, elapsed ms and peak memory. A level is never retried.
- Machine info: OS and version (WSL detected via `/proc/version`), architecture, CPU model (Linux
  `/proc/cpuinfo`, macOS `sysctl -n machdep.cpu.brand_string`, Windows `platform.processor()`), logical CPU
  count, total RAM when available without extra dependencies, Python implementation and version,
  `pygame-ce` version when installed, app version, solver version. No hostname or user name (results are
  meant to be shared).
- Summary: solved count, total time, nodes expanded per second (the headline "machine score").
- Export JSON (canonical, schema-validated) and CSV (one row per level). `compare A B` shows per-level and
  total deltas (time %, nodes) and flags status changes.
- CLI: `alexvolkihar-sokoban bench [--suite quick] [--out FILE] [--csv FILE]`, `alexvolkihar-sokoban bench compare A B`.
- UI: suite picker, live progress (current level, elapsed), cancel, results table, machine panel, export
  buttons, compare against a previous run stored in the data directory.

### 7.8 Generator (`generator/`)

- Seeded and reproducible (`random.Random(seed)`).
- Algorithm: carve a random connected room inside a `W×H` rectangle, place `n` goals with boxes on them, then
  play backwards (random player walks and pulls) for a number of steps; the resulting box positions become
  the start. Validate with the solver (`mode="optimal"`, limits from the preset); accept when solved with at
  least `min_pushes` pushes; otherwise retry up to a bounded number of attempts.
- Presets: easy (7×7, 2 boxes, ≥ 6 pushes), medium (8×8, 3 boxes, ≥ 12), hard (10×9, 4 boxes, ≥ 20).
- The accepted level stores its `par` and its seed; it is appended to `generated.json` so progress and scores
  work like any pack.
- CLI: `alexvolkihar-sokoban generate --preset medium --seed 42 [--out FILE]`.

### 7.9 User interface (`ui/`)

- Window 1024×768 by default, resizable (minimum 640×480), optional fullscreen. The board is scaled with an
  integer tile size to fit below the HUD and centred.
- Scenes, all reachable by keyboard; mouse clicks on menu items are a bonus:
  - **Main menu**: Continue (resumes the saved session or the last played level), Level select, Random level
    (generator), Benchmark, Themes, Settings, Credits, Quit.
  - **Level select**: packs on the left (First steps, Boxoban, Generated, Custom), a level grid with
    thumbnails on the right; each tile shows completion, stars and best moves/pushes; the pack header shows
    "completed X / N".
  - **Game**: HUD with pack/level name, moves, pushes, time, par (pushes/moves) and key reminders. Undo/redo
    unlimited; restart requires pressing R twice within 1.5 s; hint (H) runs the solver in a worker thread
    from the current state and highlights the next push (box and arrow) and the walk to it, or says the
    position is a dead end ("undo"); "watch the solver" plays the par solution (or a freshly solved one) from
    the start with play/pause and speed controls. Optional move animation (off / normal / fast).
  - **Pause** overlay: resume, restart, watch solution, level select, main menu.
  - **Victory** overlay: moves, pushes, time, stars, new-record badges, next level / replay / level select.
  - **Themes**: list of themes with a live preview of a sample board; Enter applies and saves.
  - **Settings**: language, animation speed, show timer, fullscreen, keybindings (opens the rebinding scene),
    reset progress (with confirmation).
  - **Keybindings**: list of actions; select one and press a key to rebind; reset to defaults.
  - **Benchmark** (7.7), **Random level** (preset and optional seed, then play), **Credits**.
- Input actions: up, down, left, right, undo, redo, restart, hint, pause, confirm, back. Defaults: arrows;
  WASD bound by physical scancode (so it is ZQSD on AZERTY keyboards); undo `U`/`Backspace`/`Ctrl+Z`; redo
  `Y`/`Ctrl+Y`; restart `R`; hint `H`; pause `Esc`/`P`; confirm `Enter`/`Space`; back `Esc`. Bindings are
  stored as strings `[ctrl+]key:<pygame key name>` or `[ctrl+]scan:<SDL scancode>`.
- Language: French and English, chosen in settings, default from the system locale (French when the locale
  starts with `fr`, English otherwise). Strings are written inline with `t(en, fr)` so tasks never share a
  catalogue file.
- Fonts: pygame's default font only (no external font files to license).
- Solver work in the UI always runs in a worker thread with a cancel token; the UI never blocks.

### 7.10 Themes (`ui/themes/`)

- `Theme` protocol: `id`, `name`, `tile(kind: TileKind, size: int) -> Surface` (cached per size),
  `background` colour, and a small UI palette (`text`, `muted`, `accent`, `panel`, `good`, `bad`).
  `TileKind` = `FLOOR`, `WALL`, `GOAL`, `BOX`, `BOX_ON_GOAL`, `PLAYER`, `PLAYER_ON_GOAL`, `OUTSIDE`.
- Bundled themes:
  - `kenney`: sprites from the Kenney Sokoban pack (CC0); `BOX_ON_GOAL` and `PLAYER_ON_GOAL` are
    composited procedurally (crate tinted plus a goal marker; player over the goal sprite).
  - `classic`: flat colours, procedurally drawn.
  - `neon`: dark background, glowing outlines, procedurally drawn.
  - `contrast`: colour-blind-safe (Okabe–Ito palette) and shape-coded: goals are rings, boxes are squares
    with a cross, a box on a goal shows a check mark, so no state relies on colour alone.
- Default theme: `kenney`.

## 8. Levels and content

| Pack id | Content | Source / licence |
|---|---|---|
| `first-steps` | 12 hand-made beginner levels (1 to 4 boxes) | Alexis MABANZA, MIT |
| `bench-extra` | generated levels (seeds kept), 3 levels unsolvable on purpose and 1 very large level; hidden, benchmarks only | Alexis MABANZA, MIT |
| `microban-1` | Microban (155 levels) by David W. Skinner; **not shipped** (licence, see 12) | — |
| `boxoban-hard` | Boxoban by DeepMind: the first 100 puzzles of `hard/000.txt` (10×10, 4 boxes) | Apache-2.0, full text and requested citation in `data/levels/boxoban-hard.LICENSE.txt` (see 12) |
| `generated` | levels made by the player's generator, stored in the user data dir | generated |
| `custom` | files dropped in `<data dir>/levels/` | the player's own |

- No level of the original game is bundled; the unsolvable and very large levels used by the tests and the
  `stress` suite are hand-made.
- Microban levels are bundled only after checking each level's own notes; any level credited to another
  author is excluded.
- `par` is precomputed with `alexvolkihar-sokoban annotate` (limits: 60 s / 5,000,000 nodes per level) and stored in
  the pack file. Levels the solver cannot solve keep `par: null`.

## 9. Data formats (portable; documented in `docs/formats.md`, schemas in `schemas/`)

All JSON files are UTF-8, with a top-level `"format"` string and an integer `"version"` (1 at launch).
Durations are integer milliseconds, sizes integer bytes, timestamps ISO-8601 UTC strings.

### 9.1 Level identity

A level is identified in saves by its canonical hash (7.2). Pack id + level id are stored alongside for
display, but the hash is the key, so re-ordering or re-titling a pack never loses scores, and editing a
level's layout naturally starts a fresh record.

### 9.2 Pack (`alexvolkihar-sokoban/pack`)

```json
{
  "format": "alexvolkihar-sokoban/pack", "version": 1,
  "id": "first-steps", "title": "First steps", "author": "Alexis MABANZA",
  "license": "MIT (see LICENSE)", "source": "https://github.com/Alexvolkihar/alexvolkihar_sokoban", "hidden": false,
  "levels": [
    { "id": "2", "title": "Two crates",
      "rows": ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"],
      "par": { "pushes": 6, "moves": 14, "lurd": "...", "solver": "push-astar/1" } }
  ]
}
```

(The par values above are illustrative.) A single level file (`alexvolkihar-sokoban/level`) has the same fields as one
entry of `levels` plus `format`/`version`.

### 9.3 Settings (`alexvolkihar-sokoban/settings`)

`language` (`"fr"`/`"en"`), `theme`, `fullscreen`, `window` (`[w, h]`), `animation` (`"off"|"normal"|"fast"`),
`show_timer`, `keybindings` (`{action: [binding strings]}`).

### 9.4 Progress (`alexvolkihar-sokoban/progress`)

`levels`: `{ "<level hash>": { "pack_id", "level_id", "completed", "stars", "plays", "first_completed_at",
"best_moves": {"moves","pushes","lurd"} | null, "best_pushes": {...} | null, "best_time_ms": int | null } }`,
plus `last_played`: `{"pack_id", "level_id", "level_hash"} | null`.

### 9.5 Session (`alexvolkihar-sokoban/session`)

`{ "pack_id", "level_id", "level_hash", "lurd", "redo_lurd", "elapsed_ms", "assisted", "saved_at" }`; the file
is deleted when the level is won or abandoned via "restart"/"level select".

### 9.6 Benchmark run (`alexvolkihar-sokoban/benchmark`)

`run_id`, `created_at`, `app_version`, `solver` (`name`, `version`, `mode`), `machine` (7.7), `suite`
(`id`, `limits`), `measure` (`"tracemalloc"`), `results` (per level: `pack_id`, `level_id`, `level_hash`,
`status`, `pushes`, `moves`, `nodes_expanded`, `nodes_generated`, `elapsed_ms`, `peak_mem_bytes`),
`summary` (`solved`, `total`, `total_ms`, `nodes_per_s`).

### 9.7 Conformance vectors

`tests/vectors/moves.json`: list of cases `{rows, input (LURD or plain udlr), expected: {player, boxes, moves,
pushes, solved, blocked_steps}}` and `tests/vectors/hash.json`: `{rows, hash}`. The Python tests run them; the
Godot port must pass the same files.

## 10. CLI

```
alexvolkihar-sokoban                       # GUI, main menu
alexvolkihar-sokoban play PATH [--level ID]
alexvolkihar-sokoban solve PATH [--level ID] [--time-limit S] [--max-nodes N] [--mode optimal|fast]
alexvolkihar-sokoban convert IN OUT [--format ...]
alexvolkihar-sokoban annotate PACK.json [--time-limit S] [--max-nodes N]
alexvolkihar-sokoban bench [--suite ID] [--out FILE] [--csv FILE] | bench compare A B
alexvolkihar-sokoban generate [--preset P] [--seed N] [--out FILE]
global: --data-dir DIR, --version
```

`python -m alexvolkihar_sokoban` is equivalent. `alexvolkihar-sokoban play old-level.txt` plays a file in the
legacy text format.

## 11. Quality

- TDD on every non-UI module; UI scenes get smoke tests under `SDL_VIDEODRIVER=dummy` (construct, feed
  events, render a frame, assert scene transitions).
- Ruff (lint + format), mypy `--strict` on `core`, `formats`, `solver`, `scoring`, `persistence`,
  `benchmark`, `generator`; UI is type-hinted but checked non-strict.
- GitHub Actions: lint + type check on 3.13; tests on Ubuntu for 3.11–3.14, and on Windows and macOS for
  3.13 (catches path and font issues).
- Coverage target ≥ 85 % on non-UI packages.

### 11.1 README media (screenshots and demo video)

- Browser recorders (Playwright etc.) cannot capture a pygame window, so media are produced by the game
  itself: `scripts/capture.py` runs the app headless (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`),
  drives scenes with scripted input events through the normal input layer, and saves the display surface
  with `pygame.image.save` (PNG screenshots) or appends frames for the video.
- Video: frames encoded to H.264 MP4 (`yuv420p`, ≤ 30 s, ≤ 8 MB) with `imageio` + `imageio-ffmpeg`
  (dev-only extra `media`, never a runtime dependency); the GIF fallback is downscaled (≈ 640 px wide,
  12–15 fps, ≤ 5 MB) with a generated palette.
- Screenshots: main menu, level select, gameplay (mid-level), the four themes side by side (or one image
  each), benchmark results with the machine panel, victory screen. Stored in `docs/media/`.
- Storyboard: follow the owner's starred video skill `latent-spaces/brag` (brag-slim variant) as guidance for
  a short "brag" demo: hook in the first seconds (a solved level snapping into place), then menu → level
  select → play with undo → hint → "watch the solver" → theme switch → benchmark table → end card with the
  project name, its author and its origin.
- Deterministic: fixed seed, fixed theme order, fixed window size (1280×720), so re-running the script
  reproduces the same media.
- The README embeds the GIF inline and links the MP4 (GitHub renders an uploaded MP4 inline when it is
  attached to the README via a URL; the repository-hosted file is the fallback link).

## 12. Licensing

- **Code and own levels**: MIT, `Copyright (c) 2026 Alexis MABANZA` (`LICENSE`, declared in
  `pyproject.toml`). The repository ships only the owner's own work plus the credited third-party assets
  below; the original project, its code and its levels stay in their own repository. GitHub Actions minutes
  are free for public repositories, so the CI matrix is not constrained.
- **Kenney sprites**: the four images are from Kenney's "Sokoban" pack (kenney.nl/assets/sokoban), licence
  CC0 1.0. Recorded in `data/themes/kenney/LICENSE.txt`; credit given anyway.
- **Microban**: by David W. Skinner. Secondary sources quote his terms as "these sets may be freely
  distributed provided they remain properly credited"; his original page (users.bentonrea.com/~sasquatch)
  is offline. Gate (plan Task 11): Microban is committed only if the downloaded collection carries
  Skinner's own copyright/distribution notice (header of his `.txt`/`.sok` file), copied verbatim into the
  pack's `license` field with its source URL. Otherwise the pack is left out, the task reports it as
  blocked, and every feature still works with the other bundled packs, generated levels and custom imports
  (benchmark suites skip missing packs with a warning). The credit goes in the pack's `author`/`license`
  fields, the credits screen and the README.
- **Microban gate outcome (Task 11, 2026-11-05)**: blocked. Skinner's own file (`m1`, archived on the Wayback
  Machine) carries no notice; his archived home page says "These sets may be freely distributed provided they
  remain unchanged and credited with my name and email address", and "unchanged" conflicts with dropping the
  levels credited to other sets (Original, Boxxle, Revenge) and with the JSON conversion. Owner decision needed.
- **Boxoban** (`boxoban-hard`): DeepMind's boxoban-levels repository, Apache-2.0 (licence file checked in the
  downloaded repository). Pack metadata names the authors, the source, the selection, the change (format
  conversion) and the citation their README requests; the licence text ships next to the pack.
- **pygame-ce**: LGPL-2.1-or-later, used as an unmodified dependency, compatible with MIT.

## 13. Decisions made without the user

Each can be revisited; none is hard to change before plan Phase 2 starts unless noted.

1. **pygame-ce instead of pygame** — pygame has no 3.14 wheel (the original README's problem); pygame-ce
   does, same API.
2. **Python ≥ 3.11** — `StrEnum`, `Self`, better error messages; 3.10 is near end of life.
3. **`src/` layout, package `alexvolkihar_sokoban`, hatchling build, entry point `alexvolkihar-sokoban`** — standard,
   keeps tests honest about installed imports.
4. **Original code not shipped** — it stays in the original repository (it was first kept in `legacy/`,
   removed on 2026-11-06).
5. **Row/column coordinates and a non-transposed display** — fixes the original mirror bug.
6. **Bundled levels stored as JSON packs, not `.xsb`** — one format that carries metadata and par, trivially
   read by Godot; `.xsb` stays fully supported for import/export.
7. **Saves keyed by canonical level hash** — robust to pack edits and reordering.
8. **Push-optimal solver** (pushes first, moves as tie-break) — the standard Sokoban optimality for solvers;
   move-optimal search is much more expensive.
9. **Exact integer bitmask keys instead of random 64-bit Zobrist keys** — in Python an arbitrary-size int is
   hashable, exact (no collision handling), compact and updated incrementally by XOR like Zobrist; this keeps
   the benefit the owner asked for without collision risk.
10. **Memory bounded by node count + time** — portable, deterministic; real memory is measured
    (`tracemalloc`) in benchmarks rather than used as a limit.
11. **Stars against the solver's par; assisted runs give completion only** — keeps scores meaningful.
12. **No progression locks** — puzzle collections are usually free-choice; fewer frustrations.
13. **Restart needs a double press of R** instead of a confirmation dialog — fast but accident-proof.
14. **Bilingual UI (FR/EN) with inline `t(en, fr)`** — the project is public, the owner is French; inline
    strings avoid a shared catalogue file that parallel tasks would fight over.
15. **Themes: kenney (default), classic, neon, contrast** — only CC0 or procedural art; `contrast` covers
    the colour-blind requirement with shapes.
16. **No sound, no editor, no web build in this phase** — scope control.
17. **Benchmark measures with `tracemalloc` always on** — memory column always available; overhead is equal
    between runs of the same version, so comparisons stay fair. Results contain no hostname.
18. **Hand-made test levels** — the unsolvable and very large levels of the tests and the `stress` suite are
    made for this repository, not taken from the original game.
19. **Licence: MIT**, `Copyright (c) 2026 Alexis MABANZA`.
20. **Microban I only** (not Sasquatch etc.) at first — small levels suit a Python solver and new players;
    more sets can be added once their licences are checked.
21. **Runtime dependencies limited to pygame-ce and platformdirs** — no psutil; machine info comes from the
    standard library and OS files.
22. **Names**: repository and project name `alexvolkihar_sokoban` (owner's choice); Python package
    `alexvolkihar_sokoban`; command `alexvolkihar-sokoban`; JSON format ids `alexvolkihar-sokoban/<kind>`;
    data directory `alexvolkihar-sokoban`; window title "Alexvolkihar Sokoban" with the subtitle
    "remake of Sokoban-LAMA" on the main menu.
23. **Media are captured from pygame itself** (dummy video driver + `pygame.image.save`, encoded with
    `imageio-ffmpeg` as a dev-only extra) — the only reliable way to film a pygame window in CI-like
    headless conditions.

## 14. Follow-up phase: Godot remake (not planned in detail here)

- Reimplement `core` rules in GDScript (or C#) against `tests/vectors/*.json` and `docs/formats.md`.
- Reuse `data/levels/*.json`, the save formats (settings, progress, session) and the canonical hash, so a
  player's progress could be imported.
- The Python solver stays the reference for par computation; a native solver in Godot is optional.

## 15. Left to the builder

Exact widget look, menu animations, HUD layout details, colour values within the theme rules, internal
module splits inside a package, solver heuristic refinements beyond the acceptance criteria, generator
carving details, test file organisation inside each package.
