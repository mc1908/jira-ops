#!/usr/bin/env python3
"""Issue commands: search, mine, view, comment.

Invoked as:
  jira search  (--jql "..." | --preset NAME) [--limit N] [--json]
  jira mine    [--preset my-open|my-in-progress|my-stale|my-blocked|...] [--json]
  jira view    ISSUE-KEY [--json]
  jira comment ISSUE-KEY (--body "..." | --template NAME ...) [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
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
    }
    handler = dispatch.get(command)
    if not handler:
        raise JiraOpsError("config", f"Unknown command: {command}")
    handler(rest)


if __name__ == "__main__":
    run(main)
