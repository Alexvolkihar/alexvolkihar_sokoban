"""Base class of every screen. Scenes live on the ``App`` stack and are created by name."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from alexvolkihar_sokoban.ui.input import Action

if TYPE_CHECKING:
    from alexvolkihar_sokoban.ui.app import App


class Scene:
    """Every hook is a no-op; subclasses override what they need.

    ``name`` is the name the scene was pushed under (set by ``App``). An overlay (``is_overlay = True``) is
    drawn on top of the scene below it instead of hiding it.
    """

    is_overlay: bool = False

    def __init__(self, app: App) -> None:
        self.app = app
        self.name = ""

    def on_enter(self, **params: object) -> None:
        """Called once, right after the scene is pushed, with the parameters given to ``push``."""

    def on_exit(self) -> None:
        """Called once when the scene leaves the stack (pop, replace, or the window closing)."""

    def on_resume(self) -> None:
        """Called when the scene above it was popped and this scene is on top again."""

    def handle_action(self, action: Action) -> None:
        """A bound key was pressed (see ``ui.input``)."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """Every raw event (mouse, keys, …), after its actions were handled."""

    def update(self, dt_ms: int) -> None:
        """Advance time; only the top scene is updated."""

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the whole scene (an overlay draws only what it adds)."""
