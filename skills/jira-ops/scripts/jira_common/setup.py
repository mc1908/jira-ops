"""Environment checks, venv creation, dependency install, and health checks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

MIN_PYTHON = (3, 10)


def skill_root() -> Path:
    """Repo/skill root == parent of the scripts/ directory."""
    return Path(__file__).resolve().parents[2]


def venv_dir() -> Path:
    return skill_root() / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def requirements_file() -> Path:
    return skill_root() / "assets" / "requirements.txt"


def python_version_ok() -> bool:
    return sys.version_info[:2] >= MIN_PYTHON


def in_target_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == venv_python().resolve()
    except OSError:
        return False


def venv_exists() -> bool:
    return venv_python().is_file()


def create_venv() -> Path:
    if venv_exists():
        return venv_python()
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir())])
    return venv_python()


def install_requirements(python: Path | None = None) -> None:
    py = str(python or venv_python())
    req = requirements_file()
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
    if req.is_file():
        subprocess.check_call([py, "-m", "pip", "install", "-r", str(req)])


def imports_ok(python: Path | None = None) -> bool:
    py = str(python or venv_python())
    try:
        subprocess.check_call(
            [py, "-c", "import requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def health_check() -> Tuple[bool, List[str]]:
    """Run non-network readiness checks. Returns (ok, notes)."""
    from . import config as config_mod

    notes: List[str] = []
    ok = True

    if not python_version_ok():
        ok = False
        notes.append(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required.")

    if not venv_exists():
        ok = False
        notes.append("Virtual environment missing (.venv). Run bootstrap.")
    elif not imports_ok():
        ok = False
        notes.append("Dependencies missing in .venv. Run bootstrap.")

    if not config_mod.config_exists():
        ok = False
        notes.append("No config found. Run 'jira setup'.")
    else:
        try:
            cfg = config_mod.load()
            cfg.get()  # resolve default profile
            notes.append(f"Config OK (default profile: {cfg.default_profile}).")
        except Exception as exc:  # noqa: BLE001
            ok = False
            notes.append(f"Config invalid: {exc}")

    return ok, notes
