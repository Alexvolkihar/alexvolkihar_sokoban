# Data formats

This is the reference for every file alexvolkihar_sokoban reads or writes. It is written for anyone who
reimplements the game, first of all the planned Godot port: a port that follows this page reads the same
level packs, computes the same level identities and opens the same saves.

The Python package is the reference implementation. Where this page and the code disagree, the conformance
vectors (section 11) decide, then the code.

The JSON Schemas live in [`schemas/`](../schemas). `tests/test_schemas.py` checks every example on this page
against its schema, loads the level examples and replays their solutions, so the examples stay true.

## Contents

1. [Conventions](#1-conventions)
2. [Boards](#2-boards)
3. [Level identity: the canonical hash](#3-level-identity-the-canonical-hash)
4. [Moves and LURD](#4-moves-and-lurd)
5. [Text level files: XSB, SOK and the legacy format](#5-text-level-files-xsb-sok-and-the-legacy-format)
6. [JSON packs and levels](#6-json-packs-and-levels)
7. [Par and stars](#7-par-and-stars)
8. [The data directory: settings, progress, session](#8-the-data-directory-settings-progress-session)
9. [Benchmarks](#9-benchmarks)
10. [Generated levels](#10-generated-levels)
11. [Conformance vectors](#11-conformance-vectors)
12. [Versioning and migrations](#12-versioning-and-migrations)

## 1. Conventions

- Text files are UTF-8. Readers accept a leading byte order mark and CRLF or CR line ends; writers emit
  UTF-8 without a BOM and LF line ends.
- Every JSON file is an object whose first keys are `"format"` (`"alexvolkihar-sokoban/<kind>"`) and
  `"version"` (an integer, `1` for every format today).
- Coordinates are `[row, col]`, row 0 at the top, column 0 on the left. They are never transposed.
- Durations are integer milliseconds (`*_ms`), sizes integer bytes (`*_bytes`), timestamps ISO-8601 UTC
  strings with second precision: `2026-11-05T14:03:22Z`.
- A level is identified in saves by its canonical hash, `"sha256:<64 lowercase hex digits>"` (section 3).
  Pack ids and level ids are stored next to it for display only.

| Kind | `format` | Schema |
|---|---|---|
| Level pack | `alexvolkihar-sokoban/pack` | `schemas/pack.schema.json` |
| Single level | `alexvolkihar-sokoban/level` | `schemas/level.schema.json` |
| Settings | `alexvolkihar-sokoban/settings` | `schemas/settings.schema.json` |
| Progress | `alexvolkihar-sokoban/progress` | `schemas/progress.schema.json` |
| Session (game in progress) | `alexvolkihar-sokoban/session` | `schemas/session.schema.json` |
| Benchmark run | `alexvolkihar-sokoban/benchmark` | `schemas/benchmark.schema.json` |
| Benchmark suites | `alexvolkihar-sokoban/benchmark-suites` | none (bundled data, section 9.1) |
| Conformance vectors | `alexvolkihar-sokoban/vectors-moves`, `…/vectors-hash` | none (test data, section 11) |

## 2. Boards

A board is a list of rows written with the standard XSB symbols:

| Symbol | Meaning |
|---|---|
| `#` | wall |
| `@` | player |
| `+` | player on a goal |
| `$` | box |
| `*` | box on a goal |
| `.` | goal |
| space, `-`, `_` | floor (or outside, see below) |

Any other character makes the level invalid. Rows may have different lengths; the board width is the
length of the longest row after normalisation (section 3).

A level is valid when:

1. there is exactly one player;
2. there is at least one box;
3. the number of boxes equals the number of goals;
4. the player's region, flood-filled from the player through every non-wall cell in the four directions,
   never leaves the grid (the player is enclosed by walls);
5. every box and every goal lies inside that region;
6. the boxes are not already all on goals.

The cells of that region are the **floor**. Non-wall cells outside it are **outside**: they are drawn as
background and written as spaces.

A reader reports an invalid level with a human-readable reason and skips it; it never crashes on one.

## 3. Level identity: the canonical hash

The canonical text of a level is its starting position:

1. written as XSB rows, one character per cell, using the symbols above, with every floor or outside cell
   written as a space (so `-` and `_` become spaces);
2. trailing spaces removed from every row;
3. empty rows at the top and at the bottom removed (empty rows in the middle stay);
4. rows joined with a single LF (`\n`), no LF at the end.

The level hash is `"sha256:" + hex(SHA-256(UTF-8 bytes of the canonical text))`, hex in lowercase.

Leading spaces are kept: two levels that differ only by indentation are different texts. Text readers
remove the indentation common to all rows of a level before building it (section 5), so a level indented
in a file still hashes like the same level written flush left.

Worked example: level 2 of the bundled First steps pack, "Two crates". Its canonical text is the six rows
below, seven characters each, joined by five LFs: 47 bytes, no LF at the end.

<!-- canonical-hash: sha256:ae18fe77b0c8bc6d2978a80b84c06daf4eb1ad4f51d2c45f81cb18a7796c676c -->
```text
#######
#.   .#
#  $  #
# $   #
#@    #
#######
```

`printf '#######\n#.   .#\n#  $  #\n# $   #\n#@    #\n#######' | sha256sum` prints the same digest. The same
level written `["#######  ", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######", ""]` (trailing spaces, a
final empty row) has the same canonical text and the same hash. More cases are in `tests/vectors/hash.json`.

Editing a layout changes the hash, so the edited level starts with a fresh record; re-ordering or renaming
levels in a pack keeps every record.

## 4. Moves and LURD

Rules:

- The player moves one cell up, down, left or right.
- Moving into a wall, or into a box whose next cell is a wall or another box, is **blocked**: nothing
  changes and nothing is counted.
- Moving into a box whose next cell is free pushes the box one cell. Boxes are never pulled.
- `moves` is the number of steps in the current history, `pushes` the number of those steps that pushed a
  box. Undo removes the last step (and its counts); redo replays it. A new move after an undo clears the
  redo stack.
- The level is solved when every box is on a goal.

**LURD** writes a history as one character per step: `l u r d` for a walking step left, up, right or down,
`L U R D` for a step that pushes a box. Readers ignore whitespace inside a LURD string. When a LURD string
is replayed, a blocked step is an error, and so is a mismatched case: a lower-case step that would push, or
an upper-case step that would not. The par of the level above, `rUURRulLddrrrU`, is 14 moves and 6 pushes.

A saved game stores two LURD strings (section 8.4): the history, replayed from the start, and the redo
stack, next redo first. To restore it, replay the history, play the redo string, then undo as many steps as
the redo string holds.

## 5. Text level files: XSB, SOK and the legacy format

### 5.1 Reading a file

Before parsing, a reader removes a leading BOM, turns CRLF and CR into LF, expands tabs to the next multiple
of 8 columns and strips trailing spaces from every line. A file that holds a NUL byte (binary) or is not
valid UTF-8 is rejected as a whole.

The format is chosen by `--format` when given (`xsb`, `legacy`, `json`), otherwise detected:

1. JSON when the extension is `.json` or the text (after a BOM and leading whitespace) starts with `{`;
2. legacy when the text contains `X` and no `#`;
3. XSB otherwise.

### 5.2 XSB and SOK

One file holds one level or many (`.xsb`, `.sok` and `.txt` are read the same way).

- A **board line** holds only `# @ + $ * . - _ space`, digits and `|`, and at least one of `# @ + $ * .`.
- Consecutive board lines form one level. Any other line, including an empty one, ends the current level.
- **Run-length encoding**: a number repeats the next character (`4#` is `####`, `3-` is three floor
  cells); `|` starts a new row inside a line. `7#|#.@-#-#|7#` is three rows.
- `Title:`, `Author:` and `Comment:` lines (key case-insensitive, value trimmed) describe the level just
  above them, or the whole pack when no board came yet. The first value of each key wins. Other lines,
  `;` comments included, are ignored.
- Each level's rows are **dedented**: `-` and `_` become spaces, then the indentation common to every
  non-empty row is removed.
- Level ids are the 1-based position of the board in the file, counting invalid boards too: when level 2
  is broken, the valid ones are `"1"` and `"3"`, and fixing level 2 later never renumbers the others.
- An invalid level becomes a warning naming the pack, the level number and the line of its first row; the
  valid levels still load. A file with no valid level is an error.
- The pack id is the file name without extension; its title is the header `Title:` or that id.

The XSB writer prints an optional `Title:`/`Author:` header, then each level as its canonical text
followed by its own `Title:`, `Author:` and `Comment:` lines, levels separated by an empty line.

### 5.3 The legacy format

The legacy format is the one of Sokoban-LAMA (2022), the game this one remakes: one level per file, with its
own symbols. It has no symbol for a box or the player standing on a goal.

| Legacy | XSB | Meaning |
|---|---|---|
| `X` | `#` | wall |
| `*` | `$` | box |
| `.` | `.` | goal |
| `@` | `@` | player |
| space | space | floor |

A legacy file becomes a one-level pack whose level id is `"1"`, read with the same line clean-up and
dedent as XSB. Example, the level of the worked example in section 3:

```text
XXXXXXX
X.   .X
X  *  X
X *   X
X@    X
XXXXXXX
```

A level whose box and goal counts differ is rejected as invalid, as in every other format.

### 5.4 Custom levels

Files dropped in `<data dir>/levels/` with the extensions `.xsb`, `.sok`, `.txt` or `.json` form the
**Custom** pack (id `custom`). A custom level id is `<file stem>/<level id in the file>`, for example
`mine/3`. A second file with the same stem is skipped with a warning, and a broken file only produces a
warning.

## 6. JSON packs and levels

### 6.1 Pack

The bundled packs (`data/levels/*.json` in the package), the user's generated levels (`generated.json`) and
exported packs use this format. Example (two levels of the bundled `first-steps` pack, abridged):

<!-- schema: pack -->
```json
{
  "format": "alexvolkihar-sokoban/pack",
  "version": 1,
  "id": "first-steps",
  "title": "First steps",
  "author": "Alexis MABANZA",
  "license": "MIT (see LICENSE)",
  "source": "https://github.com/Alexvolkihar/alexvolkihar_sokoban",
  "hidden": false,
  "levels": [
    {
      "id": "1",
      "title": "First push",
      "rows": ["########", "#   #  #", "# $   .#", "#@ ##  #", "########"],
      "par": { "pushes": 4, "moves": 5, "lurd": "uRRRR", "solver": "push-astar/1" }
    },
    {
      "id": "2",
      "title": "Two crates",
      "rows": ["#######", "#.   .#", "#  $  #", "# $   #", "#@    #", "#######"],
      "par": { "pushes": 6, "moves": 14, "lurd": "rUURRulLddrrrU", "solver": "push-astar/1" }
    }
  ]
}
```

| Field | Rule |
|---|---|
| `id` | required, non-empty; unique among loaded packs. `generated` and `custom` are reserved. |
| `title` | required (may be empty); shown in the level list. |
| `author`, `license`, `source` | optional strings, shown in the credits. |
| `hidden` | optional, default `false`; a hidden pack loads but is not listed in level select. |
| `levels` | required list of level entries. |
| `levels[].id` | required, non-empty, unique in the pack; never renumbered. |
| `levels[].title`, `author`, `comment` | optional strings. |
| `levels[].rows` | required, at least one row, XSB symbols only (section 2). |
| `levels[].par` | optional, `null` or a par object (section 7). |
| `levels[].seed` | optional integer or `null`: the generator seed (section 10). |

Readers accept extra keys and ignore them. A broken level entry (invalid board, wrong type, duplicate id)
is skipped with a warning when the pack is loaded by the game; the `annotate` command refuses such a pack.
Writers emit each level's rows as its canonical text, `"title"` always, `"par"` always (possibly `null`),
and `author`, `comment` and `seed` only when set.

### 6.2 Single level

A single-level file has the fields of one pack entry plus `format`/`version`. It loads as a one-level pack
named after the file. Example (a generated level exported on its own):

<!-- schema: level -->
```json
{
  "format": "alexvolkihar-sokoban/level",
  "version": 1,
  "id": "easy-42",
  "title": "",
  "rows": ["#######", "#.  $ #", "# ##@ #", "# ### #", "#   # #", "#   $.#", "#######"],
  "par": { "pushes": 8, "moves": 21, "lurd": "ruLLLrrdrdddLLulldRRR", "solver": "push-astar/1" },
  "seed": 42
}
```

### 6.3 Bundled packs

| Id | Content | Licence |
|---|---|---|
| `first-steps` | 12 hand-made beginner levels, ids `"1"`…`"12"` | MIT, `LICENSE` |
| `boxoban-hard` | the first 100 puzzles of DeepMind's Boxoban `hard/000.txt`, ids `"1"`…`"100"` | Apache-2.0, `data/levels/boxoban-hard.LICENSE.txt` |
| `bench-extra` | 16 generated levels (`medium-1`…`medium-8`, `hard-1`…`hard-8`, seeds kept), 3 levels unsolvable on purpose and 1 very large level; hidden, in `data/benchmarks/extra.json`, used by benchmarks only | MIT, `LICENSE` |

## 7. Par and stars

The **par** of a level is the solver's solution, stored in the pack so nothing is solved at play time:

```text
"par": { "pushes": int, "moves": int, "lurd": "LURD string", "solver": "push-astar/1" }
```

- The solver is a push-based A* that minimises **pushes**; ties are broken by walking moves. The par is
  therefore **push-optimal**, and its move count is not guaranteed minimal: a player can solve a level in
  fewer moves than the par.
- `lurd` replays from the start to a solved position with exactly `pushes` pushes and `moves` moves.
- `solver` names the algorithm and its version (`push-astar/1`); a port keeps the Python solver as the par
  reference and never rewrites pars it did not compute itself.
- `par` is `null` when the solver hit its limits, or proved the level unsolvable.

Stars for a completed run that was not assisted (no hint, no solver replay):

| Stars | Condition |
|---|---|
| 3 | `pushes <= par.pushes` and `moves <= par.moves` |
| 2 | `pushes <= ceil(1.25 × par.pushes)`, computed in integers as `(5 × par.pushes + 3) // 4` |
| 1 | otherwise, or when `par` is `null` |

`moves < par.moves` earns the "better than par" badge. An assisted run marks the level completed but
records 0 stars and updates no best.

## 8. The data directory: settings, progress, session

### 8.1 Location and files

The data directory is `platformdirs.user_data_dir("alexvolkihar-sokoban", appauthor=False)` (for example
`~/.local/share/alexvolkihar-sokoban` on Linux), unless the `ALEXVOLKIHAR_SOKOBAN_HOME` environment
variable or the `--data-dir` option names another one.

| Path | Content |
|---|---|
| `settings.json` | settings (8.2) |
| `progress.json` | records and last level played (8.3) |
| `session.json` | the game in progress (8.4), absent when there is none |
| `generated.json` | the user's generated levels, a pack with id `generated` (section 10) |
| `levels/` | custom level files (5.4) |
| `benchmarks/<run_id>.json`, `.csv` | benchmark runs (9.2) |

Every JSON file is written atomically: to a temporary file in the same directory, flushed with `fsync`,
then renamed over the target. Reading follows these rules:

- missing file: defaults;
- invalid JSON, a root that is not an object, a wrong `format`, a missing or invalid `version`, or a failed
  migration: the file is renamed `<name>.corrupt-<YYYYMMDDTHHMMSSZ>.json` (with `-1`, `-2`… on a clash), a
  warning is shown once, and defaults are used;
- a file that exists but cannot be read: defaults, and the file is never overwritten during that session;
- `version` older than the app's: migrated in memory (section 12), written in the new version at the next
  save;
- `version` newer than the app's: the file is left untouched, the app runs with defaults and never
  overwrites it during that session, and a warning is shown;
- a failed write (read-only folder, full disk) is a warning, never a crash.

### 8.2 Settings

<!-- schema: settings -->
```json
{
  "format": "alexvolkihar-sokoban/settings",
  "version": 1,
  "language": "en",
  "theme": "kenney",
  "fullscreen": false,
  "window": [1024, 768],
  "animation": "normal",
  "show_timer": true,
  "keybindings": {
    "up": ["key:up", "scan:26"],
    "down": ["key:down", "scan:22"],
    "left": ["key:left", "scan:4"],
    "right": ["key:right", "scan:7"],
    "undo": ["key:u", "key:backspace", "ctrl+key:z"],
    "redo": ["key:y", "ctrl+key:y"],
    "restart": ["key:r"],
    "hint": ["key:h"],
    "pause": ["key:escape", "key:p"],
    "confirm": ["key:return", "key:space"],
    "back": ["key:escape"]
  }
}
```

These are the defaults. The settings reader is tolerant: an unknown key is ignored and each invalid field
falls back to its default, so a hand-edited file never locks the player out.

- `language`: `"fr"` or `"en"`. On first run it comes from the system locale.
- `theme`: a theme id; an unknown id falls back to `kenney`.
- `window`: windowed size in pixels, at least `[640, 480]`; a smaller size resets to the default.
- `animation`: `"off"`, `"normal"` or `"fast"`.
- `keybindings`: for each of the 11 actions, a list of bindings. A binding is `key:<name>` (a pygame-ce key
  name, layout-dependent, such as `key:return` or `key:u`) or `scan:<code>` (an SDL scancode, the USB HID
  usage id of the physical key: 26 is the key labelled W on a US keyboard, so `scan:26` stays on that key
  under AZERTY), optionally prefixed with `ctrl+`. A plain binding fires only without Ctrl, a `ctrl+`
  binding only with it. An action whose list is empty or invalid gets its defaults back. A port maps
  `key:` names to its own key codes and `scan:` codes to physical keys.

### 8.3 Progress

<!-- schema: progress -->
```json
{
  "format": "alexvolkihar-sokoban/progress",
  "version": 1,
  "levels": {
    "sha256:ae18fe77b0c8bc6d2978a80b84c06daf4eb1ad4f51d2c45f81cb18a7796c676c": {
      "pack_id": "first-steps",
      "level_id": "2",
      "completed": true,
      "stars": 3,
      "plays": 2,
      "first_completed_at": "2026-11-05T14:03:22Z",
      "best_moves": { "moves": 14, "pushes": 6, "lurd": "rUURRulLddrrrU" },
      "best_pushes": { "moves": 14, "pushes": 6, "lurd": "rUURRulLddrrrU" },
      "best_time_ms": 9400
    },
    "sha256:afdf47b65b6752393e6bb66d7b8cbb6c7bb5d15963bc13efc28dd28ee32ba632": {
      "pack_id": "generated",
      "level_id": "easy-42",
      "completed": true,
      "stars": 0,
      "plays": 1,
      "first_completed_at": "2026-11-05T14:10:05Z",
      "best_moves": null,
      "best_pushes": null,
      "best_time_ms": null
    }
  },
  "last_played": {
    "pack_id": "first-steps",
    "level_id": "2",
    "level_hash": "sha256:ae18fe77b0c8bc6d2978a80b84c06daf4eb1ad4f51d2c45f81cb18a7796c676c"
  }
}
```

- `levels` is keyed by level hash (section 3). `pack_id`/`level_id` follow the latest run, for display.
- The second record above is an assisted completion: completed, but no stars and no bests.
- `stars` is the best ever earned (0 to 3). `plays` counts completed runs, assisted ones included.
- `best_moves` keeps the solution with the fewest moves (fewer pushes breaks a tie), `best_pushes` the one
  with the fewest pushes (fewer moves breaks a tie); an exact tie keeps the older solution. The two are
  tracked independently and may be the same solution. `best_time_ms` keeps the strictly lowest time.
- `last_played` drives the **Continue** entry of the main menu when no session exists; `null` when nothing
  was played.
- Reading is lenient: a record whose key is not a level hash, or without `pack_id`/`level_id`, is
  skipped, and each invalid field takes its default.

### 8.4 Session

<!-- schema: session -->
```json
{
  "format": "alexvolkihar-sokoban/session",
  "version": 1,
  "pack_id": "first-steps",
  "level_id": "2",
  "level_hash": "sha256:ae18fe77b0c8bc6d2978a80b84c06daf4eb1ad4f51d2c45f81cb18a7796c676c",
  "lurd": "rUUd",
  "redo_lurd": "r",
  "elapsed_ms": 5200,
  "assisted": false,
  "saved_at": "2026-11-05T14:05:10Z"
}
```

This player walked right, pushed up twice, walked down, walked right, then undid that last step: the
history is `rUUd` (4 moves, 2 pushes) and `r` can be redone. The session is saved on pause, when leaving the game, on window
close and every 10 s of play; it is deleted when the level is won, or saved again with no move played. Here `lurd` and `redo_lurd` contain
only `l u r d L U R D` (no whitespace).

To resume: find the level by `pack_id` + `level_id` and check that its hash equals `level_hash`; when it
does not, look the hash up in every pack; when no level has that hash, discard the session. Then restore
the history as described in section 4. `assisted` carries over, so a resumed assisted attempt stays
assisted.

## 9. Benchmarks

### 9.1 Suites

`data/benchmarks/suites.json` lists the suites, each with fixed solver limits. An item is `"<pack id>"`
(every level of the pack) or `"<pack id>/<level id>"` (the pack id ends at the first `/`). Items that do
not resolve are reported and skipped, never fatal. Abridged:

```json
{
  "format": "alexvolkihar-sokoban/benchmark-suites",
  "version": 1,
  "suites": [
    {
      "id": "quick",
      "title": "Quick",
      "description": "The 12 First steps levels, a few seconds on a laptop.",
      "limits": { "time_ms": 10000, "max_nodes": 1000000 },
      "items": ["first-steps"]
    },
    {
      "id": "standard",
      "title": "Standard",
      "description": "First steps, 8 generated levels (medium) and the first 40 Boxoban (hard) levels.",
      "limits": { "time_ms": 30000, "max_nodes": 3000000 },
      "items": ["first-steps", "bench-extra/medium-1", "bench-extra/medium-8", "boxoban-hard/1", "boxoban-hard/40"]
    }
  ]
}
```

The bundled suites are `quick` (`first-steps`), `standard` (`first-steps`, `bench-extra/medium-1` to
`bench-extra/medium-8` and `boxoban-hard/1` to `boxoban-hard/40`) and `stress` (all of `bench-extra` and all
of `boxoban-hard`; hitting a limit is an expected result there). Benchmarks read the bundled packs, including the hidden ones, and
never the player's own levels.

### 9.2 Run file

`alexvolkihar-sokoban bench --out FILE` and the benchmark screen write this file (the screen stores it as
`<data dir>/benchmarks/<run_id>.json`). Example (a two-level excerpt of a `standard` run):

<!-- schema: benchmark -->
```json
{
  "format": "alexvolkihar-sokoban/benchmark",
  "version": 1,
  "run_id": "2026-11-06T07-49-06Z-ed72",
  "created_at": "2026-11-06T07:49:06Z",
  "app_version": "1.0.0",
  "solver": { "name": "push-astar", "version": "1", "mode": "optimal" },
  "machine": {
    "os": "Linux",
    "os_version": "Ubuntu 24.04 LTS (kernel 6.8.0)",
    "arch": "x86_64",
    "is_wsl": false,
    "cpu_model": "Example CPU @ 2.50GHz",
    "cpu_count_logical": 8,
    "ram_total_bytes": 17179869184,
    "python": "CPython 3.13.1",
    "pygame_ce": "2.5.8",
    "app_version": "1.0.0"
  },
  "suite": { "id": "standard", "limits": { "time_ms": 30000, "max_nodes": 3000000 } },
  "measure": "tracemalloc",
  "results": [
    {
      "pack_id": "first-steps",
      "level_id": "2",
      "level_hash": "sha256:ae18fe77b0c8bc6d2978a80b84c06daf4eb1ad4f51d2c45f81cb18a7796c676c",
      "status": "solved",
      "pushes": 6,
      "moves": 14,
      "nodes_expanded": 28,
      "nodes_generated": 123,
      "elapsed_ms": 4,
      "peak_mem_bytes": 258211
    },
    {
      "pack_id": "boxoban-hard",
      "level_id": "2",
      "level_hash": "sha256:2c5e4077578ee4da653bc1e7fdc56c1a33d124562dd6ed4b890fe2bb36f598fc",
      "status": "solved",
      "pushes": 13,
      "moves": 55,
      "nodes_expanded": 277,
      "nodes_generated": 847,
      "elapsed_ms": 59,
      "peak_mem_bytes": 187656
    }
  ],
  "summary": { "solved": 2, "total": 2, "total_ms": 63, "nodes_per_s": 4825 }
}
```

- `run_id` is `created_at` with `:` replaced by `-`, a dash and 4 random hex digits.
- `status` is one of `solved`, `unsolvable`, `limit_time`, `limit_nodes`, `cancelled`, `invalid`;
  `pushes` and `moves` are `null` unless solved. A cancelled run keeps the level it stopped on, marked
  `cancelled`, and no level after it.
- `peak_mem_bytes` is the `tracemalloc` peak while that level was solved (`measure` names the method).
  `tracemalloc` slows the Python solver several times, so `nodes_per_s` is only comparable between runs
  with the same `measure`.
- `summary.total_ms` is the sum of `elapsed_ms`; `summary.nodes_per_s` is
  `sum(nodes_expanded) × 1000 // total_ms` (0 when `total_ms` is 0), the headline machine score.
- `machine` never holds a host name, a user name or a path: run files are meant to be shared. Its keys
  are exactly the ten above; unknown values are `null`.

The CSV export has one row per result with the columns `pack_id, level_id, level_hash, status, pushes,
moves, nodes_expanded, nodes_generated, elapsed_ms, peak_mem_bytes` (a header row first, empty cell for
`null`, LF line ends).

`alexvolkihar-sokoban bench compare A B` matches levels by `level_hash`, so a renamed level still lines up
and an edited level appears as two different levels. It shows per-level and total deltas (time in %,
nodes) and flags status changes.

## 10. Generated levels

`alexvolkihar-sokoban generate` and the Random level screen build a level from a **preset** and a
**seed**:

| Preset | Rectangle (walls included) | Boxes | Accepted from | Solver limits |
|---|---|---|---|---|
| `easy` | 7 × 7 | 2 | 6 pushes | 2 s, 200,000 nodes |
| `medium` | 8 × 8 | 3 | 12 pushes | 4 s, 400,000 nodes |
| `hard` | 10 × 9 | 4 | 20 pushes | 8 s, 800,000 nodes |

Each attempt (at most 50 per call) draws, from one `random.Random(seed)` stream:

1. a room: the rectangle's interior, from which random cells become walls as long as the floor stays
   connected, no floor cell becomes a dead end, and at least 60 % of the interior stays floor;
2. goals on random floor cells from which a box can be pulled away, with a box on each;
3. an **exhaustive reverse search**: starting from every solved position (the player in each area of the
   room), every sequence of pulls is explored breadth first, up to the preset's pull depth and 20,000
   positions; one of the positions needing the most pulls becomes the start, with the player on a random
   cell of its area;
4. a check by the solver in `optimal` mode within the preset's limits.

The first level the solver solves with at least the preset's pushes is accepted, with its par. Its id is
`<preset>-<seed>` and the entry stores `"seed"`. Levels the player plays or saves go to `generated.json`,
an ordinary pack with id `generated`, so records and stars work like for any pack.

**Determinism rule.** The same preset and seed give the same level only within the Python implementation,
and only when no attempt depends on the solver's time limit (an attempt rejected because time ran out may
be accepted on a faster machine). The level depends on CPython's Mersenne Twister and on the exact
sequence of `random` calls. A port must not expect to regenerate a Python level from its seed: the rows
stored in `generated.json` are the level, and the seed is a label. A port that writes its own generator
should keep the same id pattern and the same "exhaustive reverse search, then solver check" contract, and
store its own seeds.

## 11. Conformance vectors

`tests/vectors/` holds the language-neutral test cases every implementation of the rules must pass. The
Python suite runs them in `tests/core/test_vectors.py`; a port runs the same files unchanged.

`moves.json` (`alexvolkihar-sokoban/vectors-moves`): each case has `name`, `rows`, `input` (plain `udlr`,
case-insensitive, played one key at a time like a player would) and `expected`. A blocked step changes
nothing and is only counted in `blocked_steps`.

```json
{
  "name": "push",
  "rows": ["#######", "#     #", "# @$ .#", "#     #", "#######"],
  "input": "r",
  "expected": { "player": [2, 3], "boxes": [[2, 4]], "moves": 1, "pushes": 1, "solved": false, "blocked_steps": 0 }
}
```

`boxes` is sorted by row, then column.

`hash.json` (`alexvolkihar-sokoban/vectors-hash`): each case has `rows`, the expected `canonical` text and
its `hash`. A port checks both the text and the digest.

```json
{
  "rows": ["--####", "###--#", "#@$.-#", "######"],
  "canonical": "  ####\n###  #\n#@$. #\n######",
  "hash": "sha256:e641e2cca051259b12ef3fb00a33c8474a813f1e615f7da84ab5e7b52bcf9847"
}
```

How a port should use them:

1. load each file, check `format` and `version`, iterate over `cases`;
2. build the level from `rows` with the port's own reader, play `input`, compare every field of
   `expected`; for hashes, compare the canonical text first, then the hash;
3. also replay the `par.lurd` of every level of the bundled packs and check that it solves the level with
   the stored `pushes` and `moves`: this covers undo-free LURD replay on real levels;
4. load the examples of this page (pack, level, settings, progress, session, benchmark) with the port's
   readers.

The vectors do not yet cover undo/redo, whitespace inside LURD strings, rows of different lengths or empty
rows inside a board; this page (sections 2 to 4) is the reference for those.

## 12. Versioning and migrations

- Every JSON file carries an integer `version`, 1 today. A change that an older reader would misread
  (renamed, removed or re-typed field, new meaning) bumps the version of that format only. Adding an
  optional field that older readers can ignore does not.
- Migrations are steps `vN → vN+1` registered per format and applied in order on the payload (the object
  without `format`/`version`). A migrated file is rewritten in the new version at its next save, never
  just for being read.
- A file whose version is newer than the reader's is never modified (section 8.1).
- Level packs and single levels are read-only data; a pack format change would ship with a converter
  (`alexvolkihar-sokoban convert`) rather than a silent rewrite.
- The level hash (section 3) is part of every save format: it must never change for an unchanged layout.
  If the canonical text ever had to change, it would get a new prefix (not `sha256:`) and a progress
  migration.
- The par's `solver` string (`push-astar/1`) changes when the solver's results change. `annotate` skips
  levels that already have a par unless `--force` is given, and a level the solver cannot solve within the
  limits keeps its existing par.
