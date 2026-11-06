import argparse

import pytest


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    from alexvolkihar_sokoban.cli import main

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0 and "1.0.0" in capsys.readouterr().out


def test_all_subcommands_registered() -> None:
    from alexvolkihar_sokoban.cli import build_parser

    sub = {"play", "solve", "convert", "annotate", "bench", "generate"}
    actions = [a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction)]
    assert sub <= set(actions[0].choices)


def test_package_version_attribute() -> None:
    import alexvolkihar_sokoban

    assert alexvolkihar_sokoban.__version__ == "1.0.0"


def test_no_subcommand_runs_play_without_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from alexvolkihar_sokoban import cli
    from alexvolkihar_sokoban.commands import play

    seen: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace) -> int:
        seen.append(args)
        return 0

    monkeypatch.setattr(play, "run", fake_run)
    assert cli.main([]) == 0
    assert seen and seen[0].path is None


def test_global_data_dir_option(monkeypatch: pytest.MonkeyPatch) -> None:
    from alexvolkihar_sokoban import cli
    from alexvolkihar_sokoban.commands import play

    seen: list[argparse.Namespace] = []
    monkeypatch.setattr(play, "run", lambda args: seen.append(args) or 0)
    assert cli.main(["--data-dir", "/tmp/x", "play"]) == 0
    assert seen[0].data_dir == "/tmp/x"


def test_python_dash_m_entry_point() -> None:
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "alexvolkihar_sokoban", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0 and "1.0.0" in out.stdout


def test_importing_main_module_does_not_run_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    from alexvolkihar_sokoban import cli

    def boom(argv: list[str] | None = None) -> int:
        raise AssertionError("cli.main ran on import")

    monkeypatch.setattr(cli, "main", boom)
    monkeypatch.delitem(sys.modules, "alexvolkihar_sokoban.__main__", raising=False)
    importlib.import_module("alexvolkihar_sokoban.__main__")
