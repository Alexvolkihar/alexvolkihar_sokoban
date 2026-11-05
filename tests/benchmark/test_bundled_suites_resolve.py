"""The bundled suites resolve against the bundled packs (only optional Microban items may be missing)."""

from alexvolkihar_sokoban.benchmark.suites import load_bundled_packs, load_suites, resolve

OPTIONAL_PACK = "microban-1"


def test_bundled_packs_load_without_warnings() -> None:
    packs, warnings = load_bundled_packs()
    assert warnings == []
    assert {"lama-original", "lama-unsolvable", "bench-extra"} <= set(packs)


def test_quick_suite_has_no_missing_item() -> None:
    packs, _ = load_bundled_packs()
    items, missing = resolve(load_suites()["quick"], packs)
    assert missing == [] and len(items) == len(packs["lama-original"].levels)


def test_other_suites_miss_only_the_optional_microban_pack() -> None:
    packs, _ = load_bundled_packs()
    for suite in load_suites().values():
        items, missing = resolve(suite, packs)
        assert items, suite.id
        for item in missing:
            assert item.partition("/")[0] == OPTIONAL_PACK, (suite.id, item)
            assert OPTIONAL_PACK not in packs, (suite.id, item)
