import dataclasses
import getpass
import socket
from pathlib import Path

from alexvolkihar_sokoban import __version__
from alexvolkihar_sokoban.benchmark.machine import MachineInfo, collect_machine_info, is_wsl

CPUINFO = """processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Core(TM) i7-1185G7 @ 3.00GHz

processor\t: 1
model name\t: Intel(R) Core(TM) i7-1185G7 @ 3.00GHz
"""
MEMINFO = "MemTotal:       16303580 kB\nMemFree:         1234567 kB\n"
WSL_VERSION = "Linux version 6.6.36.6-microsoft-standard-WSL2 (root@f8d5d1a1a8c7) (gcc) #1 SMP"
NATIVE_VERSION = "Linux version 6.8.0-45-generic (buildd@lcy02-amd64-075) (gcc) #45-Ubuntu SMP"


def fake_proc(tmp_path: Path, version: str) -> Path:
    (tmp_path / "version").write_text(version, encoding="utf-8")
    (tmp_path / "cpuinfo").write_text(CPUINFO, encoding="utf-8")
    (tmp_path / "meminfo").write_text(MEMINFO, encoding="utf-8")
    return tmp_path


def string_values(info: MachineInfo) -> list[str]:
    return [v for v in dataclasses.asdict(info).values() if isinstance(v, str)]


def test_machine_info_has_no_hostname() -> None:
    info = collect_machine_info()
    hostname = socket.gethostname()
    assert hostname not in dataclasses.asdict(info).values()
    for value in string_values(info):
        assert hostname.lower() not in value.lower() or len(hostname) < 3


def test_machine_info_has_no_user_name() -> None:
    user = getpass.getuser()
    for value in string_values(collect_machine_info()):
        assert len(user) < 3 or user.lower() not in value.lower()
    assert str(Path.home()) not in str(dataclasses.asdict(collect_machine_info()))


def test_machine_info_basics() -> None:
    info = collect_machine_info()
    assert info.app_version == __version__
    assert info.os and info.arch and info.python
    assert info.cpu_count_logical is None or info.cpu_count_logical >= 1
    assert info.ram_total_bytes is None or info.ram_total_bytes > 0


def test_wsl_detection(tmp_path: Path) -> None:
    assert is_wsl(WSL_VERSION)
    assert is_wsl("Linux version 4.4.0-19041-Microsoft (Microsoft@Microsoft.com)")
    assert not is_wsl(NATIVE_VERSION)
    assert not is_wsl(None)
    info = collect_machine_info(proc_dir=fake_proc(tmp_path, WSL_VERSION))
    assert info.is_wsl is True


def test_linux_proc_files_give_cpu_and_ram() -> None:
    import alexvolkihar_sokoban.benchmark.machine as machine

    assert machine.cpu_model_from_cpuinfo(CPUINFO) == "Intel(R) Core(TM) i7-1185G7 @ 3.00GHz"
    assert machine.cpu_model_from_cpuinfo("processor\t: 0\nHardware\t: BCM2835\n") == "BCM2835"
    assert machine.cpu_model_from_cpuinfo("nothing useful") is None
    assert machine.ram_from_meminfo(MEMINFO) == 16303580 * 1024
    assert machine.ram_from_meminfo("garbage") is None


def test_unreadable_proc_dir_is_not_an_error(tmp_path: Path) -> None:
    info = collect_machine_info(proc_dir=tmp_path / "missing")
    assert info.is_wsl is False
