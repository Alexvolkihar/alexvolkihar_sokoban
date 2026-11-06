"""Packaging checks: bundled data reachable through ``importlib.resources``, single-sourced version, and
(when ``AVS_DIST`` names a folder holding a built wheel and sdist) the content of the distributions.

CI's build job runs this file from a fresh virtual environment where only the wheel is installed, with
``AVS_DIST=dist``: the resource tests then read the installed package, not ``src/``.
"""

import os
import tarfile
import tomllib
import zipfile
from importlib.metadata import entry_points, metadata, version
from importlib.resources import files
from pathlib import Path

import pytest

import alexvolkihar_sokoban

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
DIST = os.environ.get("AVS_DIST")
PACKAGE_DIR = Path(alexvolkihar_sokoban.__file__).resolve().parent
INSTALLED = not PACKAGE_DIR.is_relative_to(REPO / "src")

LEVEL_PACKS = ["lama-original.json", "lama-unsolvable.json", "boxoban-hard.json", "boxoban-hard.LICENSE.txt"]
BENCHMARKS = ["suites.json", "extra.json"]
KENNEY = [
    "Character4.png",
    "Crate_Brown.png",
    "EndPoint_Brown.png",
    "WallRound_Brown.png",
    "empty.png",
    "icon.png",
    "LICENSE.txt",
]
DATA_FILES = (
    [f"levels/{name}" for name in LEVEL_PACKS]
    + [f"benchmarks/{name}" for name in BENCHMARKS]
    + [f"themes/kenney/{name}" for name in KENNEY]
)
SCHEMAS = sorted(p.name for p in (REPO / "schemas").glob("*.schema.json"))


# -- bundled data -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", DATA_FILES)
def test_bundled_data_found_via_importlib_resources(name: str) -> None:
    resource = files("alexvolkihar_sokoban").joinpath("data").joinpath(*name.split("/"))
    assert resource.is_file(), name
    assert resource.read_bytes(), name


def test_kenney_pngs_are_png_files() -> None:
    folder = files("alexvolkihar_sokoban").joinpath("data/themes/kenney")
    for name in KENNEY:
        if name.endswith(".png"):
            assert folder.joinpath(name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", name


def test_schemas_exist_in_the_repository() -> None:
    assert "pack.schema.json" in SCHEMAS and "level.schema.json" in SCHEMAS


# -- version and metadata -----------------------------------------------------------------------------------


def test_version_is_1_0_0() -> None:
    assert alexvolkihar_sokoban.__version__ == "1.0.0"


def test_version_is_single_sourced() -> None:
    assert "version" not in PYPROJECT["project"]
    assert "version" in PYPROJECT["project"]["dynamic"]
    assert PYPROJECT["tool"]["hatch"]["version"]["path"] == "src/alexvolkihar_sokoban/__init__.py"


def test_installed_metadata_matches_the_package_version() -> None:
    assert version("alexvolkihar-sokoban") == alexvolkihar_sokoban.__version__


def test_console_script_entry_point() -> None:
    scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert scripts.get("alexvolkihar-sokoban") == "alexvolkihar_sokoban.cli:main"


def test_project_metadata() -> None:
    project = PYPROJECT["project"]
    assert project["readme"] == "README.en.md"
    assert project["requires-python"] == ">=3.11"
    assert project["dependencies"] == ["pygame-ce>=2.5", "platformdirs>=4"]
    classifiers = set(project["classifiers"])
    assert "Development Status :: 5 - Production/Stable" in classifiers
    assert "Topic :: Games/Entertainment :: Puzzle Games" in classifiers
    for minor in (11, 12, 13, 14):
        assert f"Programming Language :: Python :: 3.{minor}" in classifiers
    repo_url = "https://github.com/Alexvolkihar/alexvolkihar_sokoban"
    urls = project["urls"]
    assert urls["Homepage"] == repo_url
    assert urls["Source"] == repo_url
    assert urls["Issues"] == f"{repo_url}/issues"
    assert urls["Changelog"] == f"{repo_url}/blob/main/CHANGELOG.md"


def test_mit_licence_and_single_author() -> None:
    project = PYPROJECT["project"]
    assert project["license"] == "MIT"
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert project["authors"] == [{"name": "Alexis MABANZA"}]
    for path in project["license-files"]:
        assert (REPO / path).is_file(), path
    licence = (REPO / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("MIT License\n") and "Copyright (c) 2026 Alexis MABANZA" in licence


def test_installed_metadata_has_readme_and_urls() -> None:
    meta = metadata("alexvolkihar-sokoban")
    assert meta["Description-Content-Type"] == "text/markdown"
    assert "Sokoban" in str(meta.json["description"])
    assert any("github.com/Alexvolkihar/alexvolkihar_sokoban" in url for url in meta.get_all("Project-URL"))


def test_wheel_maps_the_schemas_into_the_package() -> None:
    force = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force == {"schemas": "alexvolkihar_sokoban/schemas"}


# -- installed wheel (CI build job) -------------------------------------------------------------------------


@pytest.mark.skipif(not INSTALLED, reason="package imported from src/ (editable install)")
@pytest.mark.parametrize("name", SCHEMAS)
def test_installed_package_ships_the_schemas(name: str) -> None:
    assert files("alexvolkihar_sokoban").joinpath("schemas").joinpath(name).is_file()


# -- built distributions (AVS_DIST) -------------------------------------------------------------------------


def _one(pattern: str) -> Path:
    assert DIST is not None
    found = sorted(Path(DIST).glob(pattern))
    assert len(found) == 1, f"expected one {pattern} in {DIST}, found {found}"
    return found[0]


@pytest.mark.skipif(DIST is None, reason="set AVS_DIST to a folder holding the built wheel and sdist")
def test_wheel_content() -> None:
    wheel = _one("alexvolkihar_sokoban-*.whl")
    assert wheel.name.startswith(f"alexvolkihar_sokoban-{alexvolkihar_sokoban.__version__}-py3-none-any")
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        dist_info = f"alexvolkihar_sokoban-{alexvolkihar_sokoban.__version__}.dist-info"
        entry = zf.read(f"{dist_info}/entry_points.txt").decode()
        meta = zf.read(f"{dist_info}/METADATA").decode()
    for name in DATA_FILES:
        assert f"alexvolkihar_sokoban/data/{name}" in names, name
    for name in SCHEMAS:
        assert f"alexvolkihar_sokoban/schemas/{name}" in names, name
    assert "alexvolkihar_sokoban/cli.py" in names
    assert not any(n.startswith(("tests/", "legacy/", "docs/")) or "__pycache__" in n for n in names)
    assert "alexvolkihar-sokoban = alexvolkihar_sokoban.cli:main" in entry
    assert f"Version: {alexvolkihar_sokoban.__version__}" in meta
    assert "License-Expression: MIT" in meta and f"{dist_info}/licenses/LICENSE" in names


SDIST_FILES = [
    "pyproject.toml",
    "README.md",
    "README.en.md",
    "LICENSE",
    "src/alexvolkihar_sokoban/__init__.py",
]


@pytest.mark.skipif(DIST is None, reason="set AVS_DIST to a folder holding the built wheel and sdist")
def test_sdist_content() -> None:
    sdist = _one("alexvolkihar_sokoban-*.tar.gz")
    root = f"alexvolkihar_sokoban-{alexvolkihar_sokoban.__version__}"
    assert sdist.name == f"{root}.tar.gz"
    with tarfile.open(sdist) as tf:
        names = {n.removeprefix(f"{root}/") for n in tf.getnames()}
    for name in SDIST_FILES:
        assert name in names, name
    for name in DATA_FILES:
        assert f"src/alexvolkihar_sokoban/data/{name}" in names, name
    for name in SCHEMAS:
        assert f"schemas/{name}" in names, name
    assert not any(n.startswith(("legacy/", ".github/", ".superpowers/")) for n in names)
