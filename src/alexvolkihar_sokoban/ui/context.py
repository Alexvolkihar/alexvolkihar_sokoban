"""Everything the scenes share besides the window: packs, settings, progress, the saved session, warnings.

``AppContext.load`` never raises for a bad file on disk: a corrupt, too-new or unreadable file, a broken
bundled pack or a broken drop-in level becomes a line in ``warnings`` (shown by the main menu) and the game
runs with what could be read.
"""

from __future__ import annotations

import json
import locale
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from alexvolkihar_sokoban.core.pack import LevelEntry, Pack
from alexvolkihar_sokoban.formats import FormatError
from alexvolkihar_sokoban.formats.detect import load_any
from alexvolkihar_sokoban.formats.jsonfmt import PACK_FORMAT, pack_from_dict, pack_to_dict
from alexvolkihar_sokoban.formats.jsonfmt import VERSION as PACK_VERSION
from alexvolkihar_sokoban.persistence.session import SESSION_FORMAT, SESSION_VERSION, SavedSession
from alexvolkihar_sokoban.persistence.settings import (
    SETTINGS_FORMAT,
    SETTINGS_VERSION,
    Settings,
    default_language,
)
from alexvolkihar_sokoban.persistence.store import JsonStore, LoadResult
from alexvolkihar_sokoban.scoring.records import PROGRESS_FORMAT, PROGRESS_VERSION, Progress
from alexvolkihar_sokoban.ui.i18n import set_language, t

logger = logging.getLogger(__name__)

GENERATED_ID = "generated"
CUSTOM_ID = "custom"
LEVELS_DIR = "levels"  # <data dir>/levels/: drop-in level files, shown as the Custom pack
CUSTOM_EXTENSIONS = (".xsb", ".sok", ".txt", ".json")
FIRST_PACKS = ("lama-original", "microban-1")  # then the other bundled packs alphabetically


@dataclass(frozen=True)
class ContinueTarget:
    """What the main menu's Continue opens: a level, plus the session to resume when there is one."""

    pack: Pack
    level_id: str
    session: SavedSession | None


def _system_locale() -> str | None:
    try:
        return locale.getlocale()[0]
    except (ValueError, TypeError):
        return None


def _generated_pack(levels: Sequence[LevelEntry] = ()) -> Pack:
    return Pack(GENERATED_ID, "Generated", tuple(levels), source="alexvolkihar-sokoban generate")


def load_bundled_packs(root: Traversable | None = None) -> tuple[list[Pack], list[str]]:
    """Every ``*.json`` pack of ``root`` (default: the package's ``data/levels``), in file name order.

    A broken file or level is skipped and described in the returned warnings.
    """
    if root is None:
        root = files("alexvolkihar_sokoban").joinpath("data/levels")
    packs: list[Pack] = []
    warnings: list[str] = []
    seen: set[str] = set()
    try:
        children = sorted(
            (c for c in root.iterdir() if c.name.lower().endswith(".json")), key=lambda c: c.name
        )
    except OSError as exc:
        logger.warning("cannot list the bundled packs: %s", exc)
        return [], [t(f"Bundled levels unreadable: {exc}", f"Niveaux fournis illisibles : {exc}")]
    for child in children:
        try:
            data = json.loads(child.read_text(encoding="utf-8-sig"))
            level_warnings: list[str] = []
            pack = pack_from_dict(data, warnings=level_warnings)
            if pack.id in seen or pack.id in (GENERATED_ID, CUSTOM_ID):
                raise FormatError(f"pack id {pack.id!r} already used")
        except (OSError, ValueError) as exc:  # FormatError and JSONDecodeError are ValueErrors
            warnings.append(
                t(f"Bundled pack {child.name} skipped: {exc}", f"Pack fourni {child.name} ignoré : {exc}")
            )
            continue
        warnings.extend(level_warnings)
        seen.add(pack.id)
        packs.append(pack)
    return packs, warnings


def _order(packs: Iterable[Pack]) -> list[Pack]:
    def key(pack: Pack) -> tuple[int, str]:
        if pack.id in FIRST_PACKS:
            return (FIRST_PACKS.index(pack.id), "")
        return (len(FIRST_PACKS), pack.id)

    return sorted(packs, key=key)


@dataclass
class AppContext:
    data_dir: Path
    store: JsonStore
    settings: Settings
    progress: Progress
    packs: list[Pack]
    hidden_packs: list[Pack]
    session: SavedSession | None = None
    warnings: list[str] = field(default_factory=list)
    _bundled: list[Pack] = field(default_factory=list, init=False, repr=False)
    _generated: Pack = field(default_factory=_generated_pack, init=False, repr=False)
    _custom: Pack = field(default_factory=lambda: Pack(CUSTOM_ID, "Custom", ()), init=False, repr=False)

    # -- loading -----------------------------------------------------------------------------------------

    @classmethod
    def load(cls, data_dir: Path, *, bundled: Sequence[Pack] | None = None) -> AppContext:
        """Read everything from ``data_dir``; ``bundled`` replaces the package's packs (tests)."""
        store = JsonStore(data_dir)
        warnings: list[str] = []

        loaded = store.load("settings", format_id=SETTINGS_FORMAT, version=SETTINGS_VERSION)
        if loaded.data is not None:
            settings = Settings.from_dict(loaded.data)
        else:
            settings = Settings(language=default_language(_system_locale()))
        # Every later message, starting with this file's own warning, is in the player's language.
        set_language(settings.language)
        warnings.extend(_store_warning("settings.json", loaded, t("settings", "paramètres")))

        loaded = store.load("progress", format_id=PROGRESS_FORMAT, version=PROGRESS_VERSION)
        progress = Progress.from_dict(loaded.data) if loaded.data is not None else Progress()
        warnings.extend(_store_warning("progress.json", loaded, t("progress", "progression")))

        session = _load_session(store, warnings)

        if bundled is None:
            bundled_packs, bundled_warnings = load_bundled_packs()
            warnings.extend(bundled_warnings)
        else:
            bundled_packs = list(bundled)

        ctx = cls(
            data_dir=data_dir,
            store=store,
            settings=settings,
            progress=progress,
            packs=[],
            hidden_packs=[],
            session=session,
            warnings=warnings,
        )
        ctx._bundled = bundled_packs
        ctx._generated = ctx._load_generated()
        ctx._custom = ctx._load_custom()
        ctx._rebuild()
        return ctx

    def _load_generated(self) -> Pack:
        loaded = self.store.load(GENERATED_ID, format_id=PACK_FORMAT, version=PACK_VERSION)
        self.warnings.extend(
            _store_warning("generated.json", loaded, t("generated levels", "niveaux générés"))
        )
        if loaded.data is None:
            return _generated_pack()
        level_warnings: list[str] = []
        try:
            stored = pack_from_dict(
                {"format": PACK_FORMAT, "version": PACK_VERSION, **loaded.data}, warnings=level_warnings
            )
        except FormatError as exc:
            self.warnings.append(
                t(f"Generated levels unreadable: {exc}", f"Niveaux générés illisibles : {exc}")
            )
            return _generated_pack()
        self.warnings.extend(level_warnings)
        return _generated_pack(stored.levels)

    def _load_custom(self) -> Pack:
        folder = self.levels_dir
        try:
            folder.mkdir(parents=True, exist_ok=True)
            paths = sorted(
                (p for p in folder.iterdir() if p.suffix.lower() in CUSTOM_EXTENSIONS and p.is_file()),
                key=lambda p: p.name,
            )
        except OSError as exc:
            logger.warning("cannot list %s: %s", folder, exc)
            paths = []
        entries: list[LevelEntry] = []
        seen: set[str] = set()
        for path in paths:
            try:
                pack, level_warnings = load_any(path)
            except FormatError as exc:
                where = path.name if exc.line is None else f"{path.name}:{exc.line}"
                self.warnings.append(
                    t(f"Level file {where} skipped: {exc.reason}", f"Fichier {where} ignoré : {exc.reason}")
                )
                continue
            for message in level_warnings:
                self.warnings.append(f"{path.name}: {message}")
            if path.stem in seen:
                self.warnings.append(
                    t(
                        f"{path.name} skipped: another file is already named {path.stem!r}",
                        f"{path.name} ignoré : un autre fichier s'appelle déjà {path.stem!r}",
                    )
                )
                continue
            seen.add(path.stem)
            entries.extend(
                LevelEntry(f"{path.stem}/{e.id}", e.level, par=e.par, seed=e.seed) for e in pack.levels
            )
        return Pack(CUSTOM_ID, "Custom", tuple(entries), source=str(folder))

    def _rebuild(self) -> None:
        visible = _order(p for p in self._bundled if not p.hidden)
        self.packs = [*visible, self._generated, self._custom]
        self.hidden_packs = _order(p for p in self._bundled if p.hidden)

    # -- packs -------------------------------------------------------------------------------------------

    @property
    def levels_dir(self) -> Path:
        """``<data dir>/levels/``, where the player drops level files."""
        return self.data_dir / LEVELS_DIR

    def all_packs(self) -> list[Pack]:
        return [*self.packs, *self.hidden_packs]

    def pack(self, pack_id: str) -> Pack:
        """The visible or hidden pack ``pack_id``. Raises ``KeyError``."""
        for pack in self.all_packs():
            if pack.id == pack_id:
                return pack
        raise KeyError(pack_id)

    def add_generated_level(self, entry: LevelEntry) -> Pack:
        """Append ``entry`` to the Generated pack (replacing a level with the same id) and save the pack."""
        levels = list(self._generated.levels)
        ids = [e.id for e in levels]
        if entry.id in ids:
            levels[ids.index(entry.id)] = entry
        else:
            levels.append(entry)
        self._generated = _generated_pack(levels)
        self._rebuild()
        self._save(GENERATED_ID, pack_to_dict(self._generated), PACK_FORMAT, PACK_VERSION, "generated levels")
        return self._generated

    def reload_custom(self) -> None:
        """Re-read ``<data dir>/levels/`` (new or changed files); problems go to ``warnings``."""
        self._custom = self._load_custom()
        self._rebuild()

    def continue_target(self) -> ContinueTarget | None:
        """The saved session if its level still exists, else the last played level, else ``None``."""
        if self.session is not None:
            found = self._find(self.session.pack_id, self.session.level_id, self.session.level_hash)
            if found is not None:
                return ContinueTarget(found[0], found[1], self.session)
        last = self.progress.last_played
        if last is not None:
            found = self._find(last.pack_id, last.level_id, last.level_hash)
            if found is not None:
                return ContinueTarget(found[0], found[1], None)
        return None

    def _find(self, pack_id: str, level_id: str, level_hash: str) -> tuple[Pack, str] | None:
        """The level by pack and id when its layout is unchanged, else the first level with that hash."""
        try:
            pack = self.pack(pack_id)
            if pack.entry(level_id).level.canonical_hash() == level_hash:
                return pack, level_id
        except KeyError:
            pass
        for pack in self.all_packs():
            for entry in pack.levels:
                if entry.level.canonical_hash() == level_hash:
                    return pack, entry.id
        return None

    # -- saving ------------------------------------------------------------------------------------------

    def save_settings(self) -> bool:
        return self._save("settings", self.settings.to_dict(), SETTINGS_FORMAT, SETTINGS_VERSION, "settings")

    def save_progress(self) -> bool:
        return self._save("progress", self.progress.to_dict(), PROGRESS_FORMAT, PROGRESS_VERSION, "progress")

    def save_session(self, session: SavedSession | None) -> bool:
        """Save the game in progress; ``None`` deletes the file (level won or abandoned)."""
        self.session = session
        if session is None:
            self.store.delete("session")
            return not self.store.path("session").exists()
        return self._save("session", session.to_dict(), SESSION_FORMAT, SESSION_VERSION, "session")

    def pop_warnings(self) -> list[str]:
        """The warnings not shown yet; the list is emptied."""
        out, self.warnings = self.warnings, []
        return out

    def _save(self, name: str, payload: dict[str, object], format_id: str, version: int, what: str) -> bool:
        if self.store.save(name, payload, format_id=format_id, version=version):
            return True
        message = _SAVE_FAILED[what]()
        if message not in self.warnings:
            self.warnings.append(message)
        return False


_SAVE_FAILED: dict[str, Callable[[], str]] = {
    "settings": lambda: t("Could not save the settings.", "Impossible d'enregistrer les paramètres."),
    "progress": lambda: t("Could not save the progress.", "Impossible d'enregistrer la progression."),
    "session": lambda: t(
        "Could not save the game in progress.", "Impossible d'enregistrer la partie en cours."
    ),
    "generated levels": lambda: t(
        "Could not save the generated levels.", "Impossible d'enregistrer les niveaux générés."
    ),
}


def _store_warning(file_name: str, loaded: LoadResult, what: str) -> list[str]:
    if loaded.status == "corrupt":
        if loaded.backup_path is not None:
            backup = loaded.backup_path.name
            return [
                t(
                    f"The {what} file {file_name} was damaged: backed up as {backup}, defaults used.",
                    f"Le fichier de {what} {file_name} était abîmé : copié en {backup}, "
                    "valeurs par défaut utilisées.",
                )
            ]
        return [
            t(
                f"The {what} file {file_name} could not be read: defaults used.",
                f"Le fichier de {what} {file_name} est illisible : valeurs par défaut utilisées.",
            )
        ]
    if loaded.status == "too_new":
        return [
            t(
                f"The {what} file {file_name} comes from a newer version: "
                "it is left untouched and not saved.",
                f"Le fichier de {what} {file_name} vient d'une version plus récente : "
                "il est conservé tel quel et ne sera pas modifié.",
            )
        ]
    return []


def _load_session(store: JsonStore, warnings: list[str]) -> SavedSession | None:
    what = t("saved game", "partie sauvegardée")
    loaded = store.load("session", format_id=SESSION_FORMAT, version=SESSION_VERSION)
    warnings.extend(_store_warning("session.json", loaded, what))
    if loaded.data is None:
        return None
    try:
        return SavedSession.from_dict(loaded.data)
    except ValueError as exc:
        logger.warning("ignoring session.json: %s", exc)
        warnings.append(
            t(
                "The saved game could not be resumed and was ignored.",
                "La partie sauvegardée n'a pas pu être reprise et a été ignorée.",
            )
        )
        return None
