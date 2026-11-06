"""README checks: links and images resolve, the English README works off GitHub, required topics are covered.

``README.en.md`` is the wheel's long description (PyPI-style pages, ``pip show``), where relative links do
not resolve: it must only use absolute ``github.com`` URLs, and those pointing into this repository must
name files that exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/Alexvolkihar/alexvolkihar_sokoban"
REPO_PREFIXES = tuple(f"{REPO_URL}/{kind}/main/" for kind in ("blob", "raw", "tree"))
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img [^>]*src=\"([^\"]+)\"|<a [^>]*href=\"([^\"]+)\"")
# Built from pieces so that this file does not match the repository-wide attribution grep itself.
ATTRIBUTION = re.compile(
    "|".join(["co-" + "authored", "clau" + "de", "anthro" + "pic", "generated " + "with"]), re.I
)
REQUIRED = [
    "docs/media/demo.gif",
    "docs/media/demo.mp4",
    "Alexis MABANZA",
    "github.com/Alexvolkihar/Sokoban-LAMA",
    "LICENSE",
    "MIT",
    *(f"{shot}.png" for shot in ("menu", "level-select", "gameplay", "themes", "hint", "replay")),
    *(f"{shot}.png" for shot in ("random-level", "benchmark", "credits")),
    "pipx install",
    *(f"alexvolkihar-sokoban {cmd}" for cmd in ("play", "solve", "convert", "annotate", "bench", "generate")),
    "bench compare",
    "--data-dir",
    "ALEXVOLKIHAR_SOKOBAN_HOME",
    "Boxoban",
    "Apache",
    "Kenney",
    "CC0",
    "docs/formats.md",
    "scripts/capture.py",
    "CHANGELOG.md",
    "%LOCALAPPDATA%",
    "Library/Application Support",
    ".local/share",
]


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def readme_problems(root: Path, name: str, *, absolute: bool) -> list[str]:
    """Everything wrong with ``root/name``; ``absolute`` forbids relative links."""
    text = (root / name).read_text(encoding="utf-8")
    problems = [f"missing {need!r}" for need in REQUIRED if need not in text]
    if ATTRIBUTION.search(text):
        problems.append("attribution text")
    for match in LINK.finditer(text):
        target = next(group for group in match.groups() if group)
        if target.startswith(("#", "mailto:")):
            continue
        if target.startswith("http"):
            for prefix in REPO_PREFIXES:
                if target.startswith(prefix) and not (root / target[len(prefix) :].split("#")[0]).exists():
                    problems.append(f"dead repository link {target}")
            continue
        if absolute:
            problems.append(f"relative link {target}")
        elif not (root / target.split("#")[0]).exists():
            problems.append(f"dead relative link {target}")
    anchors = {_slug(h) for h in re.findall(r"^#+ (.+)$", text, re.M)}
    problems += [f"dead anchor #{a}" for a in re.findall(r"\]\(#([^)]+)\)", text) if a not in anchors]
    return problems


def test_french_readme_links_resolve() -> None:
    assert readme_problems(ROOT, "README.md", absolute=False) == []


def test_english_readme_uses_absolute_links_that_resolve() -> None:
    assert readme_problems(ROOT, "README.en.md", absolute=True) == []


def test_readmes_link_each_other() -> None:
    assert "README.en.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"{REPO_URL}/blob/main/README.md" in (ROOT / "README.en.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("absolute", [False, True])
def test_the_checker_reports_broken_readmes(tmp_path: Path, absolute: bool) -> None:
    (tmp_path / "there.md").write_text("x", encoding="utf-8")
    body = "\n".join(REQUIRED)
    text = (
        f"# Title\n\n{body}\n\n[ok](there.md) [gone](missing.md) [jump](#nowhere) [top](#title)\n"
        f"![img]({REPO_URL}/raw/main/nope.png) " + "Gener" + "ated with a tool\n"
    )
    (tmp_path / "R.md").write_text(text, encoding="utf-8")
    problems = readme_problems(tmp_path, "R.md", absolute=absolute)
    expected = {
        "dead anchor #nowhere",
        f"dead repository link {REPO_URL}/raw/main/nope.png",
        "attribution text",
    }
    if absolute:
        expected |= {"relative link there.md", "relative link missing.md"}
    else:
        expected |= {"dead relative link missing.md"}
    assert set(problems) == expected
