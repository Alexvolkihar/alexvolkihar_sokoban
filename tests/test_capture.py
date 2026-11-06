"""The headless capture script that renders the README screenshots and the demo video (scripts/capture.py)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture.py"


def _load_capture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture"] = module  # dataclasses look their module up by name
    spec.loader.exec_module(module)
    return module


capture = _load_capture()


def test_capture_never_opens_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "x11")
    capture.force_headless()
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"


def test_storyboard_lasts_between_20_and_40_seconds() -> None:
    storyboard = capture.load_storyboard()
    assert 20.0 <= capture.duration_s(storyboard) <= 40.0


def test_render_storyboard_returns_frames_of_the_video_size() -> None:
    frames = capture.render_storyboard(capture.load_storyboard(), frames=10)
    assert len(frames) == 10
    assert all(frame.get_size() == (1280, 720) for frame in frames)


def test_render_storyboard_is_deterministic() -> None:
    storyboard = capture.load_storyboard()
    first = capture.render_storyboard(storyboard, frames=3)[-1]
    second = capture.render_storyboard(storyboard, frames=3)[-1]
    assert first.get_buffer().raw == second.get_buffer().raw


def test_every_shot_of_the_storyboard_renders() -> None:
    storyboard = capture.load_storyboard()
    for index in range(len(storyboard["shots"])):
        only = {**storyboard, "shots": [storyboard["shots"][index]]}
        frames = capture.render_storyboard(only, frames=capture.frame_count(only))
        assert frames, storyboard["shots"][index]["id"]


@pytest.mark.parametrize("name", list(capture.SCREENSHOTS))
def test_screenshot_renders_at_1280_by_800(name: str) -> None:
    assert capture.render_screenshot(name).get_size() == (1280, 800)


def test_screenshot_list_covers_the_readme_set() -> None:
    expected = {"menu", "level-select", "gameplay", "themes", "benchmark", "victory"}
    assert expected <= set(capture.SCREENSHOTS)


def test_unknown_screenshot_is_refused() -> None:
    with pytest.raises(KeyError):
        capture.render_screenshot("nope")


def test_encode_writes_an_mp4_and_a_gif(tmp_path: Path) -> None:
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    storyboard = capture.load_storyboard()
    frames = capture.render_storyboard(storyboard, frames=6)
    mp4, gif = capture.encode(frames, tmp_path, fps=storyboard["fps"])
    assert mp4.stat().st_size > 0
    assert gif.stat().st_size > 0
    assert gif.read_bytes()[:6] in (b"GIF87a", b"GIF89a")
