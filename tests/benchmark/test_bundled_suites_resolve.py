"""The bundled suites resolve against the bundled packs, with no missing item."""

import json
from importlib.resources import files

from alexvolkihar_sokoban.benchmark.suites import load_bundled_packs, load_suites, resolve


def test_bundled_packs_load_without_warnings() -> None:
    packs, warnings = load_bundled_packs()
    assert warnings == []
    assert {"lama-original", "lama-unsolvable", "boxoban-hard", "bench-extra"} <= set(packs)


def test_quick_suite_has_no_missing_item() -> None:
    packs, _ = load_bundled_packs()
    items, missing = resolve(load_suites()["quick"], packs)
    assert missing == [] and len(items) == len(packs["lama-original"].levels)


def test_every_suite_resolves_without_missing_items() -> None:
    packs, _ = load_bundled_packs()
    for suite in load_suites().values():
        items, missing = resolve(suite, packs)
        assert items and missing == [], (suite.id, missing)


def test_suites_name_no_pack_that_is_not_shipped() -> None:
    """Microban is not shipped (licence): neither its items nor its name may appear in the suites file."""
    text = files("alexvolkihar_sokoban").joinpath("data/benchmarks/suites.json").read_text(encoding="utf-8")
    assert "microban" not in text.lower()
    for suite in json.loads(text)["suites"]:
        assert "Boxoban" in suite["description"] or suite["id"] == "quick", suite["id"]
