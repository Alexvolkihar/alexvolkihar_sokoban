"""UI language. Strings are written inline as ``t(en, fr)``: no shared catalogue (spec 7.9)."""

from __future__ import annotations

from typing import get_args

from alexvolkihar_sokoban.persistence.settings import Language

_language: Language = "en"


def set_language(lang: Language) -> None:
    """Switch every later ``t()`` call to ``lang``. Raises ``ValueError`` for an unsupported language."""
    global _language
    if lang not in get_args(Language):
        raise ValueError(f"unsupported language: {lang!r}")
    _language = lang


def get_language() -> Language:
    return _language


def t(en: str, fr: str) -> str:
    """The string of the current language."""
    if _language == "fr":
        return fr
    return en
