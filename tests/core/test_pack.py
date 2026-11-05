import pytest

from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.core.pack import LevelEntry, Pack, Par

LV = Level.from_rows(["#####", "#@$.#", "#####"], title="Corridor")
LV2 = Level.from_rows(["######", "#@$ .#", "######"])


def _pack() -> Pack:
    par = Par(pushes=1, moves=1, lurd="R", solver="push-astar/1")
    return Pack(
        id="p",
        title="Pack",
        levels=(LevelEntry("a", LV, par), LevelEntry("b", LV2), LevelEntry("c", LV, seed=7)),
    )


def test_pack_navigation() -> None:
    pack = _pack()
    assert pack.entry("b").level is LV2
    assert pack.index_of("a") == 0 and pack.index_of("c") == 2
    assert pack.next_id("a") == "b" and pack.next_id("b") == "c" and pack.next_id("c") is None


def test_unknown_level_id_raises_key_error() -> None:
    pack = _pack()
    with pytest.raises(KeyError):
        pack.entry("zz")
    with pytest.raises(KeyError):
        pack.index_of("zz")
    with pytest.raises(KeyError):
        pack.next_id("zz")


def test_defaults_and_title() -> None:
    pack = _pack()
    assert (pack.author, pack.license, pack.source, pack.hidden) == ("", "", "", False)
    a, b, c = pack.levels
    assert a.title == "Corridor" and b.title == "b"
    assert a.par is not None and a.par.pushes == 1 and b.par is None and c.seed == 7 and a.seed is None


def test_pack_is_frozen() -> None:
    with pytest.raises(AttributeError):
        _pack().title = "x"  # type: ignore[misc]
