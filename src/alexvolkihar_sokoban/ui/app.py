"""Window, scene stack and main loop (spec 7.9)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files

import pygame

from alexvolkihar_sokoban.persistence.settings import MIN_WINDOW, Settings
from alexvolkihar_sokoban.ui.i18n import set_language
from alexvolkihar_sokoban.ui.input import InputMapper
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes import load_scene_class
from alexvolkihar_sokoban.ui.themes.base import Theme
from alexvolkihar_sokoban.ui.themes.registry import get_theme

WINDOW_TITLE = "Alexvolkihar Sokoban"
FPS = 60
KEY_REPEAT = (180, 60)  # delay and interval in ms, so holding an arrow keeps walking


@dataclass(frozen=True)
class Fonts:
    small: pygame.font.Font
    normal: pygame.font.Font
    title: pygame.font.Font


def _clamp(size: tuple[int, int]) -> tuple[int, int]:
    return (max(MIN_WINDOW[0], size[0]), max(MIN_WINDOW[1], size[1]))


class App:
    """Owns the window and a stack of scenes; only the top scene gets input and updates.

    ``headless=True`` renders into an off-screen surface and never opens a window (tests, captures).
    """

    def __init__(self, settings: Settings, *, context: object | None = None, headless: bool = False) -> None:
        pygame.init()
        self.settings = settings
        self.context = context
        self.headless = headless
        self.running = True
        self._stack: list[Scene] = []
        set_language(settings.language)
        self.input = InputMapper(settings.keybindings)
        self.theme: Theme = get_theme(settings.theme)
        self.fonts = Fonts(
            small=pygame.font.Font(None, 24),
            normal=pygame.font.Font(None, 34),
            title=pygame.font.Font(None, 64),
        )
        pygame.key.set_repeat(*KEY_REPEAT)
        if not headless:
            pygame.display.set_caption(WINDOW_TITLE)
            _set_icon()
        self.screen = self._make_screen()

    # -- scene stack -------------------------------------------------------------------------------------

    @property
    def stack(self) -> tuple[Scene, ...]:
        return tuple(self._stack)

    @property
    def top(self) -> Scene | None:
        return self._stack[-1] if self._stack else None

    def push(self, name: str, **params: object) -> Scene:
        """Create the scene ``name`` on top of the stack and call its ``on_enter(**params)``."""
        scene = load_scene_class(name)(self)
        scene.name = name
        self._stack.append(scene)
        scene.on_enter(**params)
        return scene

    def replace(self, name: str, **params: object) -> Scene:
        """Swap the top scene for ``name`` (the scene below is not resumed)."""
        if self._stack:
            self._stack.pop().on_exit()
        return self.push(name, **params)

    def pop(self) -> None:
        """Remove the top scene; the app stops when the stack becomes empty."""
        if not self._stack:
            return
        self._stack.pop().on_exit()
        if self._stack:
            self._stack[-1].on_resume()
        else:
            self.running = False

    def quit(self) -> None:
        """Exit every scene, top first (so a game in progress can save), then stop the loop."""
        while self._stack:
            self._stack.pop().on_exit()
        self.running = False

    # -- display -----------------------------------------------------------------------------------------

    def set_theme(self, theme_id: str) -> None:
        self.theme = get_theme(theme_id)
        self.settings.theme = self.theme.id

    def apply_display_settings(self) -> None:
        """Re-create the window from ``settings.window`` and ``settings.fullscreen``."""
        self.screen = self._make_screen()

    def _make_screen(self) -> pygame.Surface:
        size = _clamp(self.settings.window)
        self.settings.window = size
        if self.headless:
            return pygame.Surface(size)
        if self.settings.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode(size, pygame.RESIZABLE)

    def _resize(self, size: tuple[int, int]) -> None:
        if self.settings.fullscreen:
            return
        self.settings.window = _clamp(size)
        self.screen = self._make_screen()

    # -- loop --------------------------------------------------------------------------------------------

    def step(self, events: Sequence[pygame.event.Event], dt_ms: int = 16) -> None:
        """Handle ``events``, update the top scene and draw the visible part of the stack.

        A key press is dispatched to the scene on top when it arrives; its remaining actions are dropped
        once the stack changes (Escape = pause + back must not open the pause overlay and close it).
        """
        for event in events:
            if not self.running:
                return
            if event.type == pygame.QUIT:
                self.quit()
                return
            if event.type == pygame.VIDEORESIZE:
                self._resize((event.w, event.h))
                continue
            self._dispatch(event)
        if not self.running:
            return
        top = self.top
        if top is not None:
            top.update(dt_ms)
        self._draw()

    def _dispatch(self, event: pygame.event.Event) -> None:
        scene = self.top
        if scene is None:
            return
        for action in self.input.actions_for(event):
            scene.handle_action(action)
            if self.top is not scene:
                return
        scene.handle_event(event)

    def _draw(self) -> None:
        if not self._stack:
            return
        first = len(self._stack) - 1
        while first > 0 and self._stack[first].is_overlay:
            first -= 1
        self.screen.fill(self.theme.background)
        for scene in self._stack[first:]:
            scene.draw(self.screen)
        if not self.headless:
            pygame.display.flip()

    def run(self) -> None:
        """Run at 60 fps until the stack is empty or the window is closed; starts on the main menu."""
        if not self._stack:
            self.push("main_menu")
        clock = pygame.time.Clock()
        self.running = True
        while self.running:
            dt = clock.tick(FPS)
            self.step(pygame.event.get(), dt)


def _set_icon() -> None:
    icon = files("alexvolkihar_sokoban").joinpath("data/themes/kenney/icon.png")
    try:
        with icon.open("rb") as f:
            pygame.display.set_icon(pygame.image.load(f, "icon.png"))
    except (OSError, pygame.error):
        pass  # a missing icon is cosmetic
