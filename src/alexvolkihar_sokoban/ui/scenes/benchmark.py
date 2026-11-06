"""Benchmark scene (spec 7.7, 7.9): pick a suite, run it in a worker thread, read and compare the results.

Views: ``suites`` (picker, plus a "saved runs" row) → ``running`` (live table, ``back`` cancels through the
solver's ``should_stop``) → ``results`` (table, summary, machine panel; Export JSON / Export CSV / Compare)
→ ``runs`` (saved runs of ``<data dir>/benchmarks``) → ``compare`` (per-level time delta and status changes).

A finished run is saved to ``<data dir>/benchmarks/<run_id>.json`` at once; a cancelled run only when the
player exports it. Peak memory is measured with ``tracemalloc``, which slows the solver several times over, so
nodes per second only compare between runs measured the same way (every run of this game and of the
``bench`` command is).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pygame

from alexvolkihar_sokoban.benchmark.compare import Comparison, LevelDelta, compare
from alexvolkihar_sokoban.benchmark.export import BenchmarkFileError, read_json, write_csv, write_json
from alexvolkihar_sokoban.benchmark.machine import MachineInfo, collect_machine_info
from alexvolkihar_sokoban.benchmark.runner import BenchmarkRun, LevelResult, run_suite
from alexvolkihar_sokoban.benchmark.suites import Suite, load_bundled_packs, load_suites, resolve
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.solver.api import SolveLimits, SolveResult, SolveStatus, solve
from alexvolkihar_sokoban.ui.i18n import get_language, t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.main_menu import _wrap
from alexvolkihar_sokoban.ui.scenes.themes import ScrollList, draw_row_bar, fit_text
from alexvolkihar_sokoban.ui.themes.base import RGB, UiPalette

BENCHMARKS_DIR = "benchmarks"
JOIN_TIMEOUT_S = 2.0
MAX_BODY_WIDTH = 1240

_SUITES: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "quick": (
        ("Quick", "Rapide"),
        (
            "The original LAMA levels, under 30 s on a laptop.",
            "Les niveaux LAMA d'origine, moins de 30 s sur un portable.",
        ),
    ),
    "standard": (
        ("Standard", "Standard"),
        (
            "The original LAMA levels and the first 40 Boxoban (hard) levels.",
            "Les niveaux LAMA d'origine et les 40 premiers niveaux Boxoban (difficiles).",
        ),
    ),
    "stress": (
        ("Stress", "Intensif"),
        (
            "Unsolvable and very large levels: hitting a limit is an expected result.",
            "Niveaux insolubles et très grands : atteindre une limite est un résultat attendu.",
        ),
    ),
}

_STATUS = {
    SolveStatus.SOLVED: ("solved", "résolu"),
    SolveStatus.UNSOLVABLE: ("unsolvable", "insoluble"),
    SolveStatus.LIMIT_TIME: ("time limit", "limite de temps"),
    SolveStatus.LIMIT_NODES: ("node limit", "limite de nœuds"),
    SolveStatus.CANCELLED: ("cancelled", "annulé"),
    SolveStatus.INVALID: ("invalid", "invalide"),
}


# --- text helpers ----------------------------------------------------------------------------------------


def suite_title(suite_id: str, fallback: str) -> str:
    """The suite's title in the current language; ``fallback`` (the file's English title) when unknown."""
    known = _SUITES.get(suite_id)
    return t(*known[0]) if known else fallback


def suite_description(suite_id: str) -> str:
    known = _SUITES.get(suite_id)
    return t(*known[1]) if known else ""


def status_label(status: SolveStatus) -> str:
    return t(*_STATUS[status])


def _french() -> bool:
    return get_language() == "fr"


def fmt_int(value: int) -> str:
    """``1,234,567`` in English, ``1 234 567`` in French."""
    text = f"{value:,}"
    return text.replace(",", " ") if _french() else text


def _decimal(text: str) -> str:
    return text.replace(".", ",") if _french() else text


def fmt_seconds(ms: int) -> str:
    return _decimal(f"{ms / 1000:.1f}") + " s"


def fmt_pct(pct: float | None) -> str:
    if pct is None:
        return "–"
    return _decimal(f"{pct:+.1f}") + (" %" if _french() else "%")


def limits_text(limits: SolveLimits) -> str:
    return f"{_decimal(f'{limits.time_s:g}')} s / {fmt_int(limits.max_nodes)} {t('nodes', 'nœuds')}"


def fmt_date(created_at: str) -> str:
    """``2026-11-05T14:03:22Z`` → ``2026-11-05 14:03 UTC``."""
    if len(created_at) >= 16 and created_at[10] == "T":
        return f"{created_at[:10]} {created_at[11:16]} UTC"
    return created_at


def display_path(path: Path) -> str:
    """``path`` with the home folder written ``~``."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except (ValueError, RuntimeError):
        return str(path)


def machine_lines(m: MachineInfo) -> list[str]:
    """The machine panel; nothing that identifies the computer or its user."""
    os_line = f"{m.os} {m.os_version}" + (" (WSL)" if m.is_wsl else "")
    cpu = m.cpu_model or t("unknown", "inconnu")
    if m.cpu_count_logical:
        cpu += t(f" ({m.cpu_count_logical} threads)", f" ({m.cpu_count_logical} threads)")
    ram = t("unknown", "inconnue")
    if m.ram_total_bytes is not None:
        ram = _decimal(f"{m.ram_total_bytes / 2**30:.1f}") + t(" GiB", " Gio")
    return [
        t("System: ", "Système : ") + os_line + f" · {m.arch}",
        t("CPU: ", "Processeur : ") + cpu,
        t("Memory: ", "Mémoire : ") + ram,
        f"Python {m.python.split()[-1]} ({m.python.split()[0]}) · pygame-ce "
        + (m.pygame_ce or t("not installed", "absent")),
        t("Game version ", "Version du jeu ") + m.app_version,
    ]


def _status_colour(status: SolveStatus, palette: UiPalette) -> RGB:
    if status is SolveStatus.SOLVED:
        return palette.good
    if status is SolveStatus.INVALID:
        return palette.bad
    if status is SolveStatus.UNSOLVABLE:
        return palette.text
    return palette.muted  # limits and cancel: expected outcomes, not failures


# --- worker ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Started:
    index: int
    total: int
    entry: LevelEntry


@dataclass(frozen=True)
class _Done:
    index: int
    result: LevelResult


@dataclass(frozen=True)
class _Finished:
    run: BenchmarkRun


@dataclass(frozen=True)
class _Failed:
    message: str


_Event = _Started | _Done | _Finished | _Failed


class BenchmarkWorker:
    """Runs one suite in a daemon thread and reports through a queue the scene drains in ``update``."""

    def __init__(
        self,
        items: Sequence[tuple[Pack, LevelEntry]],
        suite: Suite,
        solve_fn: Callable[..., SolveResult],
    ) -> None:
        self.events: queue.SimpleQueue[_Event] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(list(items), suite, solve_fn), name="benchmark", daemon=True
        )
        self._thread.start()

    def _run(
        self, items: list[tuple[Pack, LevelEntry]], suite: Suite, solve_fn: Callable[..., SolveResult]
    ) -> None:
        try:
            run = run_suite(
                items,
                suite_id=suite.id,
                limits=suite.limits,
                solve_fn=solve_fn,
                on_level_start=lambda i, n, entry: self.events.put(_Started(i, n, entry)),
                on_level_done=lambda i, result: self.events.put(_Done(i, result)),
                should_stop=self._stop.is_set,
            )
        except Exception as exc:  # reported to the player, never lost with the thread
            self.events.put(_Failed(f"{type(exc).__name__}: {exc}"))
        else:
            self.events.put(_Finished(run))

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def cancel(self) -> None:
        self._stop.set()

    def join(self, timeout: float) -> None:
        self._thread.join(timeout)


# --- scene -----------------------------------------------------------------------------------------------


class BenchmarkScene(Scene):
    view: str
    message: str
    suites: list[Suite]
    packs: dict[str, Pack]
    machine: MachineInfo
    suite_scroll: ScrollList
    worker: BenchmarkWorker | None
    suite: Suite | None
    total: int
    missing: list[str]
    results: list[LevelResult]
    current: tuple[int, int, LevelEntry] | None
    level_ms: int
    run_ms: int
    run: BenchmarkRun | None
    cancelled: bool
    saved_path: Path | None
    action_index: int
    table_scroll: ScrollList
    saved_runs: list[tuple[Path, BenchmarkRun]]
    runs_scroll: ScrollList
    runs_purpose: str
    runs_back: str
    results_back: str
    comparison: Comparison | None
    compare_scroll: ScrollList

    def on_enter(self, **params: object) -> None:
        self.view = "suites"
        self.message = ""
        try:
            self.suites = list(load_suites().values())
        except ValueError as exc:
            self.suites = []
            self.message = t("Cannot read the benchmark suites: ", "Suites illisibles : ") + str(exc)
        self.packs, warnings = load_bundled_packs()
        if warnings and not self.message:
            self.message = warnings[0]
        self.machine = collect_machine_info()
        self.suite_scroll = ScrollList(len(self.suites) + 1)
        self.worker = None
        self.suite = None
        self.total = 0
        self.missing = []
        self.results = []
        self.current = None
        self.level_ms = self.run_ms = 0
        self.run = None
        self.cancelled = False
        self.saved_path = None
        self.action_index = 0
        self.table_scroll = ScrollList(0)
        self.saved_runs = []
        self.runs_scroll = ScrollList(0)
        self.runs_purpose = "open"
        self.runs_back = "suites"
        self.results_back = "suites"
        self.comparison = None
        self.compare_scroll = ScrollList(0)
        self._buttons: list[tuple[int, pygame.Rect]] = []

    def on_exit(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.worker.join(JOIN_TIMEOUT_S)
            self.worker = None

    # -- state -------------------------------------------------------------------------------------------

    @property
    def selected_suite(self) -> Suite | None:
        """The highlighted suite; ``None`` on the "saved runs" row."""
        index = self.suite_scroll.selected
        return self.suites[index] if index < len(self.suites) else None

    @property
    def benchmarks_dir(self) -> Path | None:
        context = self.app.context
        return None if context is None else context.data_dir / BENCHMARKS_DIR

    def missing_line(self, suite: Suite) -> str | None:
        """A warning naming the packs a suite needs but that are not installed, or ``None``."""
        _, missing = resolve(suite, self.packs)
        if not missing:
            return None
        packs = list(dict.fromkeys(item.partition("/")[0] for item in missing))
        return t(
            f"Not installed, skipped: {', '.join(packs)} ({len(missing)} items)",
            f"Non installé, ignoré : {', '.join(packs)} ({len(missing)} éléments)",
        )

    def level_label(self, pack_id: str, level_id: str, *, multi: bool) -> str:
        """The level's title, after its pack id when the run spans several packs."""
        pack = self.packs.get(pack_id)
        ids = {entry.id: entry for entry in pack.levels} if pack is not None else {}
        entry = ids.get(level_id)  # a level removed since the run keeps its id
        title = entry.title if entry is not None else level_id
        return f"{pack_id} · {title}" if multi else title

    def progress_text(self) -> str:
        if self.current is None:
            return t("Starting…", "Démarrage…")
        index, total, entry = self.current
        return f"{t('Level', 'Niveau')} {index + 1}/{total} · {entry.title} · {fmt_seconds(self.level_ms)}"

    def actions(self) -> list[tuple[str, str]]:
        return [
            ("export_json", t("Export JSON", "Exporter JSON")),
            ("export_csv", t("Export CSV", "Exporter CSV")),
            ("compare", t("Compare…", "Comparer…")),
            ("back", t("Back", "Retour")),
        ]

    # -- transitions -------------------------------------------------------------------------------------

    def start(self, suite: Suite) -> None:
        items, self.missing = resolve(suite, self.packs)
        if not items:
            self.message = t(
                "No level of this suite is installed.", "Aucun niveau de cette suite n'est installé."
            )
            return
        self.suite = suite
        self.total = len(items)
        self.results = []
        self.current = None
        self.level_ms = self.run_ms = 0
        self.run = None
        self.cancelled = False
        self.saved_path = None
        self.message = ""
        self.table_scroll = ScrollList(0)
        self.view = "running"
        self.worker = BenchmarkWorker(items, suite, solve)

    def cancel(self) -> None:
        if self.worker is not None and not self.worker.stopping:
            self.worker.cancel()
            self.message = t("Cancelling…", "Annulation…")

    def _finish(self, run: BenchmarkRun, cancelled: bool) -> None:
        self.worker = None
        self.run = run
        self.results = list(run.results)
        self.cancelled = cancelled
        self.current = None
        self.view = "results"
        self.results_back = "suites"
        self.action_index = 0
        self.table_scroll = ScrollList(len(self.results))
        self.message = ""
        if cancelled:
            self.message = t(
                "Cancelled: this partial run is not saved unless you export it.",
                "Annulé : ce passage partiel n'est enregistré que si vous l'exportez.",
            )
        else:
            self._export("json")

    def _export(self, kind: str) -> None:
        run, folder = self.run, self.benchmarks_dir
        if run is None:
            return
        if folder is None:
            self.message = t(
                "No data folder: nothing saved.", "Pas de dossier de données : rien d'enregistré."
            )
            return
        path = folder / f"{run.run_id}.{kind}"
        try:
            if kind == "json":
                write_json(run, path)
            else:
                write_csv(run, path)
        except OSError as exc:
            self.message = t("Could not save the results: ", "Impossible d'enregistrer : ") + (
                exc.strerror or str(exc)
            )
            return
        if kind == "json":
            self.saved_path = path
        self.message = t("Saved to ", "Enregistré dans ") + display_path(path)

    def _load_saved_runs(self) -> list[tuple[Path, BenchmarkRun]]:
        folder = self.benchmarks_dir
        runs: list[tuple[Path, BenchmarkRun]] = []
        bad = 0
        if folder is not None:
            try:
                paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
            except OSError:
                paths = []
            for path in paths:
                try:
                    runs.append((path, read_json(path)))
                except BenchmarkFileError:
                    bad += 1
        if bad:
            self.message = t(
                f"{bad} unreadable file(s) skipped.", f"{bad} fichier(s) illisible(s) ignoré(s)."
            )
        runs.sort(key=lambda item: (item[1].created_at, item[1].run_id), reverse=True)
        return runs

    def open_runs(self, purpose: str) -> None:
        """List the saved runs: ``purpose`` ``"compare"`` (with the run shown) or ``"open"``."""
        self.message = ""
        runs = self._load_saved_runs()
        selected = 0
        if purpose == "compare" and self.run is not None:
            current = self.run
            runs = [item for item in runs if item[1].run_id != current.run_id]
            same = [i for i, (_, r) in enumerate(runs) if r.suite_id == current.suite_id]
            selected = same[0] if same else 0
        self.saved_runs = runs
        self.runs_scroll = ScrollList(len(runs), selected)
        self.runs_purpose = purpose
        self.runs_back = self.view
        self.view = "runs"

    def _choose_run(self) -> None:
        if not self.saved_runs:
            return
        path, chosen = self.saved_runs[self.runs_scroll.selected]
        if self.runs_purpose == "compare" and self.run is not None:
            self.comparison = compare(chosen, self.run)
            self.compare_scroll = ScrollList(len(self.comparison.levels))
            self.view = "compare"
            return
        self.run = chosen
        self.results = list(chosen.results)
        self.suite = next((s for s in self.suites if s.id == chosen.suite_id), None)
        self.total = len(chosen.results)
        self.missing = []
        self.cancelled = False
        self.saved_path = path
        self.table_scroll = ScrollList(len(self.results))
        self.action_index = 0
        self.results_back = "runs"
        self.message = ""
        self.view = "results"

    def _do_action(self, action_id: str) -> None:
        if action_id == "export_json":
            self._export("json")
        elif action_id == "export_csv":
            self._export("csv")
        elif action_id == "compare":
            self.open_runs("compare")
        else:
            self._results_back()

    def _results_back(self) -> None:
        self.message = ""
        self.view = self.results_back
        if self.view == "runs":
            self.runs_purpose = "open"

    # -- input -------------------------------------------------------------------------------------------

    def handle_action(self, action: Action) -> None:
        handler = {
            "suites": self._suites_action,
            "running": self._running_action,
            "results": self._results_action,
            "runs": self._runs_action,
            "compare": self._compare_action,
        }[self.view]
        handler(action)

    def _suites_action(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.suite_scroll.move(-1 if action is Action.UP else 1)
        elif action is Action.CONFIRM:
            self._pick_suite()
        elif action is Action.BACK:
            self.app.pop()

    def _pick_suite(self) -> None:
        suite = self.selected_suite
        if suite is None:
            self.open_runs("open")
        else:
            self.start(suite)

    def _running_action(self, action: Action) -> None:
        if action in (Action.BACK, Action.CONFIRM):
            self.cancel()

    def _results_action(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.table_scroll.move(-1 if action is Action.UP else 1, wrap=False)
        elif action in (Action.LEFT, Action.RIGHT):
            count = len(self.actions())
            self.action_index = (self.action_index + (1 if action is Action.RIGHT else -1)) % count
        elif action is Action.CONFIRM:
            self._do_action(self.actions()[self.action_index][0])
        elif action is Action.BACK:
            self._results_back()

    def _runs_action(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.runs_scroll.move(-1 if action is Action.UP else 1)
        elif action is Action.CONFIRM:
            self._choose_run()
        elif action is Action.BACK:
            self.message = ""
            self.view = self.runs_back

    def _compare_action(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.compare_scroll.move(-1 if action is Action.UP else 1, wrap=False)
        elif action is Action.BACK:
            self.view = "results"

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.view == "suites":
            if self.suite_scroll.handle_event(event) is not None:
                self._pick_suite()
        elif self.view == "runs":
            if self.runs_scroll.handle_event(event) is not None:
                self._choose_run()
        elif self.view in ("results", "compare"):
            scroll = self.table_scroll if self.view == "results" else self.compare_scroll
            if event.type == pygame.MOUSEWHEEL:
                scroll.move(-event.y, wrap=False)
            elif self.view == "results":
                self._button_event(event)
        elif (
            self.view == "running"
            and event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and any(rect.collidepoint(event.pos) for _, rect in self._buttons)
        ):
            self.cancel()

    def _button_event(self, event: pygame.event.Event) -> None:
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            return
        for index, rect in self._buttons:
            if rect.collidepoint(event.pos):
                self.action_index = index
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._do_action(self.actions()[index][0])
                return

    # -- time --------------------------------------------------------------------------------------------

    def update(self, dt_ms: int) -> None:
        worker = self.worker
        if worker is None:
            return
        self.level_ms += dt_ms
        self.run_ms += dt_ms
        while True:
            try:
                event = worker.events.get_nowait()
            except queue.Empty:
                return
            if isinstance(event, _Started):
                self.current = (event.index, event.total, event.entry)
                self.level_ms = 0
            elif isinstance(event, _Done):
                self.results.append(event.result)
                self.table_scroll.count = len(self.results)
                self.table_scroll.selected = len(self.results) - 1
            elif isinstance(event, _Finished):
                self._finish(event.run, cancelled=worker.stopping)
                return
            else:
                self.worker = None
                self.current = None
                self.view = "suites"
                self.message = t("The benchmark failed: ", "Le benchmark a échoué : ") + event.message
                return

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        surface.fill(self.app.theme.background)
        screen = surface.get_rect()
        margin = max(12, screen.height // 40)
        self._buttons = []

        title = fonts.title.render(t("Benchmark", "Benchmark"), True, palette.accent)
        title_rect = title.get_rect(midtop=(screen.centerx, margin))
        surface.blit(title, title_rect)

        hint = fonts.small.render(
            fit_text(fonts.small, self._hint(), screen.width - 2 * margin), True, palette.muted
        )
        hint_rect = hint.get_rect(midbottom=(screen.centerx, screen.bottom - margin // 2))
        surface.blit(hint, hint_rect)
        bottom = hint_rect.top - margin // 2
        if self.message:
            colour = palette.bad if self._message_is_problem() else palette.text
            text = fonts.small.render(
                fit_text(fonts.small, self.message, screen.width - 2 * margin), True, colour
            )
            rect = text.get_rect(midbottom=(screen.centerx, bottom))
            surface.blit(text, rect)
            bottom = rect.top - margin // 2

        body = pygame.Rect(margin, title_rect.bottom + margin // 2, screen.width - 2 * margin, 0)
        body.height = max(1, bottom - body.top)
        if body.width > MAX_BODY_WIDTH:  # keep lines and tables together on very wide windows
            body.width = MAX_BODY_WIDTH
            body.centerx = screen.centerx
        {
            "suites": self._draw_suites,
            "running": self._draw_run,
            "results": self._draw_run,
            "runs": self._draw_runs,
            "compare": self._draw_compare,
        }[self.view](surface, body)

    def _message_is_problem(self) -> bool:
        ok = (t("Saved to ", "Enregistré dans "), t("Cancelling…", "Annulation…"))
        return not self.message.startswith(ok)

    def _hint(self) -> str:
        if self.view == "suites":
            return t(
                "Up/Down: choose · Enter: run · Esc: back",
                "Haut/Bas : choisir · Entrée : lancer · Échap : retour",
            )
        if self.view == "running":
            return t("Esc or Enter: cancel", "Échap ou Entrée : annuler")
        if self.view == "results":
            return t(
                "Up/Down: scroll · Left/Right: choose · Enter: confirm · Esc: back",
                "Haut/Bas : défiler · Gauche/Droite : choisir · Entrée : valider · Échap : retour",
            )
        if self.view == "runs":
            return t(
                "Up/Down: choose · Enter: open · Esc: back",
                "Haut/Bas : choisir · Entrée : ouvrir · Échap : retour",
            )
        return t("Up/Down: scroll · Esc: back", "Haut/Bas : défiler · Échap : retour")

    def _blit(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        colour: RGB,
        x: int,
        y: int,
        width: int,
    ) -> int:
        """Draw one line cut to ``width``; return the y below it."""
        label = font.render(fit_text(font, text, width), True, colour)
        surface.blit(label, (x, y))
        return y + font.get_linesize()

    def _paragraph(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        colour: RGB,
        rect: pygame.Rect,
        y: int,
    ) -> int:
        for line in _wrap(text, font, rect.width):
            if y + font.get_linesize() > rect.bottom:
                break
            y = self._blit(surface, line, font, colour, rect.left, y, rect.width)
        return y

    def _panel(self, surface: pygame.Surface, rect: pygame.Rect) -> pygame.Rect:
        palette = self.app.theme.palette
        pygame.draw.rect(surface, palette.panel, rect, border_radius=8)
        pad = max(8, min(rect.width, rect.height) // 30)
        return rect.inflate(-2 * pad, -2 * pad)

    # suites ---------------------------------------------------------------------------------------------

    def _draw_suites(self, surface: pygame.Surface, body: pygame.Rect) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        gap = max(12, body.width // 50)
        list_rect = pygame.Rect(body.left, body.top, min(340, max(200, body.width // 3)), body.height)
        row_h = fonts.normal.get_height() + 14
        for index, row in self.suite_scroll.layout(list_rect, row_h):
            bar = row.inflate(0, -4)
            selected = index == self.suite_scroll.selected
            if selected:
                draw_row_bar(surface, bar, palette)
            if index < len(self.suites):
                name = suite_title(self.suites[index].id, self.suites[index].title)
            else:
                name = t("Saved runs…", "Historique…")
            colour = palette.accent if selected else palette.text
            label = fonts.normal.render(fit_text(fonts.normal, name, bar.width - 20), True, colour)
            surface.blit(label, label.get_rect(midleft=(bar.left + 12, bar.centery)))
        self.suite_scroll.draw_arrows(surface, list_rect, palette.muted)

        panel = pygame.Rect(list_rect.right + gap, body.top, body.right - list_rect.right - gap, body.height)
        inner = self._panel(surface, panel)
        y = inner.top
        suite = self.selected_suite
        if suite is None:
            y = self._blit(
                surface,
                t("Saved runs", "Historique"),
                fonts.normal,
                palette.accent,
                inner.left,
                y,
                inner.width,
            )
            y = self._paragraph(
                surface,
                t(
                    "Open a run saved in the data folder, then compare it with another one.",
                    "Ouvrir un passage enregistré dans le dossier de données, puis le comparer à un autre.",
                ),
                fonts.small,
                palette.text,
                inner,
                y + 4,
            )
        else:
            items, _ = resolve(suite, self.packs)
            y = self._blit(
                surface,
                suite_title(suite.id, suite.title),
                fonts.normal,
                palette.accent,
                inner.left,
                y,
                inner.width,
            )
            y = self._paragraph(surface, suite_description(suite.id), fonts.small, palette.text, inner, y + 4)
            y += 6
            counts = t(f"{len(items)} levels", f"{len(items)} niveaux")
            limits = t("limits per level: ", "limites par niveau : ") + limits_text(suite.limits)
            y = self._paragraph(surface, f"{counts} · {limits}", fonts.small, palette.text, inner, y)
            missing = self.missing_line(suite)
            if missing:
                y = self._paragraph(surface, missing, fonts.small, palette.bad, inner, y)
        y += fonts.small.get_linesize()
        self._draw_machine(surface, pygame.Rect(inner.left, y, inner.width, inner.bottom - y), self.machine)

    def _draw_machine(self, surface: pygame.Surface, rect: pygame.Rect, machine: MachineInfo) -> int:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        y = rect.top
        if y + fonts.small.get_linesize() > rect.bottom:
            return y
        y = self._blit(
            surface, t("Machine", "Machine"), fonts.small, palette.accent, rect.left, y, rect.width
        )
        for line in machine_lines(machine):
            y = self._paragraph(surface, line, fonts.small, palette.text, rect, y)
        note = t(
            "Peak memory is traced, which slows the solver: compare nodes/s only with other runs "
            "of this game.",
            "La mémoire est tracée, ce qui ralentit le solveur : ne comparez les nœuds/s qu'avec d'autres "
            "passages de ce jeu.",
        )
        return self._paragraph(surface, note, fonts.small, palette.muted, rect, y + 4)

    # running and results --------------------------------------------------------------------------------

    def _draw_run(self, surface: pygame.Surface, body: pygame.Rect) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        y = body.top
        suite_id = self.run.suite_id if self.run is not None else (self.suite.id if self.suite else "")
        name = suite_title(suite_id, self.suite.title if self.suite else suite_id)
        heading = name
        if self.run is not None:
            heading += " · " + fmt_date(self.run.created_at) + " · " + limits_text(self.run.limits)
        elif self.suite is not None:
            heading += " · " + limits_text(self.suite.limits)
        y = self._blit(surface, heading, fonts.small, palette.muted, body.left, y, body.width)

        if self.view == "running":
            y = self._draw_progress(surface, pygame.Rect(body.left, y + 4, body.width, 0))
        elif self.run is not None:
            y = self._draw_summary(surface, self.run, body.left, y + 4, body.width)
        y += 6

        buttons_h = fonts.normal.get_height() + 12
        table_bottom = body.bottom - buttons_h - 14  # room for the "more below" arrow
        wide = body.width >= 860
        machine = self.run.machine if self.run is not None else self.machine
        side_w = min(360, body.width // 3) if wide else 0
        table = pygame.Rect(body.left, y, body.width - side_w - 16 * wide, table_bottom - y)
        right = self._draw_results_table(surface, table)
        if wide:  # the machine panel right next to the table, not pushed to the far edge
            side = pygame.Rect(right + 16, y, side_w, table.height)
            self._draw_machine(surface, self._panel(surface, side), machine)
        self._draw_buttons(surface, pygame.Rect(body.left, body.bottom - buttons_h, body.width, buttons_h))

    def _draw_progress(self, surface: pygame.Surface, rect: pygame.Rect) -> int:
        palette = self.app.theme.palette
        font = self.app.fonts.normal
        y = self._blit(surface, self.progress_text(), font, palette.text, rect.left, rect.top, rect.width)
        bar = pygame.Rect(rect.left, y + 2, rect.width, 10)
        pygame.draw.rect(surface, palette.panel, bar, border_radius=5)
        if self.total:
            done = bar.copy()
            done.width = bar.width * len(self.results) // self.total
            if done.width:
                pygame.draw.rect(surface, palette.accent, done, border_radius=5)
        small = self.app.fonts.small
        text = t("Total ", "Total ") + fmt_seconds(self.run_ms) + f" · {len(self.results)}/{self.total}"
        return self._blit(surface, text, small, palette.muted, rect.left, bar.bottom + 4, rect.width)

    def _draw_summary(self, surface: pygame.Surface, run: BenchmarkRun, x: int, y: int, width: int) -> int:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        s = run.summary
        score = fonts.normal.render(
            f"{fmt_int(s.nodes_per_s)} {t('nodes/s', 'nœuds/s')}", True, palette.accent
        )
        surface.blit(score, (x, y))
        rest = (
            f"  ·  {t('solved', 'résolus')} {s.solved}/{s.total}  ·  "
            + t("total ", "total ")
            + fmt_seconds(s.total_ms)
        )
        if self.cancelled:
            rest += "  ·  " + t(
                f"cancelled after {len(run.results)} of {self.total}",
                f"annulé après {len(run.results)} sur {self.total}",
            )
        x2 = x + score.get_width()
        label = fonts.small.render(
            fit_text(fonts.small, rest, max(1, width - score.get_width())), True, palette.text
        )
        surface.blit(label, label.get_rect(midleft=(x2, y + score.get_height() // 2)))
        y += score.get_height()
        if self.missing:
            line = t("Not installed, skipped: ", "Non installé, ignoré : ") + ", ".join(
                dict.fromkeys(item.partition("/")[0] for item in self.missing)
            )
            y = self._blit(surface, line, fonts.small, palette.bad, x, y, width)
        return y

    def _draw_results_table(self, surface: pygame.Surface, rect: pygame.Rect) -> int:
        palette = self.app.theme.palette
        headers = [
            t("Level", "Niveau"),
            t("Status", "Statut"),
            t("Pushes", "Poussées"),
            t("Moves", "Coups"),
            t("Nodes", "Nœuds"),
            "ms",
            t("Peak KiB", "Pic Kio"),
        ]
        rows: list[list[tuple[str, RGB]]] = []
        multi = len({r.pack_id for r in self.results}) > 1 or (
            self.suite is not None and len({p.id for p, _ in resolve(self.suite, self.packs)[0]}) > 1
        )
        for r in self.results:
            rows.append(
                [
                    (self.level_label(r.pack_id, r.level_id, multi=multi), palette.text),
                    (status_label(r.status), _status_colour(r.status, palette)),
                    ("–" if r.pushes is None else fmt_int(r.pushes), palette.text),
                    ("–" if r.moves is None else fmt_int(r.moves), palette.text),
                    (fmt_int(r.nodes_expanded), palette.text),
                    (fmt_int(r.elapsed_ms), palette.text),
                    (fmt_int(r.peak_mem_bytes // 1024), palette.text),
                ]
            )
        if self.view == "running" and self.current is not None:
            index, _, entry = self.current
            if index >= len(self.results):
                pack_id = self.current_pack_id()
                rows.append(
                    [
                        (self.level_label(pack_id, entry.id, multi=multi), palette.accent),
                        (t("solving…", "en cours…"), palette.accent),
                    ]
                )
        return self._draw_table(
            surface, rect, headers, rows, self.table_scroll, highlight=self.view == "results"
        )

    def current_pack_id(self) -> str:
        if self.current is None or self.suite is None:
            return ""
        entry = self.current[2]
        items, _ = resolve(self.suite, self.packs)
        return next((pack.id for pack, e in items if e is entry), "")

    def _draw_buttons(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        palette = self.app.theme.palette
        font = self.app.fonts.normal
        if self.view == "running":
            labels = [t("Cancel", "Annuler")]
            selected = 0
        else:
            labels = [label for _, label in self.actions()]
            selected = self.action_index
        if font.size("    ".join(labels))[0] + 24 * len(labels) > rect.width:
            font = self.app.fonts.small
        gap = 12
        widths = [font.size(label)[0] + 24 for label in labels]
        x = rect.centerx - (sum(widths) + gap * (len(labels) - 1)) // 2
        for i, (label, w) in enumerate(zip(labels, widths, strict=True)):
            button = pygame.Rect(x, rect.top, w, rect.height)
            self._buttons.append((i, button))
            if i == selected:
                draw_row_bar(surface, button, palette)
            else:
                pygame.draw.rect(surface, palette.panel, button, border_radius=max(2, rect.height // 4))
            colour = palette.accent if i == selected else palette.text
            text = font.render(label, True, colour)
            surface.blit(text, text.get_rect(center=button.center))
            x += w + gap

    def _draw_table(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        headers: list[str],
        rows: list[list[tuple[str, RGB]]],
        scroll: ScrollList,
        *,
        highlight: bool,
    ) -> int:
        """Column 0 left-aligned and as wide as what is left, the others right-aligned to their content.

        Returns the right edge of the table.
        """
        palette = self.app.theme.palette
        font = self.app.fonts.small
        gap = 14
        widths = [font.size(h)[0] for h in headers]
        for row in rows:
            for i, (text, _) in enumerate(row):
                widths[i] = max(widths[i], font.size(text)[0])
        room = rect.width - 12  # 6 px inset on both sides
        rest = sum(widths[1:]) + gap * (len(headers) - 1)
        if rest + widths[0] > room:
            gap = 8
            rest = sum(widths[1:]) + gap * (len(headers) - 1)
        first_w = max(40, room - rest)
        first_w = min(first_w, widths[0] + 40)  # do not stretch the table across a wide window
        xs = [rect.left + 6]
        x = rect.left + 6 + first_w
        for w in widths[1:]:
            x += gap + w
            xs.append(x)  # right edge of the column

        row_h = font.get_linesize() + 6
        y = rect.top
        for i, header in enumerate(headers):
            label = font.render(fit_text(font, header, first_w if i == 0 else widths[i]), True, palette.muted)
            if i == 0:
                surface.blit(label, (xs[0], y + 3))
            else:
                surface.blit(label, label.get_rect(topright=(xs[i], y + 3)))
        y += row_h
        pygame.draw.line(surface, palette.muted, (rect.left, y - 2), (min(rect.right, xs[-1] + 6), y - 2))
        body = pygame.Rect(rect.left, y, min(rect.width, xs[-1] + 6 - rect.left), max(1, rect.bottom - y))
        scroll.count = len(rows)
        if not rows:
            return body.right
        for index, row_rect in scroll.layout(body, row_h):
            if highlight and index == scroll.selected:
                draw_row_bar(surface, row_rect, palette)
            for i, (text, colour) in enumerate(rows[index]):
                if i == 0:
                    label = font.render(fit_text(font, text, first_w), True, colour)
                    surface.blit(label, label.get_rect(midleft=(xs[0], row_rect.centery)))
                else:
                    label = font.render(text, True, colour)
                    surface.blit(label, label.get_rect(midright=(xs[i], row_rect.centery)))
        scroll.draw_arrows(surface, body, palette.muted)
        return body.right

    # saved runs and comparison -------------------------------------------------------------------------

    def _run_line(self, run: BenchmarkRun) -> str:
        s = run.summary
        return (
            f"{fmt_date(run.created_at)} · {suite_title(run.suite_id, run.suite_id)} · "
            f"{s.solved}/{s.total} · {fmt_int(s.nodes_per_s)} {t('nodes/s', 'nœuds/s')} · "
            f"{run.machine.cpu_model or run.machine.os}"
        )

    def _draw_runs(self, surface: pygame.Surface, body: pygame.Rect) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        if self.runs_purpose == "compare":
            heading = t("Compare this run with:", "Comparer ce passage avec :")
        else:
            heading = t("Saved runs", "Passages enregistrés")
        y = self._blit(surface, heading, fonts.normal, palette.text, body.left, body.top, body.width)
        if not self.saved_runs:
            self._paragraph(
                surface,
                t(
                    "No other run saved yet: run a suite first.",
                    "Aucun autre passage enregistré : lancez une suite.",
                ),
                fonts.small,
                palette.muted,
                body,
                y + 8,
            )
            return
        rect = pygame.Rect(body.left, y + 10, body.width, body.bottom - y - 10)
        row_h = fonts.small.get_linesize() + 12
        for index, row in self.runs_scroll.layout(rect, row_h):
            bar = row.inflate(0, -4)
            selected = index == self.runs_scroll.selected
            if selected:
                draw_row_bar(surface, bar, palette)
            colour = palette.accent if selected else palette.text
            text = fit_text(fonts.small, self._run_line(self.saved_runs[index][1]), bar.width - 20)
            label = fonts.small.render(text, True, colour)
            surface.blit(label, label.get_rect(midleft=(bar.left + 10, bar.centery)))
        self.runs_scroll.draw_arrows(surface, rect, palette.muted)

    def _draw_compare(self, surface: pygame.Surface, body: pygame.Rect) -> None:
        c = self.comparison
        if c is None:
            return
        palette = self.app.theme.palette
        fonts = self.app.fonts
        y = body.top
        y = self._blit(
            surface, "A: " + self._run_line(c.a), fonts.small, palette.muted, body.left, y, body.width
        )
        y = self._blit(
            surface,
            "B: " + self._run_line(c.b) + t(" (this run)", " (ce passage)"),
            fonts.small,
            palette.muted,
            body.left,
            y,
            body.width,
        )
        (ms_a, ms_b), (nps_a, nps_b), (sa, sb) = c.total_ms, c.nodes_per_s, c.solved
        nps = fonts.normal.render(
            f"{fmt_int(nps_a)} » {fmt_int(nps_b)} {t('nodes/s', 'nœuds/s')} ({fmt_pct(_pct(nps_a, nps_b))})",
            True,
            palette.accent,
        )
        surface.blit(nps, (body.left, y + 4))
        y += 4 + nps.get_height()
        totals = (
            t("Time ", "Temps ")
            + f"{fmt_seconds(ms_a)} » {fmt_seconds(ms_b)} ({fmt_pct(_pct(ms_a, ms_b))}) · "
            + t("solved ", "résolus ")
            + f"{sa} » {sb}"
        )
        y = self._blit(surface, totals, fonts.small, palette.text, body.left, y, body.width)
        if c.a.machine != c.b.machine:
            y = self._blit(
                surface,
                t("Different machines or versions.", "Machines ou versions différentes."),
                fonts.small,
                palette.muted,
                body.left,
                y,
                body.width,
            )
        if c.changed:
            y = self._blit(
                surface,
                t(f"{len(c.changed)} status change(s)", f"{len(c.changed)} changement(s) de statut"),
                fonts.small,
                palette.bad,
                body.left,
                y,
                body.width,
            )
        headers = [
            t("Level", "Niveau"),
            "A",
            "B",
            t("Time A", "Temps A"),
            t("Time B", "Temps B"),
            t("Δ time", "Δ temps"),
            t("Δ nodes", "Δ nœuds"),
        ]
        multi = len({r.pack_id for r in (*c.a.results, *c.b.results)}) > 1
        rows = [self._delta_row(d, palette, multi) for d in c.levels]
        table = pygame.Rect(body.left, y + 8, body.width, body.bottom - y - 8)
        self._draw_table(surface, table, headers, rows, self.compare_scroll, highlight=True)

    def _delta_label(self, d: LevelDelta, multi: bool) -> str:
        ref = d.a or d.b
        assert ref is not None  # compare() never pairs two missing sides
        return self.level_label(ref.pack_id, ref.level_id, multi=multi)

    def _delta_row(self, d: LevelDelta, palette: UiPalette, multi: bool) -> list[tuple[str, RGB]]:
        colour = palette.bad if d.status_changed else palette.text
        pct = d.time_pct

        def status(r: LevelResult | None) -> tuple[str, RGB]:
            if r is None:
                return ("–", palette.muted)
            return (
                status_label(r.status),
                palette.bad if d.status_changed else _status_colour(r.status, palette),
            )

        def ms(r: LevelResult | None) -> str:
            return "–" if r is None else fmt_int(r.elapsed_ms)

        pct_colour = palette.text
        if pct is not None and pct <= -5:
            pct_colour = palette.good
        elif pct is not None and pct >= 5:
            pct_colour = palette.bad
        nodes = d.nodes_delta
        return [
            (("! " if d.status_changed else "") + self._delta_label(d, multi), colour),
            status(d.a),
            status(d.b),
            (ms(d.a), palette.text),
            (ms(d.b), palette.text),
            (fmt_pct(pct), pct_colour),
            ("–" if nodes is None else ("+" if nodes > 0 else "") + fmt_int(nodes), palette.text),
        ]


def _pct(a: int, b: int) -> float | None:
    return (b - a) * 100 / a if a > 0 else None


SCENE = BenchmarkScene
