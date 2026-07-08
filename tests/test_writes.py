"""LT-30..38: real writes against the safe targets, with revert where possible.

Gated by `write` marker → only runs with JIRA_OPS_LIVE_WRITE=1. Some Jira
artifacts (comments, worklogs, attachments, links) cannot be removed via the CLI
by design; those tests create durable artifacts flagged as test data. Field-level
changes on the write-target issue are reverted in `finally` blocks.

See tests/live-test-plan.md §5 and §8.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.write]


@pytest.fixture(scope="module")
def throwaway(jira, project, issue_type):
    """Create a disposable issue; best-effort close + label on teardown."""
    created = jira("create", "--project", project, "--type", issue_type,
                   "--summary", "LT-36 throwaway (safe to close)", "--json")
    assert created.ok, created
    key = created.data["issue"]
    yield key
    # Cannot delete via the skill; mark it and try to move it to a done state.
    jira("update", key, "--label", "lt-artifact", "--json")
    transitions = jira("transitions", key, "--json")
    if transitions.ok:
        for t in transitions.data.get("transitions", []):
            if (t.get("to") or "").lower() in ("done", "closed", "resolved"):
                jira("transition", key, "--id", str(t["id"]), "--json")
                break


def test_lt30_comment(jira, issue):
    r = jira("comment", issue, "--body", "live-test LT-30 (safe to ignore)", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("commentId")


def test_lt31_update_summary_revert(jira, issue, original_578):
    original = original_578["summary"]
    try:
        r = jira("update", issue, "--summary", "LT-31 temp summary", "--json")
        assert r.code == 0 and r.ok, r
        assert "summary" in r.data.get("fields", [])
    finally:
        jira("update", issue, "--summary", original, "--json")


def test_lt32_assign_and_revert(jira, issue, me, original_578):
    original = original_578.get("assignee")  # displayName or "-"
    try:
        r = jira("assign", issue, "--to", me, "--json")
        assert r.code == 0 and r.ok, r
        assert r.data.get("to") == me
    finally:
        if not original or original == "-":
            jira("assign", issue, "--to", "-", "--json")
        else:
            lookup = jira("users", "--query", original, "--json")
            name = None
            if lookup.ok and lookup.data.get("users"):
                name = lookup.data["users"][0]["name"]
            jira("assign", issue, "--to", name or "-", "--json")


def test_lt33_label_add_remove(jira, issue):
    try:
        r = jira("update", issue, "--label", "lt-marker", "--json")
        assert r.code == 0 and r.ok, r
    finally:
        jira("update", issue, "--label", "-lt-marker", "--json")


def test_lt34_worklog_add(jira, issue):
    r = jira("worklog", issue, "--time", "5m", "--comment", "LT-34", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("worklogId")


def test_lt35_attach(jira, issue, tmp_attach):
    r = jira("attach", issue, "--file", str(tmp_attach), "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("attached")
    assert r.data["attached"][0]["filename"] == tmp_attach.name


def test_lt36_create_throwaway(throwaway, project):
    assert throwaway.startswith(project + "-")


def test_lt37_link_issues(jira, issue, throwaway, link_type):
    r = jira("link", issue, "--to", throwaway, "--type", link_type, "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "link"
