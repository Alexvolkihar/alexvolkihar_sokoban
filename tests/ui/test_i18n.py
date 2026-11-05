from collections.abc import Iterator

import pytest

from alexvolkihar_sokoban.ui.i18n import get_language, set_language, t


@pytest.fixture(autouse=True)
def _restore_language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


def test_t_follows_language() -> None:
    set_language("en")
    assert get_language() == "en"
    assert t("Quit", "Quitter") == "Quit"
    set_language("fr")
    assert get_language() == "fr"
    assert t("Quit", "Quitter") == "Quitter"


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(ValueError):
        set_language("de")  # type: ignore[arg-type]
