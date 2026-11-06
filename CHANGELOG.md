# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-06

First release of alexvolkihar_sokoban, a remake of Sokoban-LAMA as a finished pygame-ce game.

### Added

- Game: smooth or instant moves, unlimited undo and redo, restart, move/push counters and timer, pause
  menu, victory screen with 1 to 3 stars against the solver's par and a "better than par" badge.
- Hints: the next push of an optimal solution from the current position, computed in the background, with
  dead-end detection. Watching the solver play the level is available from the pause menu. Both mark the
  run as assisted.
- Menus: main menu with Continue, level select with packs, thumbnails, stars and best scores, settings
  (language, animation speed, timer, fullscreen, progress reset), theme picker with a live preview, key
  rebinding, credits. The window is resizable down to 640×480.
- French and English interface, chosen from the system language on first run.
- 20 themes: Kenney sprites (CC0), classic, neon, high contrast, and 16 palettes adapted from the author's
  Dobble 3D project.
- Level packs: the 11 original LAMA levels, the 100 first Boxoban (hard) puzzles by DeepMind
  (Apache-2.0), generated levels, and custom levels dropped in the data folder.
- Level files: XSB/SOK (multi-level, run-length encoding, metadata), the original LAMA format, and a
  JSON pack format. CRLF, byte order marks, tabs and broken levels are handled without crashing.
- Push-based A* solver with push-optimal solutions, dead-square and freeze deadlock detection, time and
  node limits, and cancellation. Every bundled level stores its par.
- Random level generator with easy, medium and hard presets and reproducible seeds, checked by the
  solver.
- Benchmark mode on the command line and in the game: quick, standard and stress suites, machine
  information without host or user names, JSON and CSV export, comparison of two runs.
- Saves: settings, progress (keyed by a level hash, so renaming or reordering packs keeps scores) and the
  game in progress, written atomically, with versioned formats, migrations and backups of corrupt files.
- Command line: `play`, `solve`, `convert`, `annotate`, `bench`, `bench compare` and `generate`, plus
  `--data-dir` and `--version`.
- Format reference for ports in `docs/formats.md`, JSON Schemas in `schemas/` and conformance vectors in
  `tests/vectors/`.
- Tests, Ruff, mypy and continuous integration on Linux, Windows and macOS.

### Changed

- The board is drawn in the right orientation (the original game drew it transposed).
- The original level files are read in their own format; their `*` (a box) no longer clashes with the
  XSB `*` (a box on a goal).
- The solver is rewritten from scratch: the original "A*" ignored its priorities and searched breadth-first
  over moves.

### Removed

- `lvlultime` (a copy of `test8`), `wiki.txt` (level 1 of the 1982 Sokoban by Thinking Rabbit, not ours to
  distribute) and the unplayable `test_performance` (12 boxes, 14 goals) from the playable levels. A
  repaired `test_performance` is kept for the stress benchmark.

## [0.0.0] - 2022

Sokoban-LAMA, the original student project by the LAMA group: Antoine LAROCHE, Alexis MABANZA, Logan
VIVIEN and Martin PACARY. A pygame Sokoban with its own level format, 17 levels and an automatic solver.
Its code is kept in `legacy/`. Source: <https://github.com/Alexvolkihar/Sokoban-LAMA>.

[1.0.0]: https://github.com/Alexvolkihar/alexvolkihar_sokoban/releases/tag/v1.0.0
[0.0.0]: https://github.com/Alexvolkihar/Sokoban-LAMA
