#!/usr/bin/env python3
"""Bootstrap and health-check entrypoint.

Usage:
  python scripts/bootstrap.py            Full setup: venv + install deps + health
                                         Then guided config/token if none exists.
  python scripts/bootstrap.py -i         Force the guided interactive onboarding.
  python scripts/bootstrap.py --health   Local readiness check only (no install)
  jira health                            (routed here) readiness check only

Safe to rerun; idempotent. Does NOT re-exec into the venv (it creates it).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jira_common import setup as setup_mod  # noqa: E402


def _print(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def run_health() -> int:
    ok, notes = setup_mod.health_check()
    _print("Health check:")
    for n in notes:
        _print(f"  - {n}")
    _print(f"Result: {'READY' if ok else 'NOT READY'}")
    return 0 if ok else 1


def run_bootstrap(interactive: bool = False) -> int:
    _print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    if not setup_mod.python_version_ok():
        _print(f"ERROR: Python {setup_mod.MIN_PYTHON[0]}.{setup_mod.MIN_PYTHON[1]}+ required.")
        return 1

    _print(f"Skill root: {setup_mod.skill_root()}")

    if setup_mod.venv_exists():
        _print(f"Virtual environment present: {setup_mod.venv_dir()}")
    else:
        _print("Creating virtual environment (.venv) ...")
        setup_mod.create_venv()
        _print(f"  created: {setup_mod.venv_dir()}")

    if setup_mod.imports_ok():
        _print("Dependencies present (requests importable).")
    else:
        _print("Installing dependencies from assets/requirements.txt ...")
        setup_mod.install_requirements()
        _print("  dependencies installed.")

    _print("")
    _print(f"Interpreter to use for all commands:\n  {setup_mod.venv_python()}")
    _print("")

    _, notes = setup_mod.health_check()
    _print("Health check:")
    for n in notes:
        _print(f"  - {n}")

    if not _config_exists():
        # Guided onboarding: prompt when forced (-i) or on an interactive shell.
        if interactive or sys.stdin.isatty():
            _print("")
            _print("No profile configured yet — starting guided setup.")
            _print("")
            return _run_onboarding()
        _print("")
        _print("Next steps:")
        _print("  python scripts/bootstrap.py -i     # guided setup (recommended)")
        _print('  jira setup --base-url "https://jira.example.com" --default-project ABC')
        _print("  jira auth set-token          # enter your PAT securely")
        _print("  jira auth test-auth          # validate against /myself")
    return 0


def _run_onboarding() -> int:
    """Run the interactive profile+token setup through the venv interpreter."""
    vpy = setup_mod.venv_python()
    jira_entry = setup_mod.skill_root() / "scripts" / "jira.py"
    result = subprocess.run([str(vpy), str(jira_entry), "setup", "--interactive"],
                            check=False)
    return result.returncode


def _config_exists() -> bool:
    from jira_common import config as config_mod

    return config_mod.config_exists()


def main() -> None:
    parser = argparse.ArgumentParser(prog="bootstrap")
    parser.add_argument("mode", nargs="?", default="bootstrap",
                        help="'bootstrap' (default) or 'health'.")
    parser.add_argument("--health", action="store_true", help="Health check only.")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Force guided config + token onboarding.")
    args, _unknown = parser.parse_known_args()

    if args.health or args.mode == "health":
        sys.exit(run_health())
    sys.exit(run_bootstrap(interactive=args.interactive))


if __name__ == "__main__":
    main()
