"""Random level (spec 7.8, 7.9): pick a difficulty and an optional seed, generate, preview, then play or keep.

Generation runs in a worker thread (the hard preset can take a few seconds) and stops through
``should_stop`` when the player cancels or leaves. A level is written to the Generated pack only when the
player chooses Play or Save, so it then shows up in the level select under Generated.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

from alexvolkihar_sokoban.generator.api import (
    SEED_LIMIT,
    GeneratedLevel,
    GenerationCancelled,
    GenerationFailed,
)
from alexvolkihar_sokoban.generator.api import generate as generate_level
from alexvolkihar_sokoban.generator.presets import DEFAULT_PRESET, PRESETS, Preset
from alexvolkihar_sokoban.ui.hud import fit_text
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.main_menu import _wrap
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.thumbnails import render_thumbnail
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList

logger = logging.getLogger(__name__)

PRESET, SEED, GENERATE, PLAY, REGENERATE, SAVE, BACK = range(7)
PRESET_IDS: tuple[str, ...] = tuple(PRESETS)
SEED_DIGITS = len(str(SEED_LIMIT - 1))

_PRESET_NAMES: dict[str, Callable[[], str]] = {
    "easy": lambda: t("Easy", "Facile"),
    "medium": lambda: t("Medium", "Moyen"),
    "hard": lambda: t("Hard", "Difficile"),
}


def preset_name(preset_id: str) -> str:
    name = _PRESET_NAMES.get(preset_id)
    if name is None:
        return preset_id
    return name()


def preset_summary(preset: Preset) -> str:
    """``8×8, 3 boxes, 12+ pushes``: what the difficulty means."""
    size = f"{preset.width}×{preset.height}"
    return t(
        f"{size} room, {preset.boxes} boxes, {preset.min_pushes}+ pushes",
        f"salle {size}, {preset.boxes} caisses, {preset.min_pushes}+ poussées",
    )


@dataclass
class _Job:
    """One generation: the worker thread fills ``outcome`` (a level or a failure) or ``error``."""

    stop: threading.Event = field(default_factory=threading.Event)
    outcome: GeneratedLevel | GenerationFailed | None = None
    error: str | None = None
    done: bool = False


class GenerateScene(Scene):
    menu: MenuList
    preset_id: str
    seed_text: str
    result: GeneratedLevel | None
    status: str
    failed: bool
    saved: bool
    worker: threading.Thread | None

    def on_enter(self, **params: object) -> None:
        preset = params.get("preset")
        self.preset_id = preset if isinstance(preset, str) and preset in PRESETS else DEFAULT_PRESET
        self.seed_text = ""
        self.result = None
        self.status = ""
        self.failed = False
        self.saved = False
        self.worker = None
        self._job: _Job | None = None
        self._lock = threading.Lock()
        self._busy_ms = 0
        has_context = self.app.context is not None
        self.menu = MenuList(
            [
                MenuItem(
                    lambda: t(
                        f"Difficulty: {preset_name(self.preset_id)}",
                        f"Difficulté : {preset_name(self.preset_id)}",
                    ),
                    lambda: self._cycle_preset(1),
                ),
                MenuItem(self._seed_label, self._focus_seed),
                MenuItem(self._generate_label, self._generate_or_cancel),
                MenuItem(lambda: t("Play", "Jouer"), self.play, enabled=False),
                MenuItem(lambda: t("Regenerate", "Régénérer"), self.regenerate, enabled=False),
                MenuItem(self._save_label, self.save, enabled=False),
                MenuItem(lambda: t("Back", "Retour"), self.app.pop),
            ]
        )
        self._has_context = has_context
        self._refresh_items()

    def on_exit(self) -> None:
        self.cancel(quiet=True)

    # -- state -------------------------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._job is not None

    @property
    def preset(self) -> Preset:
        return PRESETS[self.preset_id]

    def _refresh_items(self) -> None:
        idle = not self.busy
        items = self.menu.items
        items[PRESET].enabled = idle
        items[SEED].enabled = idle
        items[GENERATE].enabled = True
        has_result = idle and self.result is not None
        items[PLAY].enabled = has_result and self._has_context
        items[REGENERATE].enabled = has_result
        items[SAVE].enabled = has_result and self._has_context and not self.saved
        items[BACK].enabled = idle
        if not items[self.menu.selected].enabled:
            self.menu.selected = GENERATE

    def _seed_label(self) -> str:
        if self.seed_text:
            value = self.seed_text
            if self.menu.selected == SEED and not self.busy:
                value += "_"
            return t(f"Seed: {value}", f"Graine : {value}")
        if self.menu.selected == SEED and not self.busy:
            return t("Seed: type digits_", "Graine : tapez des chiffres_")
        return t("Seed: random", "Graine : aléatoire")

    def _generate_label(self) -> str:
        if self.busy:
            return t("Cancel", "Annuler")
        if self.failed:
            return t("Try again", "Réessayer")
        return t("Generate", "Générer")

    def _save_label(self) -> str:
        if self.saved:
            return t("Saved", "Enregistré")
        return t("Save to Generated", "Garder dans Générés")

    def _cycle_preset(self, step: int) -> None:
        if self.busy:
            return
        index = PRESET_IDS.index(self.preset_id)
        self.preset_id = PRESET_IDS[(index + step) % len(PRESET_IDS)]

    def _focus_seed(self) -> None:
        """Confirm on the seed field moves on to Generate."""
        self.menu.selected = GENERATE

    def _type_digit(self, ch: str) -> None:
        text = self.seed_text + ch
        if text.startswith("0"):
            text = text.lstrip("0") or "0"
        if len(text) > SEED_DIGITS or int(text) >= SEED_LIMIT:
            return
        self.seed_text = text

    # -- generation --------------------------------------------------------------------------------------

    def _generate_or_cancel(self) -> None:
        if self.busy:
            self.cancel()
        else:
            self.start()

    def start(self, seed: int | None = None) -> None:
        """Generate a level of the chosen difficulty from ``seed``, the typed seed, or a random one."""
        self.cancel(quiet=True)
        if seed is None and self.seed_text:
            seed = int(self.seed_text)
        job = _Job()
        thread = threading.Thread(
            target=self._run, args=(job, self.preset, seed), name="level-generator", daemon=True
        )
        self._job = job
        self.worker = thread
        self.result = None
        self.saved = False
        self.failed = False
        self.status = ""
        self._busy_ms = 0
        self._refresh_items()
        thread.start()

    def _run(self, job: _Job, preset: Preset, seed: int | None) -> None:
        """Worker thread: never raises, the outcome is picked up by ``update``."""
        outcome: GeneratedLevel | GenerationFailed | None = None
        error: str | None = None
        try:
            outcome = generate_level(preset, seed, should_stop=job.stop.is_set)
        except GenerationFailed as e:
            outcome = e
        except Exception as e:  # shown to the player instead of leaving the scene busy forever
            logger.exception("level generation crashed")
            error = type(e).__name__
        with self._lock:
            job.outcome = outcome
            job.error = error
            job.done = True

    def cancel(self, *, quiet: bool = False) -> None:
        """Stop the running generation; its late outcome is ignored."""
        job = self._job
        if job is None:
            return
        job.stop.set()
        self._job = None
        if not quiet:
            self.status = t("Generation cancelled.", "Génération annulée.")
            self.failed = False
            self._refresh_items()

    def regenerate(self) -> None:
        """Another level of the same difficulty: the typed seed is dropped for a random one."""
        self.seed_text = ""
        self.start()

    def play(self) -> None:
        context = self.app.context
        if context is None or self.result is None:
            return
        entry = self.result.entry
        pack = context.add_generated_level(entry)
        self.app.replace("game", pack=pack, level_id=entry.id)

    def save(self) -> None:
        context = self.app.context
        if context is None or self.result is None or self.saved:
            return
        context.add_generated_level(self.result.entry)
        self.saved = True
        self.status = t(
            f"{self.result.entry.id} saved: find it in Level select, Generated.",
            f"{self.result.entry.id} enregistré : retrouvez-le dans Choix du niveau, Niveaux générés.",
        )
        self.menu.selected = PLAY
        self._refresh_items()

    def update(self, dt_ms: int) -> None:
        job = self._job
        if job is None:
            return
        self._busy_ms += dt_ms
        with self._lock:
            if not job.done:
                return
            outcome, error = job.outcome, job.error
        self._job = None
        if isinstance(outcome, GeneratedLevel):
            self.result = outcome
            self.menu.selected = PLAY
        elif isinstance(outcome, GenerationCancelled):
            self.status = t("Generation cancelled.", "Génération annulée.")
        else:
            self.failed = True
            if error is not None:
                self.status = t(f"Generation failed ({error}).", f"La génération a échoué ({error}).")
            else:
                attempts = self.preset.max_attempts
                self.status = t(
                    f"No level found in {attempts} attempts. Try again or change the seed.",
                    f"Aucun niveau trouvé en {attempts} essais. Réessayez ou changez la graine.",
                )
            self.menu.selected = GENERATE
        self._refresh_items()

    # -- input -------------------------------------------------------------------------------------------

    def handle_action(self, action: Action) -> None:
        if action is Action.BACK:
            if self.busy:
                self.cancel()
            else:
                self.app.pop()
            return
        if action in (Action.LEFT, Action.RIGHT):
            if self.menu.selected == PRESET:
                self._cycle_preset(-1 if action is Action.LEFT else 1)
            return
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and not self.busy:
            ch = getattr(event, "unicode", "")
            if len(ch) == 1 and ch in "0123456789":
                self.menu.selected = SEED
                self._type_digit(ch)
                return
            if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE) and self.menu.selected == SEED:
                self.seed_text = self.seed_text[:-1]
                return
        self.menu.handle_event(event)

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        surface.fill(theme.background)
        screen = surface.get_rect()
        margin = max(12, screen.height // 40)

        title = fonts.title.render(t("Random level", "Niveau aléatoire"), True, palette.accent)
        title_rect = title.get_rect(midtop=(screen.centerx, margin * 2))
        surface.blit(title, title_rect)
        hint = fonts.small.render(
            fit_text(self._hint(), fonts.small, screen.width - 2 * margin), True, palette.muted
        )
        hint_rect = hint.get_rect(midbottom=(screen.centerx, screen.bottom - margin))
        surface.blit(hint, hint_rect)

        line_h = fonts.small.get_linesize()
        status_lines: list[str] = []
        if self.status:
            status_lines = _wrap(self.status, fonts.small, screen.width - 2 * margin)[:2]
        status_top = hint_rect.top - margin // 2 - line_h * len(status_lines)
        colour = palette.bad if self.failed else palette.good
        for i, line in enumerate(status_lines):
            label = fonts.small.render(line, True, colour)
            surface.blit(label, label.get_rect(midtop=(screen.centerx, status_top + i * line_h)))

        top = title_rect.bottom + margin
        bottom = status_top - margin // 2
        body = pygame.Rect(screen.left + margin, top, screen.width - 2 * margin, max(1, bottom - top))
        left_w = min(body.width // 2, max(260, body.width * 2 // 5))
        menu_rect = pygame.Rect(body.left, body.top, left_w, body.height)
        preview = pygame.Rect(
            menu_rect.right + margin, body.top, body.right - menu_rect.right - margin, body.height
        )
        self.menu.draw(surface, menu_rect, fonts.normal, palette)
        self._draw_preview(surface, preview)

    def _hint(self) -> str:
        if self.busy:
            return t("Esc: cancel", "Échap : annuler")
        return t(
            "Left/Right: difficulty · 0-9: seed · Enter: confirm · Esc: back",
            "Gauche/Droite : difficulté · 0-9 : graine · Entrée : valider · Échap : retour",
        )

    def _draw_preview(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        if rect.width < 40 or rect.height < 40:
            return
        radius = max(4, rect.height // 40)
        pygame.draw.rect(surface, palette.panel, rect, border_radius=radius)
        pad = max(8, fonts.small.get_height() // 2)
        inner = rect.inflate(-2 * pad, -2 * pad)
        line_h = fonts.small.get_linesize()

        heading = f"{preset_name(self.preset_id)} — {preset_summary(self.preset)}"
        heading_lines = _wrap(heading, fonts.small, inner.width)[:2]
        for i, line in enumerate(heading_lines):
            label = fonts.small.render(fit_text(line, fonts.small, inner.width), True, palette.text)
            surface.blit(label, label.get_rect(midtop=(inner.centerx, inner.top + i * line_h)))
        area_top = inner.top + line_h * len(heading_lines) + pad // 2

        info: list[str] = []
        result = self.result
        if result is not None:
            entry = result.entry
            seed = entry.seed if entry.seed is not None else "?"
            info.append(t(f"{entry.id} · seed {seed}", f"{entry.id} · graine {seed}"))
            if entry.par is not None:
                info.append(
                    t(
                        f"Solver best: {entry.par.pushes} pushes, {entry.par.moves} moves",
                        f"Record du solveur : {entry.par.pushes} poussées, {entry.par.moves} pas",
                    )
                )
        area = pygame.Rect(inner.left, area_top, inner.width, inner.bottom - area_top - line_h * len(info))
        for i, text in enumerate(info):
            label = fonts.small.render(fit_text(text, fonts.small, inner.width), True, palette.muted)
            surface.blit(label, label.get_rect(midtop=(inner.centerx, area.bottom + i * line_h)))
        if area.width < 4 or area.height < 4:
            return

        if result is not None:
            thumb = render_thumbnail(result.entry.level, theme, (area.width, area.height - pad // 2))
            surface.blit(thumb, thumb.get_rect(center=area.center))
            return
        if self.busy:
            self._draw_busy(surface, area)
            return
        if self.failed:
            text = t("No level this time.", "Pas de niveau cette fois.")
            colour = palette.bad
        else:
            text = t("Press Generate to create a level.", "Choisissez Générer pour créer un niveau.")
            colour = palette.muted
        lines = _wrap(text, fonts.normal, area.width)
        y = area.centery - fonts.normal.get_linesize() * len(lines) // 2
        for line in lines:
            label = fonts.normal.render(line, True, colour)
            surface.blit(label, label.get_rect(midtop=(area.centerx, y)))
            y += fonts.normal.get_linesize()

    def _draw_busy(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """ "Generating…", the elapsed time, and a box hopping along a row of goals."""
        theme = self.app.theme
        palette = theme.palette
        fonts = self.app.fonts
        seconds = self._busy_ms / 1000
        text = t(f"Generating… {seconds:.1f} s", f"Génération… {seconds:.1f} s")
        label = fonts.normal.render(fit_text(text, fonts.normal, area.width), True, palette.text)
        tile = max(8, min(40, area.width // 8, area.height // 4))
        cells = 5
        total_h = label.get_height() + tile + tile // 2
        y = area.centery - total_h // 2
        surface.blit(label, label.get_rect(midtop=(area.centerx, y)))
        x0 = area.centerx - cells * tile // 2
        y0 = y + label.get_height() + tile // 2
        current = (self._busy_ms // 250) % cells
        for i in range(cells):
            kind = TileKind.BOX if i == current else TileKind.GOAL
            surface.blit(theme.tile(TileKind.FLOOR, tile), (x0 + i * tile, y0))
            surface.blit(theme.tile(kind, tile), (x0 + i * tile, y0))


SCENE = GenerateScene
