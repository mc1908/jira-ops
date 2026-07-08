"""LT-20..27: dry-run write previews. Hit the instance (reads) but change nothing.

See tests/live-test-plan.md. Marked `live` (network) but never `write`.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live, pytest.mark.dryrun]


def test_lt20_comment_dryrun(jira, issue):
    r = jira("comment", issue, "--body", "live-test dry-run", "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("dryRun") is True
    assert r.data.get("action") == "comment"
    assert r.data["request"]["body"] == "live-test dry-run"


def test_lt21_update_dryrun(jira, issue):
    r = jira("update", issue, "--summary", "LT temp", "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("dryRun") is True
    assert "summary" in r.data.get("fields", [])


def test_lt22_create_dryrun(jira, project, issue_type):
    r = jira("create", "--project", project, "--type", issue_type,
             "--summary", "LT create", "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "create"
    assert r.data["request"]["fields"]["project"]["key"] == project


def test_lt23_assign_dryrun(jira, issue, me):
    r = jira("assign", issue, "--to", me, "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "assign"
    assert r.data.get("to") == me


def test_lt24_link_dryrun(jira, issue, link_type):
    # Self-link is only ever previewed here; never sent.
    r = jira("link", issue, "--to", issue, "--type", link_type, "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "link"


def test_lt25_attach_dryrun(jira, issue, tmp_attach):
    r = jira("attach", issue, "--file", str(tmp_attach), "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "attach"
    assert r.data["files"][0]["name"] == tmp_attach.name


def test_lt26_worklog_dryrun(jira, issue):
    r = jira("worklog", issue, "--time", "5m", "--comment", "LT", "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "worklog"
    assert r.data["request"]["timeSpent"] == "5m"


def test_lt27_sprint_add_dryrun(jira, issue, sprint_id):
    r = jira("sprint-add", "--id", str(sprint_id), "--issue", issue, "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "sprint-add"
    assert issue in r.data.get("issues", [])


def test_lt28_update_description_file(jira, issue, tmp_path):
    """--description-file round-trips multiline content without shell quoting."""
    desc_file = tmp_path / "desc.txt"
    desc_file.write_text("h2. Goal\nLine 1\nLine 2\n\nLine 3", encoding="utf-8")
    r = jira("update", issue, "--description-file", str(desc_file), "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("dryRun") is True
    assert "description" in r.data.get("fields", [])
    assert r.data["request"]["fields"]["description"] == "h2. Goal\nLine 1\nLine 2\n\nLine 3"


def test_lt29_create_description_file(jira, project, tmp_path):
    """create --description-file works in dry-run without shell quoting (type hardcoded)."""
    desc_file = tmp_path / "desc.txt"
    desc_file.write_text("h2. Acceptance Criteria\n* Criterion 1\n* Criterion 2", encoding="utf-8")
    r = jira("create", "--project", project, "--type", "Story",
             "--summary", "LT desc-file test",
             "--description-file", str(desc_file), "--dry-run", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("action") == "create"
    assert r.data["request"]["fields"]["description"] == \
        "h2. Acceptance Criteria\n* Criterion 1\n* Criterion 2"
