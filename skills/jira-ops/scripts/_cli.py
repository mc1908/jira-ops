"""Shared CLI helpers: venv re-exec, arg wiring, error handling."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Make ``jira_common`` importable when scripts are run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jira_common import setup as setup_mod  # noqa: E402
from jira_common.config import Config, Profile, load  # noqa: E402
from jira_common.errors import JiraOpsError  # noqa: E402
from jira_common.formatting import emit  # noqa: E402


def ensure_venv() -> None:
    """Re-exec the current script through the skill-local venv interpreter.

    Skipped when already in the venv, when JIRA_OPS_NO_VENV is set, or when the
    venv does not exist yet (e.g. during bootstrap).
    """
    if os.environ.get("JIRA_OPS_NO_VENV"):
        return
    if setup_mod.in_target_venv():
        return
    vpy = setup_mod.venv_python()
    if not vpy.is_file():
        return
    # NOTE: os.execv is avoided because on Windows the C runtime re-joins argv
    # into a single command line without quoting, which splits arguments that
    # contain spaces (e.g. a comment --body). subprocess quotes correctly and
    # is cross-platform; the child sees itself as the venv interpreter, so
    # in_target_venv() short-circuits any further re-exec.
    result = subprocess.run([str(vpy), *sys.argv], check=False)
    sys.exit(result.returncode)


def load_profile(name: str | None) -> Profile:
    cfg: Config = load()
    return cfg.get(name)


def resolve_project(explicit: str | None, profile: Profile) -> str:
    """Return the explicit project key, else the profile default, else error."""
    project = explicit or profile.default_project
    if not project:
        raise JiraOpsError(
            "config",
            "No project specified and no default configured. Pass --project KEY "
            "or set one with 'jira setup --default-project KEY'.",
        )
    return project


def add_common_args(parser) -> None:
    parser.add_argument("--profile", help="Config profile name (default: configured default).")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Emit machine-readable JSON.")


def run(main_func) -> None:
    """Wrap a command main() with normalized error handling + exit codes."""
    try:
        main_func()
    except JiraOpsError as exc:
        _emit_error(exc)
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        sys.stderr.write("\nAborted.\n")
        sys.exit(130)


def _emit_error(exc: JiraOpsError) -> None:
    as_json = "--json" in sys.argv
    if as_json:
        emit(exc.to_dict(), as_json=True)
    else:
        sys.stderr.write(f"[{exc.category}] {exc.message}\n")
        if exc.hint:
            sys.stderr.write(f"  hint: {exc.hint}\n")
