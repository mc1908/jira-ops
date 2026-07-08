"""Pytest fixtures + CLI runner for the jira-ops live test suite.

These tests exercise the real Jira instance configured for the skill. They are
**opt-in** and gated by environment variables so a default `pytest` run touches
nothing:

    # read-only + dry-run + error suites (side-effect free)
    JIRA_OPS_LIVE=1 pytest tests/

    # additionally run the real-write suite (creates/reverts on the safe targets)
    JIRA_OPS_LIVE=1 JIRA_OPS_LIVE_WRITE=1 pytest tests/ -m write

Targets (override via env if needed):
    JIRA_OPS_TEST_PROJECT  (default: FASTACTR67)
    JIRA_OPS_TEST_ISSUE    (default: FASTACTR67-578)

The runner shells out to `python scripts/jira.py ... --json` from the skill root
and parses stdout. See tests/live-test-plan.md for the case catalogue.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / "skills" / "jira-ops"
JIRA_PY = SKILL_ROOT / "scripts" / "jira.py"

PROJECT = os.environ.get("JIRA_OPS_TEST_PROJECT", "FASTACTR67")
ISSUE = os.environ.get("JIRA_OPS_TEST_ISSUE", "FASTACTR67-578")

LIVE = bool(os.environ.get("JIRA_OPS_LIVE"))
LIVE_WRITE = bool(os.environ.get("JIRA_OPS_LIVE_WRITE"))


class Result:
    """Outcome of one CLI invocation."""

    def __init__(self, code: int, data, stdout: str, stderr: str) -> None:
        self.code = code
        self.data = data
        self.stdout = stdout
        self.stderr = stderr

    @property
    def ok(self) -> bool:
        return isinstance(self.data, dict) and self.data.get("ok") is True

    def __repr__(self) -> str:  # helpful on assertion failure
        return f"Result(code={self.code}, data={self.data!r}, stderr={self.stderr!r})"


def run(*args: str, timeout: int = 60) -> Result:
    """Invoke `jira.py <args>` from the skill root and parse JSON stdout."""
    proc = subprocess.run(
        [sys.executable, str(JIRA_PY), *args],
        cwd=str(SKILL_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    data = None
    out = (proc.stdout or "").strip()
    if out:
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
    return Result(proc.returncode, data, proc.stdout, proc.stderr)


# --------------------------------------------------------------------------- #
# marker registration + env gating
# --------------------------------------------------------------------------- #
def pytest_configure(config: pytest.Config) -> None:
    for name, desc in (
        ("live", "hits the live Jira instance (needs JIRA_OPS_LIVE=1)"),
        ("dryrun", "side-effect-free write preview"),
        ("write", "performs a real write (needs JIRA_OPS_LIVE_WRITE=1)"),
        ("error", "negative / error-path case"),
    ):
        config.addinivalue_line("markers", f"{name}: {desc}")


def pytest_collection_modifyitems(config: pytest.Config, items) -> None:
    skip_live = pytest.mark.skip(reason="set JIRA_OPS_LIVE=1 to run live tests")
    skip_write = pytest.mark.skip(reason="set JIRA_OPS_LIVE_WRITE=1 to run real-write tests")
    for item in items:
        if not LIVE:
            item.add_marker(skip_live)
        elif "write" in item.keywords and not LIVE_WRITE:
            item.add_marker(skip_write)


@pytest.fixture(scope="session", autouse=True)
def _ready() -> None:
    """Skip the whole session cleanly if the live environment is not usable."""
    if not LIVE:
        return
    result = run("auth", "test-auth", "--json")
    if result.code != 0:
        pytest.skip(f"auth test-auth failed (exit {result.code}); live env not ready")


# --------------------------------------------------------------------------- #
# shared fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def jira():
    return run


@pytest.fixture(scope="session")
def project() -> str:
    return PROJECT


@pytest.fixture(scope="session")
def issue() -> str:
    return ISSUE


@pytest.fixture(scope="session")
def me() -> str:
    result = run("auth", "whoami", "--json")
    assert result.ok, result
    identity = result.data.get("identity") or {}
    return identity.get("name") or result.data.get("name")


@pytest.fixture(scope="session")
def issue_type() -> str:
    result = run("projects", "--key", PROJECT, "--createmeta", "--json")
    if not result.ok or not result.data.get("createMeta"):
        # /issue/createmeta is unavailable or returns 404 on some DC versions.
        pytest.skip(f"createmeta not available for {PROJECT} (exit {result.code})")
    return result.data["createMeta"][0]["issueType"]


@pytest.fixture(scope="session")
def link_type() -> str:
    result = run("link-types", "--json")
    if not result.ok or not result.data.get("linkTypes"):
        pytest.skip("no issue link types configured")
    names = [t["name"] for t in result.data["linkTypes"]]
    return "Relates" if "Relates" in names else names[0]


@pytest.fixture(scope="session")
def sprint_id():
    result = run("sprints", "--project", PROJECT, "--json")
    if not result.ok or not result.data.get("sprints"):
        pytest.skip(f"no sprints available for {PROJECT}")
    return result.data["sprints"][0]["id"]


@pytest.fixture(scope="session")
def original_578() -> dict:
    """Snapshot of the write-target issue, used to restore mutated fields."""
    result = run("view", ISSUE, "--json")
    assert result.ok, result
    return result.data["issue"]


@pytest.fixture
def tmp_attach(tmp_path: Path) -> Path:
    path = tmp_path / "lt-attach.txt"
    path.write_text("jira-ops live test attachment\n", encoding="utf-8")
    return path
