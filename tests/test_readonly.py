"""LT-01..19: read-only suite. Safe, no cleanup. See tests/live-test-plan.md."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


def test_lt01_whoami(jira):
    r = jira("auth", "whoami", "--json")
    assert r.code == 0 and r.ok, r
    # name is nested under identity on this DC instance.
    identity = r.data.get("identity") or {}
    assert identity.get("name") or r.data.get("name")


def test_lt02_projects(jira):
    r = jira("projects", "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("count", 0) >= 1


def test_lt03_project_metadata(jira, project):
    r = jira("projects", "--key", project, "--json")
    assert r.code == 0 and r.ok, r
    assert r.data["project"]["key"] == project


def test_lt04_createmeta(jira, project):
    r = jira("projects", "--key", project, "--createmeta", "--json")
    # /issue/createmeta returns 404 on some DC configurations; accept that.
    if r.code == 15:
        pytest.skip(f"createmeta not available for {project} on this instance")
    assert r.code == 0 and r.ok, r
    assert r.data.get("createMeta") is not None


def test_lt05_user_lookup(jira, me):
    r = jira("users", "--query", me, "--json")
    assert r.code == 0 and r.ok, r
    assert r.data.get("count", 0) >= 1


def test_lt06_search_jql(jira, project):
    r = jira("search", "--jql", f"project = {project} ORDER BY created DESC", "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("issues"), list)


def test_lt07_search_project_shortcut(jira, project):
    r = jira("search", "--project", project, "--json")
    assert r.code == 0 and r.ok, r


def test_lt08_mine_open(jira):
    r = jira("mine", "--preset", "my-open", "--json")
    assert r.code == 0 and r.ok, r


def test_lt09_view(jira, issue):
    r = jira("view", issue, "--json")
    assert r.code == 0 and r.ok, r
    assert r.data["issue"]["key"] == issue


def test_lt10_comments(jira, issue):
    r = jira("comments", issue, "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("comments"), list)


def test_lt11_history(jira, issue):
    r = jira("history", issue, "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("history"), list)


def test_lt12_worklog_list(jira, issue):
    r = jira("worklog", issue, "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("worklogs"), list)


def test_lt13_transitions(jira, issue):
    r = jira("transitions", issue, "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("transitions"), list)


def test_lt14_link_types(jira):
    r = jira("link-types", "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("linkTypes"), list)


def test_lt15_filters(jira):
    r = jira("filters", "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("filters"), list)


def test_lt16_boards(jira, project):
    r = jira("boards", "--project", project, "--json")
    assert r.code == 0 and r.ok, r
    assert isinstance(r.data.get("boards"), list)


def test_lt17_sprints(jira, project):
    r = jira("sprints", "--project", project, "--json")
    # exit 0 with a (possibly empty) list, or not_found if no scrum board.
    assert r.code in (0, 15), r


def test_lt18_active_sprint(jira, project):
    r = jira("sprint", "--project", project, "--json")
    assert r.code in (0, 15), r


def test_lt19_backlog(jira, project):
    r = jira("backlog", "--project", project, "--json")
    assert r.code in (0, 15), r
