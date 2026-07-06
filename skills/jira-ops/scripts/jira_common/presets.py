"""JQL presets and comment/status-update templates.

Presets are editable data, not hard-coded into SKILL.md. Field and status names
vary per instance; ``references/examples.md`` documents how to adjust them.
"""

from __future__ import annotations

from typing import Dict

# JQL presets. {version} placeholder is not used; keep them instance-agnostic.
JQL_PRESETS: Dict[str, str] = {
    "my-open": (
        "assignee = currentUser() AND resolution = Unresolved "
        "ORDER BY priority DESC, updated DESC"
    ),
    "my-in-progress": (
        'assignee = currentUser() AND status = "In Progress" ORDER BY updated DESC'
    ),
    "my-stale": (
        "assignee = currentUser() AND resolution = Unresolved AND updated < -5d "
        "ORDER BY updated ASC"
    ),
    "my-blocked": (
        "assignee = currentUser() AND resolution = Unresolved "
        "AND (labels = blocked OR status = Blocked) ORDER BY updated DESC"
    ),
    "recently-updated-by-me": (
        "assignee = currentUser() AND updated >= -7d ORDER BY updated DESC"
    ),
    "reported-by-me-open": (
        "reporter = currentUser() AND resolution = Unresolved ORDER BY created DESC"
    ),
}


def preset_jql(name: str) -> str:
    try:
        return JQL_PRESETS[name]
    except KeyError as exc:
        available = ", ".join(sorted(JQL_PRESETS))
        raise KeyError(f"Unknown preset '{name}'. Available: {available}") from exc


def project_open_jql(project_key: str) -> str:
    return (
        f"project = {project_key} AND resolution = Unresolved "
        "ORDER BY priority DESC, updated DESC"
    )


def release_scope_jql(fix_version: str) -> str:
    return (
        f'fixVersion = "{fix_version}" AND resolution = Unresolved '
        "ORDER BY priority DESC"
    )


# --------------------------------------------------------------------------- #
# Comment templates (Jira DC v2 wiki markup)
# --------------------------------------------------------------------------- #
def _bullets(items) -> str:
    return "\n".join(f"* {i}" for i in items if str(i).strip())


def implementation_update(
    *,
    summary: str,
    changes=None,
    tests=None,
    results: str = "",
    risks=None,
    next_step: str = "",
) -> str:
    parts = ["h3. Implementation update", "", summary.strip(), ""]
    if changes:
        parts += ["*Changes*", _bullets(changes), ""]
    if tests:
        parts += ["*Tests run*", _bullets(tests), ""]
    if results:
        parts += ["*Result*", results.strip(), ""]
    if risks:
        parts += ["*Risks / open items*", _bullets(risks), ""]
    if next_step:
        parts += ["*Next step*", next_step.strip(), ""]
    return "\n".join(parts).rstrip() + "\n"


def test_result_update(*, summary: str, tests=None, results: str = "", next_step: str = "") -> str:
    parts = ["h3. Test result", "", summary.strip(), ""]
    if tests:
        parts += ["*Tests*", _bullets(tests), ""]
    if results:
        parts += ["*Outcome*", results.strip(), ""]
    if next_step:
        parts += ["*Next step*", next_step.strip(), ""]
    return "\n".join(parts).rstrip() + "\n"


def blocked_update(*, reason: str, needed_from: str = "", next_step: str = "") -> str:
    parts = ["h3. Blocked", "", reason.strip(), ""]
    if needed_from:
        parts += ["*Needed from*", needed_from.strip(), ""]
    if next_step:
        parts += ["*Proposed next step*", next_step.strip(), ""]
    return "\n".join(parts).rstrip() + "\n"


def handoff_update(*, summary: str, done=None, remaining=None, notes: str = "") -> str:
    parts = ["h3. Handoff", "", summary.strip(), ""]
    if done:
        parts += ["*Completed*", _bullets(done), ""]
    if remaining:
        parts += ["*Remaining*", _bullets(remaining), ""]
    if notes:
        parts += ["*Notes*", notes.strip(), ""]
    return "\n".join(parts).rstrip() + "\n"
