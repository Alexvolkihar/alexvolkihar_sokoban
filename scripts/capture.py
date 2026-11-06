#!/usr/bin/env python3
"""Render the README screenshots and the demo video from the real game, headless.

    python scripts/capture.py --out docs/media [--only screenshots|video]

Everything is drawn into off-screen pygame surfaces (``SDL_VIDEODRIVER=dummy``, ``App(headless=True)``): no
window ever opens. The scenes are driven with synthetic key presses on a fixed 30 fps clock, from a fresh data
folder in a temporary directory, so two runs give the same pictures. ``scripts/storyboard.json`` describes the
video shots and the screenshots.

Determinism: the solver hint, the random level and the benchmark run in worker threads; the script waits for
them (``join``) before drawing the next frame. The benchmark shows the real solver's statuses, pushes, moves
and nodes, but its times and peak memory are derived from the node counts (fixed rates: the measured values
change from one run to the next) and its machine panel is a neutral placeholder, so the pictures neither
change between runs nor describe the computer that made them.

The video and the GIF need the optional ``media`` extra (``pip install -e '.[media]'``): frames are piped to
the ffmpeg binary shipped with ``imageio-ffmpeg`` (H.264 MP4), and the GIF is made from the MP4 with
ffmpeg's palette filters.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


def force_headless() -> None:
    """Make SDL render off-screen whatever the environment says: captures never open a window."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"


force_headless()

import pygame  # noqa: E402  (after the SDL environment is set)

from alexvolkihar_sokoban import __version__  # noqa: E402
from alexvolkihar_sokoban.benchmark import runner  # noqa: E402
from alexvolkihar_sokoban.benchmark.machine import MachineInfo  # noqa: E402
from alexvolkihar_sokoban.core.lurd import restore  # noqa: E402
from alexvolkihar_sokoban.persistence.session import SavedSession  # noqa: E402
from alexvolkihar_sokoban.scoring.records import LastPlayed, RunResult  # noqa: E402
from alexvolkihar_sokoban.solver.api import SolveResult, solve  # noqa: E402
from alexvolkihar_sokoban.ui.app import App  # noqa: E402
from alexvolkihar_sokoban.ui.board_renderer import BoardRenderer  # noqa: E402
from alexvolkihar_sokoban.ui.context import AppContext  # noqa: E402
from alexvolkihar_sokoban.ui.i18n import get_language, set_language  # noqa: E402
from alexvolkihar_sokoban.ui.scenes import benchmark as benchmark_scene  # noqa: E402
from alexvolkihar_sokoban.ui.scenes import game as game_scene  # noqa: E402
from alexvolkihar_sokoban.ui.scenes.game import GameScene  # noqa: E402
from alexvolkihar_sokoban.ui.themes.base import TileKind  # noqa: E402
from alexvolkihar_sokoban.ui.themes.registry import get_theme  # noqa: E402

STORYBOARD = Path(__file__).with_name("storyboard.json")
FIXED_NOW = datetime(2026, 11, 5, 14, 3, 22, tzinfo=UTC)
FIXED_STAMP = "2026-11-05T14:03:22Z"
# The rates the benchmark times and peak memory are derived from (see the module docstring).
BENCH_NODES_PER_S = 10_000
BENCH_BASE_BYTES = 160 * 1024
BENCH_BYTES_PER_NODE = 48
NEUTRAL_MACHINE = MachineInfo(
    os="Linux",
    os_version="Ubuntu 24.04 LTS",
    arch="x86_64",
    is_wsl=False,
    cpu_model="Generic x86-64 CPU",
    cpu_count_logical=8,
    ram_total_bytes=16 * 2**30,
    python=f"{platform.python_implementation()} {platform.python_version()}",
    pygame_ce=pygame.version.ver,
    app_version=__version__,
)

# Key name → (pygame key, SDL scancode, text typed).
KEYS: dict[str, tuple[int, int, str]] = {
    "up": (pygame.K_UP, 82, ""),
    "down": (pygame.K_DOWN, 81, ""),
    "left": (pygame.K_LEFT, 80, ""),
    "right": (pygame.K_RIGHT, 79, ""),
    "enter": (pygame.K_RETURN, 40, "\r"),
    "escape": (pygame.K_ESCAPE, 41, "\x1b"),
    "tab": (pygame.K_TAB, 43, "\t"),
    "u": (pygame.K_u, 24, "u"),
    "h": (pygame.K_h, 11, "h"),
    "p": (pygame.K_p, 19, "p"),
    **{str(d): (pygame.K_0 + d, 39 if d == 0 else 29 + d, str(d)) for d in range(10)},
}
_LURD_KEYS = {"l": "left", "r": "right", "u": "up", "d": "down"}

# Video look: a caption band under the game, and dips through the band colour between shots.
BAND = (20, 22, 28)
BAND_TEXT = (245, 245, 240)
BAND_MUTED = (150, 155, 165)
BAND_HEIGHT = 80
FADE_FRAMES = 5
MP4_OPTIONS = ["-crf", "24", "-preset", "slow", "-tune", "animation", "-movflags", "+faststart"]
BRAND = "alexvolkihar_sokoban"


# --- storyboard -------------------------------------------------------------------------------------------


def load_storyboard(path: Path = STORYBOARD) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "alexvolkihar-sokoban/storyboard" or data.get("version") != 1:
        raise ValueError(f"{path}: not an alexvolkihar-sokoban/storyboard v1 file")
    return data


def _shot_frames(shot: dict[str, Any], fps: int) -> int:
    return max(1, round(float(shot["seconds"]) * fps))


def frame_count(storyboard: dict[str, Any]) -> int:
    fps = int(storyboard["fps"])
    return sum(_shot_frames(shot, fps) for shot in storyboard["shots"])


def duration_s(storyboard: dict[str, Any]) -> float:
    return frame_count(storyboard) / int(storyboard["fps"])


def _schedule(steps: list[dict[str, Any]], fps: int) -> tuple[dict[int, list[tuple[str, str]]], int]:
    """Frame index → the operations played on that frame, in order (see storyboard.json's ``_doc``), and
    the frame where the last step ends."""
    plan: dict[int, list[tuple[str, str]]] = {}
    cursor = 0.0

    def at(op: str, arg: str = "") -> None:
        plan.setdefault(round(cursor * fps), []).append((op, arg))

    for step in steps:
        every = float(step.get("every", 0.15))
        if "wait" in step:
            cursor += float(step["wait"])
        elif "key" in step:
            at("key", step["key"])
        elif "keys" in step:
            for name in step["keys"]:
                at("key", name)
                cursor += every
        elif "lurd" in step:
            for ch in step["lurd"]:
                at("key", _LURD_KEYS[ch.lower()])
                cursor += every
        elif "themes" in step:
            for theme_id in step["themes"]:
                at("theme", theme_id)
                cursor += every
        elif "join" in step:
            at("join")
        else:
            raise ValueError(f"unknown storyboard step {step!r}")
    return plan, round(cursor * fps)


# --- the game, made deterministic ------------------------------------------------------------------------


class _FixedMemory:
    """Stands in for ``tracemalloc`` in the benchmark runner: the peak follows the last level's node count."""

    peak = 0

    def is_tracing(self) -> bool:
        return True  # so the runner neither starts nor stops the real tracemalloc

    def reset_peak(self) -> None:
        pass

    def get_traced_memory(self) -> tuple[int, int]:
        return (0, self.peak)


_MEMORY = _FixedMemory()


def _bench_solve(level: Any, **kwargs: Any) -> SolveResult:
    """The real solver, with a time (and a peak memory) derived from its node counts."""
    result = solve(level, **kwargs)
    _MEMORY.peak = BENCH_BASE_BYTES + result.nodes_generated * BENCH_BYTES_PER_NODE
    return replace(result, elapsed_ms=result.nodes_expanded * 1000 // BENCH_NODES_PER_S)


@contextlib.contextmanager
def deterministic() -> Iterator[None]:
    """Fixed clock, run id, machine panel, benchmark times and memory; the language is restored afterwards."""
    language = get_language()
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(game_scene, "utc_now", lambda: FIXED_STAMP))
        stack.enter_context(mock.patch.object(runner, "_utc_now", lambda: FIXED_NOW))
        fixed_hex = SimpleNamespace(token_hex=lambda n=2: "0042"[: 2 * n])
        stack.enter_context(mock.patch.object(runner, "secrets", fixed_hex))
        stack.enter_context(mock.patch.object(runner, "collect_machine_info", lambda: NEUTRAL_MACHINE))
        stack.enter_context(
            mock.patch.object(benchmark_scene, "collect_machine_info", lambda: NEUTRAL_MACHINE)
        )
        stack.enter_context(mock.patch.object(benchmark_scene, "solve", _bench_solve))
        stack.enter_context(mock.patch.object(runner, "tracemalloc", _MEMORY))
        stack.enter_context(
            mock.patch.object(
                benchmark_scene,
                "display_path",
                lambda path: "~/.local/share/alexvolkihar-sokoban/benchmarks/" + path.name,
            )
        )
        try:
            yield
        finally:
            set_language(language)


def _seed_progress(ctx: AppContext, seeded: dict[str, Any]) -> None:
    """Completed levels (solved with their par) and the last played level, so menus look lived in."""
    progress = ctx.progress
    for pack_id, level_ids in seeded.get("completed", {}).items():
        pack = ctx.pack(pack_id)
        for i, level_id in enumerate(level_ids):
            entry = pack.entry(level_id)
            par = entry.par
            if par is None:
                continue
            run = RunResult(par.moves, par.pushes, 9_000 + 4_000 * i, par.lurd, False, FIXED_STAMP)
            progress.record_run(entry.level.canonical_hash(), pack_id, level_id, run, par)
    last = seeded.get("last_played")
    if last is not None:
        entry = ctx.pack(last[0]).entry(last[1])
        progress.set_last_played(LastPlayed(last[0], last[1], entry.level.canonical_hash()))


def _make_app(
    storyboard: dict[str, Any], data_dir: Path, size: tuple[int, int], theme: str
) -> tuple[App, AppContext]:
    ctx = AppContext.load(data_dir)
    settings = ctx.settings
    settings.language = storyboard.get("language", "en")
    settings.window = size
    settings.theme = theme
    settings.animation = "normal"
    settings.show_timer = True
    settings.fullscreen = False
    _seed_progress(ctx, storyboard.get("progress", {}))
    return App(settings, context=ctx, headless=True), ctx


def _start(app: App, ctx: AppContext, start: dict[str, Any]) -> None:
    """Build the scene stack a shot or a screenshot starts from."""
    scene = start["scene"]
    app.push("main_menu")
    if scene == "main_menu":
        return
    if scene in ("level_select", "generate", "benchmark", "themes", "settings", "credits"):
        params: dict[str, object] = {}
        if "pack" in start:
            params["pack_id"] = start["pack"]
        app.push(scene, **params)
        return
    pack = ctx.pack(start["pack"])
    entry = pack.entry(start["level"])
    resume = None
    lurd = start.get("lurd", "")
    if "played" in start and entry.par is not None:
        lurd = entry.par.lurd[: int(start["played"])]
    if lurd:
        restore(entry.level, lurd, "")  # fails early on a storyboard typo
        resume = SavedSession(
            pack_id=pack.id,
            level_id=entry.id,
            level_hash=entry.level.canonical_hash(),
            lurd=lurd,
            redo_lurd="",
            elapsed_ms=int(start.get("elapsed_ms", 0)),
            assisted=False,
            saved_at=FIXED_STAMP,
        )
    game = app.push("game", pack=pack, level_id=entry.id, resume=resume)
    assert isinstance(game, GameScene)
    if scene == "pause":
        app.push("pause", game=game)
    elif scene == "replay":
        app.push("replay", pack=pack, level_id=entry.id, on_watch=game.mark_assisted)
    elif scene != "game":
        raise ValueError(f"unknown start scene {scene!r}")


def _key_event(name: str) -> pygame.event.Event:
    key, scancode, text = KEYS[name]
    return pygame.event.Event(pygame.KEYDOWN, key=key, scancode=scancode, mod=pygame.KMOD_NONE, unicode=text)


def _join_workers(app: App) -> None:
    """Wait for the background work of the scene on top (hint, random level, benchmark run)."""
    worker = getattr(app.top, "worker", None)
    join: Callable[[float], object] | None = getattr(worker, "join", None)
    if join is not None:
        join(60.0)


def _apply(app: App, op: str, arg: str) -> None:
    if op == "key":
        app.step([_key_event(arg)], 0)
    elif op == "theme":
        app.set_theme(arg)
        for scene in app.stack:
            renderer = getattr(scene, "renderer", None)
            if renderer is not None:
                renderer.theme = app.theme
    elif op == "join":
        _join_workers(app)
        app.step([], 0)


def _frame_ms(index: int, fps: int) -> int:
    """Milliseconds between frame ``index`` and the next, so the clock never drifts from the frame count."""
    return round((index + 1) * 1000 / fps) - round(index * 1000 / fps)


def _run_scene(
    storyboard: dict[str, Any], item: dict[str, Any], size: tuple[int, int], frames: int
) -> Iterator[pygame.Surface]:
    """The app's screen after each frame of ``item`` (a shot or a screenshot), ``frames`` frames long."""
    fps = int(storyboard["fps"])
    plan, _ = _schedule(item.get("steps", []), fps)
    with deterministic(), tempfile.TemporaryDirectory(prefix="avs-capture-") as tmp:
        app, ctx = _make_app(storyboard, Path(tmp), size, item.get("theme", "kenney"))
        try:
            _start(app, ctx, item["start"])
            for index in range(frames):
                for op, arg in plan.get(index, []):
                    _apply(app, op, arg)
                app.step([], _frame_ms(index, fps))
                yield app.screen
        finally:
            app.quit()  # every scene's on_exit cancels its worker


# --- video ------------------------------------------------------------------------------------------------


def _font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.Font(None, size)


def _caption_band(frame: pygame.Surface, caption: str, accent: tuple[int, int, int]) -> None:
    w, h = frame.get_size()
    band = pygame.Rect(0, h - BAND_HEIGHT, w, BAND_HEIGHT)
    frame.fill(BAND, band)
    frame.fill(accent, pygame.Rect(0, band.top, w, 4))
    brand = _font(26).render(BRAND, True, BAND_MUTED)
    frame.blit(brand, brand.get_rect(midright=(w - 28, band.centery + 2)))
    font = _font(46)
    text = font.render(caption, True, BAND_TEXT)
    max_w = w - brand.get_width() - 100
    if text.get_width() > max_w:
        text = _font(38).render(caption, True, BAND_TEXT)
    frame.blit(text, text.get_rect(midleft=(32, band.centery + 2)))


def _end_card(frame: pygame.Surface, shot: dict[str, Any], t_s: float) -> None:
    """The closing card: name, credits to the LAMA group, how to install; lines appear one by one."""
    w, h = frame.get_size()
    frame.fill(BAND)
    theme = get_theme("kenney")
    tile = 72
    strip = (TileKind.WALL, TileKind.PLAYER, TileKind.BOX, TileKind.GOAL, TileKind.BOX_ON_GOAL, TileKind.WALL)
    x0 = (w - tile * len(strip)) // 2
    lines: list[tuple[float, int, tuple[int, int, int], str]] = [
        (0.0, 84, BAND_TEXT, shot["title"]),
        (0.35, 36, (240, 200, 90), shot["subtitle"]),
        (0.7, 30, BAND_MUTED, shot["credits"]),
        (1.05, 30, BAND_TEXT, shot["install"]),
    ]
    rendered = [
        (appear, _font(size).render(text, True, colour), text) for appear, size, colour, text in lines
    ]
    gaps = [34, 22, 40, 0]
    height = tile + 40 + sum(s.get_height() for _, s, _ in rendered) + sum(gaps)
    y = (h - height) // 2
    for i, kind in enumerate(strip):
        frame.blit(theme.tile(TileKind.FLOOR, tile), (x0 + i * tile, y))
        frame.blit(theme.tile(kind, tile), (x0 + i * tile, y))
    y += tile + 40
    for (appear, surface, text), gap in zip(rendered, gaps, strict=True):
        rect = surface.get_rect(midtop=(w // 2, y))
        y = rect.bottom + gap
        if t_s < appear:
            continue
        surface.set_alpha(round(255 * min(1.0, (t_s - appear) / 0.25)))
        if text == shot["install"]:
            box = rect.inflate(36, 22)
            pygame.draw.rect(frame, (36, 40, 50), box, border_radius=10)
            pygame.draw.rect(frame, (70, 76, 90), box, width=2, border_radius=10)
        frame.blit(surface, rect)


def _dip(frame: pygame.Surface, amount: float) -> None:
    """Darken the whole frame towards the band colour (``amount`` 0 = untouched, 1 = solid)."""
    if amount <= 0:
        return
    veil = pygame.Surface(frame.get_size())
    veil.fill(BAND)
    veil.set_alpha(round(255 * min(1.0, amount)))
    frame.blit(veil, (0, 0))


def iter_frames(storyboard: dict[str, Any], *, limit: int | None = None) -> Iterator[pygame.Surface]:
    """Every frame of the video in order (a new surface each), stopping after ``limit`` frames."""
    width, height = storyboard["size"]
    fps = int(storyboard["fps"])
    shots = storyboard["shots"]
    produced = 0
    for number, shot in enumerate(shots):
        frames = _shot_frames(shot, fps)
        fade_in = number > 0
        fade_out = number < len(shots) - 1
        if shot["start"]["scene"] == "end_card":
            source: Iterator[pygame.Surface | None] = iter([None] * frames)
        else:
            source = _run_scene(storyboard, shot, (width, height - BAND_HEIGHT), frames)
        for index, screen in enumerate(source):
            if limit is not None and produced >= limit:
                close = getattr(source, "close", None)
                if callable(close):
                    close()  # runs _run_scene's cleanup now, not at garbage collection
                return
            frame = pygame.Surface((width, height))
            if screen is None:
                _end_card(frame, shot, index / fps)
            else:
                frame.blit(screen, (0, 0))
                accent = get_theme(shot.get("theme", "kenney")).palette.accent
                _caption_band(frame, shot["caption"], accent)
            if fade_in and index < FADE_FRAMES:
                _dip(frame, 1 - (index + 1) / (FADE_FRAMES + 1))
            if fade_out and index >= frames - FADE_FRAMES:
                _dip(frame, (index - (frames - FADE_FRAMES) + 1) / (FADE_FRAMES + 1))
            produced += 1
            yield frame


def render_storyboard(storyboard: dict[str, Any], frames: int) -> list[pygame.Surface]:
    """The first ``frames`` frames of the video."""
    return list(iter_frames(storyboard, limit=frames))


def poster_frame(storyboard: dict[str, Any]) -> pygame.Surface:
    """The last frame of the first shot (the settled hook): frame 0 of the MP4, so players show it first."""
    first = {**storyboard, "shots": storyboard["shots"][:1]}
    *_, last = iter_frames(first)
    return last


def _ffmpeg() -> str:
    import imageio_ffmpeg  # optional "media" extra

    exe: str = imageio_ffmpeg.get_ffmpeg_exe()
    return exe


def encode(
    frames: Iterator[pygame.Surface] | list[pygame.Surface],
    out: Path,
    *,
    fps: int,
    gif_width: int = 640,
    gif_fps: int = 12,
    gif_limit: int = 5 * 2**20,
) -> tuple[Path, Path]:
    """Write ``demo.mp4`` (H.264, yuv420p, faststart) and ``demo.gif`` (made from the MP4) into ``out``."""
    import imageio_ffmpeg  # optional "media" extra

    out.mkdir(parents=True, exist_ok=True)
    mp4, gif = out / "demo.mp4", out / "demo.gif"
    writer = None
    for frame in frames:
        if writer is None:
            writer = imageio_ffmpeg.write_frames(
                str(mp4),
                frame.get_size(),
                fps=fps,
                codec="libx264",
                pix_fmt_in="rgb24",
                pix_fmt_out="yuv420p",
                quality=None,
                macro_block_size=8,
                output_params=MP4_OPTIONS,
            )
            writer.send(None)
        writer.send(pygame.image.tobytes(frame, "RGB"))
    if writer is None:
        raise ValueError("no frame to encode")
    writer.close()
    for colours in (128, 96, 64, 48, 32):
        _make_gif(mp4, gif, width=gif_width, fps=gif_fps, colours=colours)
        if gif.stat().st_size <= gif_limit:
            break
    return mp4, gif


def _make_gif(mp4: Path, gif: Path, *, width: int, fps: int, colours: int) -> None:
    graph = (
        f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
        f"[a]palettegen=max_colors={colours}:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
    )
    subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", "-i", str(mp4), "-filter_complex", graph, "-loop", "0", str(gif)],
        check=True,
    )


def write_video(storyboard: dict[str, Any], out: Path) -> tuple[Path, Path]:
    poster = poster_frame(storyboard)

    def frames() -> Iterator[pygame.Surface]:
        for index, frame in enumerate(iter_frames(storyboard)):
            yield poster if index == 0 else frame

    return encode(frames(), out, fps=int(storyboard["fps"]))


# --- screenshots ------------------------------------------------------------------------------------------


def _screenshots(storyboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in storyboard["screenshots"]}


SCREENSHOTS = _screenshots(load_storyboard())


def _theme_grid(storyboard: dict[str, Any], item: dict[str, Any], size: tuple[int, int]) -> pygame.Surface:
    """The same position in several themes, two by two, each named in its own colours."""
    with deterministic(), tempfile.TemporaryDirectory(prefix="avs-capture-") as tmp:
        app, ctx = _make_app(storyboard, Path(tmp), size, "kenney")
        try:
            entry = ctx.pack(item["start"]["pack"]).entry(item["start"]["level"])
            lurd = entry.par.lurd[: int(item["start"]["played"])] if entry.par is not None else ""
            state = restore(entry.level, lurd, "")
            canvas = pygame.Surface(size)
            themes = item["themes"]
            cols = 2
            rows = (len(themes) + cols - 1) // cols
            cell_w, cell_h = size[0] // cols, size[1] // rows
            font = app.fonts.normal
            for i, theme_id in enumerate(themes):
                theme = get_theme(theme_id)
                cell = pygame.Rect((i % cols) * cell_w, (i // cols) * cell_h, cell_w, cell_h)
                canvas.fill(theme.background, cell)
                label = font.render(theme.name, True, theme.palette.text)
                canvas.blit(label, label.get_rect(midtop=(cell.centerx, cell.top + 14)))
                board = pygame.Rect(cell.left + 16, cell.top + 52, cell.width - 32, cell.height - 68)
                BoardRenderer(theme).draw(canvas, state.level, state.player, state.boxes, board)
            for x in range(1, cols):
                canvas.fill((20, 22, 28), pygame.Rect(x * cell_w - 2, 0, 4, size[1]))
            for y in range(1, rows):
                canvas.fill((20, 22, 28), pygame.Rect(0, y * cell_h - 2, size[0], 4))
            return canvas
        finally:
            app.quit()


def render_screenshot(name: str, storyboard: dict[str, Any] | None = None) -> pygame.Surface:
    """The screenshot ``name`` of storyboard.json, at its ``screenshot_size``."""
    storyboard = storyboard or load_storyboard()
    item = _screenshots(storyboard)[name]
    size = tuple(storyboard["screenshot_size"])
    assert len(size) == 2
    if item["start"]["scene"] == "theme_grid":
        return _theme_grid(storyboard, item, (size[0], size[1]))
    fps = int(storyboard["fps"])
    plan, end = _schedule(item.get("steps", []), fps)
    frames = max(end, *plan, 0) + int(item.get("hold_frames", 12))
    last: pygame.Surface | None = None
    for screen in _run_scene(storyboard, item, (size[0], size[1]), frames):
        last = screen.copy()
    assert last is not None
    return last


def write_screenshots(storyboard: dict[str, Any], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in _screenshots(storyboard):
        path = out / f"{name}.png"
        pygame.image.save(render_screenshot(name, storyboard), str(path))
        paths.append(path)
    return paths


# --- command line -----------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("docs/media"), help="output folder")
    parser.add_argument("--only", choices=("screenshots", "video"), help="render only one kind")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD)
    args = parser.parse_args(argv)
    storyboard = load_storyboard(args.storyboard)
    pygame.display.init()
    if args.only in (None, "screenshots"):
        for path in write_screenshots(storyboard, args.out):
            print(f"{path}  {path.stat().st_size // 1024} KiB")
    if args.only in (None, "video"):
        for path in write_video(storyboard, args.out):
            print(f"{path}  {path.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
