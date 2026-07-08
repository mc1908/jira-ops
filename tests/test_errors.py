"""LT-40..46: error-path (negative) cases. See tests/live-test-plan.md §6."""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.live, pytest.mark.error]


def test_lt40_invalid_jql(jira, project):
    r = jira("search", "--jql", f"project = {project} AND bogusfield = x", "--json")
    assert r.code == 16, r
    assert r.data and r.data.get("category") == "invalid_jql"


def test_lt41_unknown_issue(jira, project):
    r = jira("view", f"{project}-99999999", "--json")
    assert r.code == 15, r


def test_lt42_create_missing_type(jira, project):
    r = jira("create", "--project", project, "--summary", "no type", "--json")
    assert r.code == 10, r
    assert r.data and r.data.get("category") == "config"


def test_lt43_bad_transition(jira, issue):
    r = jira("transition", issue, "--to", "NoSuchStatus", "--json")
    assert r.code == 17, r


def test_lt44_missing_attachment_file(jira, issue):
    r = jira("attach", issue, "--file", "./does-not-exist.bin", "--json")
    assert r.code == 10, r
    assert r.data and r.data.get("category") == "config"


def test_lt45_unknown_filter(jira):
    r = jira("filter", "99999999", "--json")
    # A missing/invisible filter maps to not_found (404); tolerate related 4xx.
    assert r.code in (15, 12, 18), r


def test_lt46_secret_leak_guard(jira, issue):
    token = os.environ.get("JIRA_OPS_TOKEN")
    if not (token and os.environ.get("JIRA_OPS_TEST_SECRET_GUARD")):
        pytest.skip("set JIRA_OPS_TOKEN and JIRA_OPS_TEST_SECRET_GUARD=1 to test the guard")
    # --dry-run so nothing is sent; the guard must fire before any request.
    r = jira("comment", issue, "--body", token, "--dry-run", "--json")
    assert r.code == 18, r
    assert r.data and r.data.get("category") == "validation"
