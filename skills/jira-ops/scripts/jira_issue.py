#!/usr/bin/env python3
"""Issue commands: search, mine, view, comment.

Invoked as:
  jira search  (--jql "..." | --preset NAME) [--limit N] [--json]
  jira mine    [--preset my-open|my-in-progress|my-stale|my-blocked|...] [--json]
  jira view    ISSUE-KEY [--json]
  jira comment ISSUE-KEY (--body "..." | --template NAME ...) [--dry-run] [--json]
  jira update  ISSUE-KEY [--summary ... --description ... --label ... --field k=v] [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cli import add_common_args, ensure_venv, load_profile, resolve_project, run  # noqa: E402
from jira_common import presets as presets_mod  # noqa: E402
from jira_common.client import JiraClient  # noqa: E402
from jira_common.errors import JiraOpsError  # noqa: E402
from jira_common.formatting import (  # noqa: E402
    emit,
    issue_detail,
    issue_summary_dict,
    issue_table,
)


def _search_and_emit(profile, jql: str, limit: int, as_json: bool, header: str) -> None:
    client = JiraClient(profile)
    issues = client.search(jql, max_results=limit)
    if as_json:
        emit(
            {"ok": True, "jql": jql, "count": len(issues),
             "issues": [issue_summary_dict(i, profile) for i in issues]},
            as_json=True,
        )
    else:
        text = f"{header} ({len(issues)})\n" + issue_table(issues, profile)
        emit(None, as_json=False, text=text)


def cmd_search(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira search")
    add_common_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--jql", help="Raw JQL query.")
    group.add_argument("--preset", help="Named preset (see references/examples.md).")
    parser.add_argument("--project", help="Convenience: open issues in a project.")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    if args.preset:
        try:
            jql = presets_mod.preset_jql(args.preset)
        except KeyError as exc:
            raise JiraOpsError("config", str(exc)) from exc
        header = f"Preset '{args.preset}'"
    elif args.jql:
        jql = args.jql
        header = "Results"
    else:
        project = resolve_project(args.project, profile)
        jql = presets_mod.project_open_jql(project)
        header = f"Open in {project}"
    _search_and_emit(profile, jql, args.limit, args.as_json, header)


def cmd_mine(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira mine")
    add_common_args(parser)
    parser.add_argument("--preset", default="my-open",
                        help="my-open | my-in-progress | my-stale | my-blocked | ...")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    try:
        jql = presets_mod.preset_jql(args.preset)
    except KeyError as exc:
        raise JiraOpsError("config", str(exc)) from exc
    _search_and_emit(profile, jql, args.limit, args.as_json, f"My work: {args.preset}")


def cmd_view(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira view")
    add_common_args(parser)
    parser.add_argument("issue_key")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    fields = "summary,status,assignee,reporter,priority,labels,updated,description"
    issue = client.get_json(f"issue/{args.issue_key}", {"fields": fields})
    if args.as_json:
        emit({"ok": True, "issue": issue_summary_dict(issue, profile)}, as_json=True)
    else:
        emit(None, as_json=False, text=issue_detail(issue, profile))


def _build_comment_body(args) -> str:
    if args.body:
        return args.body
    t = args.template
    changes = args.change or []
    tests = args.test or []
    risks = args.risk or []
    if t == "implementation-update":
        return presets_mod.implementation_update(
            summary=args.summary or "", changes=changes, tests=tests,
            results=args.result or "", risks=risks, next_step=args.next_step or "")
    if t == "test-result":
        return presets_mod.test_result_update(
            summary=args.summary or "", tests=tests, results=args.result or "",
            next_step=args.next_step or "")
    if t == "blocked":
        return presets_mod.blocked_update(
            reason=args.summary or args.result or "", needed_from=args.needed_from or "",
            next_step=args.next_step or "")
    if t == "handoff":
        return presets_mod.handoff_update(
            summary=args.summary or "", done=changes, remaining=risks,
            notes=args.result or "")
    raise JiraOpsError("config", f"Unknown template: {t}")


def cmd_comment(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira comment")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--body", help="Literal comment body (wiki markup).")
    parser.add_argument("--template",
                        choices=["implementation-update", "test-result", "blocked", "handoff"])
    parser.add_argument("--summary")
    parser.add_argument("--change", action="append")
    parser.add_argument("--test", action="append")
    parser.add_argument("--result")
    parser.add_argument("--risk", action="append")
    parser.add_argument("--needed-from")
    parser.add_argument("--next-step")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.body and not args.template:
        raise JiraOpsError("config", "Provide --body or --template for the comment.")

    profile = load_profile(args.profile)
    body = _build_comment_body(args)

    # Fetch current state first (safety rule).
    client = JiraClient(profile)
    client.guard_no_secret_leak(body)
    issue = client.get_json(f"issue/{args.issue_key}", {"fields": "summary,status"})

    request_payload = {"body": body}
    if args.dry_run:
        emit(
            {"ok": True, "action": "comment", "dryRun": True, "issue": args.issue_key,
             "request": request_payload},
            as_json=args.as_json,
            text=(f"[dry-run] Would comment on {args.issue_key} "
                  f"({issue.get('fields', {}).get('status', {}).get('name', '?')}):\n\n{body}"),
        )
        return

    created = client.post_json(f"issue/{args.issue_key}/comment", request_payload)
    emit(
        {"ok": True, "action": "comment", "issue": args.issue_key,
         "commentId": created.get("id"), "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"Comment added to {args.issue_key} (id {created.get('id')}).",
    )


def _parse_field_pairs(pairs: list | None) -> dict:
    """Parse repeated --field key=value flags into a fields dict."""
    out: dict = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise JiraOpsError("config", f"Invalid --field '{pair}'. Use key=value.")
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            raise JiraOpsError("config", f"Invalid --field '{pair}'. Missing field name.")
        out[key] = value
    return out


def cmd_update(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira update")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--summary", help="Set the issue summary (title).")
    parser.add_argument("--description", help="Set the description (wiki markup / plain text).")
    parser.add_argument("--priority", help="Set the priority by name (e.g. High).")
    parser.add_argument("--assignee", help="Set the assignee by username (Data Center).")
    parser.add_argument("--label", action="append", dest="labels",
                        help="Add a label; prefix with '-' to remove (repeatable).")
    parser.add_argument("--due", dest="duedate", help="Set the due date (ISO, e.g. 2026-08-01).")
    parser.add_argument("--field", action="append", dest="fields_kv",
                        help="Generic set: key=value (repeatable), e.g. customfield_10021=Team A.")
    parser.add_argument("--field-json", dest="field_json",
                        help="Raw JSON object merged into the fields payload.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    fields: dict = {}
    update_ops: dict = {}

    if args.summary is not None:
        fields["summary"] = args.summary
    if args.description is not None:
        fields["description"] = args.description
    if args.priority is not None:
        fields["priority"] = {"name": args.priority}
    if args.assignee is not None:
        fields["assignee"] = {"name": args.assignee}
    if args.duedate is not None:
        fields["duedate"] = args.duedate

    for key, value in _parse_field_pairs(args.fields_kv).items():
        fields[key] = value

    if args.field_json:
        try:
            extra = json.loads(args.field_json)
        except json.JSONDecodeError as exc:
            raise JiraOpsError("config", f"Invalid --field-json: {exc}") from exc
        if not isinstance(extra, dict):
            raise JiraOpsError("config", "--field-json must be a JSON object.")
        fields.update(extra)

    if args.labels:
        ops = []
        for raw in args.labels:
            label = raw.strip()
            if not label or label == "-":
                raise JiraOpsError("config", "Empty --label value.")
            if label.startswith("-"):
                ops.append({"remove": label[1:]})
            else:
                ops.append({"add": label})
        update_ops["labels"] = ops

    if not fields and not update_ops:
        raise JiraOpsError(
            "config",
            "No fields to update. Pass --summary/--description/--priority/--assignee/"
            "--label/--due, or --field key=value / --field-json.",
        )

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    # Refuse to leak the PAT into any string value that would be written.
    for value in fields.values():
        if isinstance(value, str):
            client.guard_no_secret_leak(value)

    # Fetch current state first (safety rule).
    issue = client.get_json(f"issue/{args.issue_key}", {"fields": "summary,status"})
    status = (issue.get("fields", {}).get("status") or {}).get("name", "?")

    changed = sorted(set(fields) | set(update_ops))
    request_body: dict = {}
    if fields:
        request_body["fields"] = fields
    if update_ops:
        request_body["update"] = update_ops

    if args.dry_run:
        emit(
            {"ok": True, "action": "update", "dryRun": True, "issue": args.issue_key,
             "fields": changed, "request": request_body},
            as_json=args.as_json,
            text=(f"[dry-run] Would update {args.issue_key} ({status}): "
                  f"{', '.join(changed)}\n\n" + json.dumps(request_body, indent=2)),
        )
        return

    client.update_issue(args.issue_key, fields=fields or None, update=update_ops or None)
    emit(
        {"ok": True, "action": "update", "issue": args.issue_key,
         "fields": changed, "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"Updated {args.issue_key}: {', '.join(changed)}.",
    )


def main() -> None:
    ensure_venv()
    if len(sys.argv) < 2:
        raise JiraOpsError("config", "Missing command.")
    command, rest = sys.argv[1], sys.argv[2:]
    dispatch = {
        "search": cmd_search,
        "mine": cmd_mine,
        "view": cmd_view,
        "comment": cmd_comment,
        "update": cmd_update,
    }
    handler = dispatch.get(command)
    if not handler:
        raise JiraOpsError("config", f"Unknown command: {command}")
    handler(rest)


if __name__ == "__main__":
    run(main)
