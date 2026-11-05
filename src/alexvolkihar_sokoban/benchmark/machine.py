"""Machine description recorded with every benchmark run (spec 7.7).

Results are meant to be shared, so nothing here may identify the computer or its user: no hostname
(``platform.node()``), no user name, no paths. pygame is never imported; its version comes from the installed
distribution's metadata.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from alexvolkihar_sokoban import __version__

PROC = Path("/proc")


@dataclass(frozen=True)
class MachineInfo:
    os: str
    os_version: str
    arch: str
    is_wsl: bool
    cpu_model: str | None
    cpu_count_logical: int | None
    ram_total_bytes: int | None
    python: str
    pygame_ce: str | None
    app_version: str


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def is_wsl(proc_version: str | None) -> bool:
    """True when ``/proc/version`` names a Microsoft kernel (WSL 1 and WSL 2)."""
    return proc_version is not None and "microsoft" in proc_version.lower()


def cpu_model_from_cpuinfo(text: str) -> str | None:
    """The first ``model name`` of ``/proc/cpuinfo`` (``Hardware``/``Model`` on some ARM boards)."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if sep and value and key not in found:
            found[key] = value
    for key in ("model name", "hardware", "model", "cpu model", "processor model"):
        if key in found and not found[key].isdigit():
            return found[key]
    return None


def ram_from_meminfo(text: str) -> int | None:
    """``MemTotal`` of ``/proc/meminfo`` in bytes."""
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
    return None


def _sysctl(name: str) -> str | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=5, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def _cpu_model(proc_dir: Path) -> str | None:
    if sys.platform == "darwin":
        return _sysctl("machdep.cpu.brand_string")
    text = _read(proc_dir / "cpuinfo")
    if text is not None:
        model = cpu_model_from_cpuinfo(text)
        if model:
            return model
    return platform.processor() or None


def _ram_windows() -> int | None:
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    windll = getattr(ctypes, "windll", None)
    if windll is None or not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys) or None


def _ram_total(proc_dir: Path) -> int | None:
    try:
        if sys.platform == "win32":
            return _ram_windows()
        if sys.platform == "darwin":
            value = _sysctl("hw.memsize")
            return int(value) if value and value.isdigit() else None
        text = _read(proc_dir / "meminfo")
        if text is not None:
            return ram_from_meminfo(text)
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, AttributeError):
        return None


def _os_version() -> str:
    system = platform.system()
    if system == "Darwin":
        return platform.mac_ver()[0] or platform.release()
    if system == "Windows":
        return platform.version()
    release = platform.release()
    try:
        pretty = platform.freedesktop_os_release().get("PRETTY_NAME", "")
    except OSError:
        pretty = ""
    return f"{pretty} (kernel {release})" if pretty else release


def _pygame_ce_version() -> str | None:
    try:
        return metadata.version("pygame-ce")
    except metadata.PackageNotFoundError:
        return None


def collect_machine_info(*, proc_dir: Path = PROC) -> MachineInfo:
    """Describe this machine. ``proc_dir`` replaces ``/proc`` (tests); unreadable files give ``None``."""
    return MachineInfo(
        os=platform.system() or sys.platform,
        os_version=_os_version(),
        arch=platform.machine() or "unknown",
        is_wsl=is_wsl(_read(proc_dir / "version")),
        cpu_model=_cpu_model(proc_dir),
        cpu_count_logical=os.cpu_count(),
        ram_total_bytes=_ram_total(proc_dir),
        python=f"{platform.python_implementation()} {platform.python_version()}",
        pygame_ce=_pygame_ce_version(),
        app_version=__version__,
    )
