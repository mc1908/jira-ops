#!/usr/bin/env python3
"""Issue commands: search, mine, view, comment.

Invoked as:
  jira search  (--jql "..." | --preset NAME) [--limit N] [--json]
  jira mine    [--preset my-open|my-in-progress|my-stale|my-blocked|...] [--json]
  jira view    ISSUE-KEY [--json]
  jira comment ISSUE-KEY (--body "..." | --template NAME ...) [--dry-run] [--json]
  jira comments ISSUE-KEY [--limit N] [--json]
  jira update  ISSUE-KEY [--summary ... --description ... --description-file PATH --label ... --field k=v] [--dry-run] [--json]
  jira create  --project ABC --type Task --summary "..." [--description ... --description-file PATH --label ...] [--dry-run] [--json]
  jira assign  ISSUE-KEY --to username | --to -            [--dry-run] [--json]
  jira link    ISSUE-KEY --to OTHER --type "Blocks"        [--comment ...] [--dry-run] [--json]
  jira link-types                                          [--json]
  jira attach  ISSUE-KEY --file PATH [--file PATH ...]     [--dry-run] [--json]
  jira worklog ISSUE-KEY [--time "1h 30m" --comment ...]   [--dry-run] [--json]
  jira history ISSUE-KEY [--limit N]                       [--json]
  jira filters                                             [--json]
  jira filter  FILTER-ID [--limit N]                       [--json]
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


def _resolve_description(args) -> str | None:
    """Resolve --description / --description-file (including '-' for stdin) to a string.

    Mutual exclusion: both flags set simultaneously → JiraOpsError.
    """
    desc_file = getattr(args, "description_file", None)
    desc = getattr(args, "description", None)

    if desc_file is not None and desc is not None:
        raise JiraOpsError("config", "Use --description or --description-file, not both.")

    if desc_file is not None:
        if desc_file == "-":
            return sys.stdin.read()
        path = Path(desc_file)
        if not path.exists():
            raise JiraOpsError("config", f"--description-file not found: {path}")
        return path.read_text(encoding="utf-8")

    if desc is None:
        return None
    if desc == "-":
        return sys.stdin.read()
    return desc


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
    parser.add_argument("--description", help="Set the description (wiki markup / plain text). Use '-' to read from stdin.")
    parser.add_argument("--description-file", dest="description_file", metavar="PATH",
                        help="Read description from a file instead of --description (avoids shell quoting for multiline content). Use '-' for stdin.")
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
    desc = _resolve_description(args)
    if desc is not None:
        fields["description"] = desc
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


def cmd_create(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira create")
    add_common_args(parser)
    parser.add_argument("--project", help="Project key (default: configured default project).")
    parser.add_argument("--type", dest="issuetype",
                        help="Issue type name, e.g. Story, Bug, Task, Test, Sub-task "
                             "(required; infer from context or ask the user).")
    parser.add_argument("--summary", required=True, help="Issue summary (title).")
    parser.add_argument("--description", help="Description (wiki markup / plain text). Use '-' to read from stdin.")
    parser.add_argument("--description-file", dest="description_file", metavar="PATH",
                        help="Read description from a file instead of --description (avoids shell quoting for multiline content). Use '-' for stdin.")
    parser.add_argument("--priority", help="Priority by name (e.g. High).")
    parser.add_argument("--assignee", help="Assignee username (Data Center).")
    parser.add_argument("--label", action="append", dest="labels",
                        help="Add a label (repeatable).")
    parser.add_argument("--due", dest="duedate", help="Due date (ISO, e.g. 2026-08-01).")
    parser.add_argument("--field", action="append", dest="fields_kv",
                        help="Generic set: key=value (repeatable).")
    parser.add_argument("--field-json", dest="field_json",
                        help="Raw JSON object merged into the fields payload.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.issuetype:
        raise JiraOpsError(
            "config",
            "Specify --type (e.g. Story, Bug, Task, Test). Determine it from the "
            "request context; if it is unclear, ask the user instead of guessing. "
            "Run 'projects --key KEY --createmeta' to list valid issue types.",
        )

    profile = load_profile(args.profile)
    project = resolve_project(args.project, profile)

    fields: dict = {
        "project": {"key": project},
        "issuetype": {"name": args.issuetype},
        "summary": args.summary,
    }
    desc = _resolve_description(args)
    if desc is not None:
        fields["description"] = desc
    if args.priority is not None:
        fields["priority"] = {"name": args.priority}
    if args.assignee is not None:
        fields["assignee"] = {"name": args.assignee}
    if args.duedate is not None:
        fields["duedate"] = args.duedate
    if args.labels:
        fields["labels"] = [label.strip() for label in args.labels]

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

    client = JiraClient(profile)

    # Refuse to leak the PAT into any string value that would be written.
    for value in fields.values():
        if isinstance(value, str):
            client.guard_no_secret_leak(value)

    request_body = {"fields": fields}
    if args.dry_run:
        emit(
            {"ok": True, "action": "create", "dryRun": True, "project": project,
             "issueType": args.issuetype, "request": request_body},
            as_json=args.as_json,
            text=(f"[dry-run] Would create a {args.issuetype} in {project}:\n\n"
                  + json.dumps(request_body, indent=2)
                  + "\n\nTip: 'projects --key " + project
                  + " --createmeta' lists required fields for each issue type."),
        )
        return

    created = client.create_issue(fields)
    key = created.get("key")
    emit(
        {"ok": True, "action": "create", "issue": key,
         "url": profile.browse_url(key) if key else None},
        as_json=args.as_json,
        text=(f"Created {key} in {project}: {args.summary}" if key else "Created issue."),
    )


def cmd_comments(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira comments")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    comments = client.paginate(
        f"issue/{args.issue_key}/comment", key="comments", max_results=args.limit)
    rows = [
        {"id": c.get("id"),
         "author": (c.get("author") or {}).get("displayName")
                   or (c.get("author") or {}).get("name") or "-",
         "created": c.get("created"),
         "updated": c.get("updated"),
         "body": c.get("body") or ""}
        for c in comments
    ]
    if args.as_json:
        emit({"ok": True, "issue": args.issue_key, "count": len(rows),
              "comments": rows}, as_json=True)
        return
    if not rows:
        emit(None, as_json=False, text=f"{args.issue_key}: no comments.")
        return
    blocks = []
    for r in rows:
        body = str(r["body"]).strip()
        blocks.append(f"[{r['id']}] {r['author']}  {str(r['created'])[:16]}\n  "
                      + body.replace("\n", "\n  "))
    emit(None, as_json=False,
         text=f"{args.issue_key} comments ({len(rows)}):\n\n" + "\n\n".join(blocks))


def cmd_assign(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira assign")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--to", required=True,
                        help="Assignee username, or '-' to unassign.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    unassign = args.to.strip() == "-"
    username = None if unassign else args.to.strip()
    target_label = "(unassigned)" if unassign else username

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    # Fetch current state first (safety rule).
    issue = client.get_json(f"issue/{args.issue_key}", {"fields": "assignee,summary"})
    current = ((issue.get("fields") or {}).get("assignee") or {}).get("name") or "(unassigned)"

    if args.dry_run:
        emit(
            {"ok": True, "action": "assign", "dryRun": True, "issue": args.issue_key,
             "from": current, "to": target_label, "request": {"name": username}},
            as_json=args.as_json,
            text=f"[dry-run] Would reassign {args.issue_key}: {current} -> {target_label}.",
        )
        return

    client.assign_issue(args.issue_key, username)
    emit(
        {"ok": True, "action": "assign", "issue": args.issue_key,
         "from": current, "to": target_label, "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"{args.issue_key} reassigned: {current} -> {target_label}.",
    )


def cmd_link_types(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira link-types")
    add_common_args(parser)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    types = client.link_types()
    rows = [{"name": t.get("name"), "inward": t.get("inward"),
             "outward": t.get("outward")} for t in types]
    emit(
        {"ok": True, "count": len(rows), "linkTypes": rows},
        as_json=args.as_json,
        text=("Link types (use --type NAME with 'link'):\n" +
              "\n".join(f"  {r['name']:<16} outward: {r['outward']:<20} inward: {r['inward']}"
                        for r in rows)) if rows else "No link types configured.",
    )


def cmd_link(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira link")
    add_common_args(parser)
    parser.add_argument("issue_key", help="Subject issue (the outward side, e.g. the blocker).")
    parser.add_argument("--to", required=True, dest="other",
                        help="Object issue key (the inward side).")
    parser.add_argument("--type", required=True, dest="link_type",
                        help="Link type name, e.g. Blocks, Relates, Duplicate. See 'link-types'.")
    parser.add_argument("--comment", help="Optional comment added with the link.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    if args.comment:
        client.guard_no_secret_leak(args.comment)

    # Fetch both issues first (safety rule; also validates the keys exist).
    client.get_json(f"issue/{args.issue_key}", {"fields": "summary"})
    client.get_json(f"issue/{args.other}", {"fields": "summary"})

    request_body = {
        "type": {"name": args.link_type},
        "outwardIssue": {"key": args.issue_key},
        "inwardIssue": {"key": args.other},
    }
    if args.comment:
        request_body["comment"] = {"body": args.comment}

    if args.dry_run:
        emit(
            {"ok": True, "action": "link", "dryRun": True, "outward": args.issue_key,
             "inward": args.other, "type": args.link_type, "request": request_body},
            as_json=args.as_json,
            text=f"[dry-run] Would link {args.issue_key} --[{args.link_type}]--> {args.other}.",
        )
        return

    client.link_issues(outward_key=args.issue_key, inward_key=args.other,
                       link_type=args.link_type, comment=args.comment)
    emit(
        {"ok": True, "action": "link", "outward": args.issue_key, "inward": args.other,
         "type": args.link_type, "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"Linked {args.issue_key} --[{args.link_type}]--> {args.other}.",
    )


def cmd_attach(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira attach")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--file", action="append", dest="files", required=True,
                        help="Path to a file to attach (repeatable).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    paths = []
    for raw in args.files:
        path = Path(raw).expanduser()
        if not path.is_file():
            raise JiraOpsError("config", f"Attachment file not found: {path}")
        paths.append(path)

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    # Fetch current state first (safety rule; validates the key is visible).
    client.get_json(f"issue/{args.issue_key}", {"fields": "summary"})

    if args.dry_run:
        emit(
            {"ok": True, "action": "attach", "dryRun": True, "issue": args.issue_key,
             "files": [{"name": p.name, "bytes": p.stat().st_size} for p in paths]},
            as_json=args.as_json,
            text=(f"[dry-run] Would attach to {args.issue_key}:\n" +
                  "\n".join(f"  {p.name} ({p.stat().st_size} bytes)" for p in paths)),
        )
        return

    attached = []
    for path in paths:
        result = client.add_attachment(args.issue_key, path)
        for meta in (result if isinstance(result, list) else []):
            attached.append({"id": meta.get("id"), "filename": meta.get("filename"),
                             "size": meta.get("size")})
    emit(
        {"ok": True, "action": "attach", "issue": args.issue_key,
         "attached": attached, "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=(f"Attached {len(attached)} file(s) to {args.issue_key}: " +
              ", ".join(a["filename"] for a in attached)) if attached
             else f"Attached to {args.issue_key}.",
    )


def cmd_worklog(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira worklog")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--time", dest="time_spent",
                        help="Time to log, e.g. '1h 30m'. Omit to list existing worklogs.")
    parser.add_argument("--comment", help="Optional worklog comment.")
    parser.add_argument("--started",
                        help="ISO start time, e.g. 2026-07-08T10:00:00.000+0000 (default: now).")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    # No --time: list existing worklogs (read).
    if not args.time_spent:
        logs = client.get_worklogs(args.issue_key, max_results=args.limit)
        rows = [
            {"id": w.get("id"),
             "author": (w.get("author") or {}).get("displayName")
                       or (w.get("author") or {}).get("name") or "-",
             "timeSpent": w.get("timeSpent"),
             "started": w.get("started"),
             "comment": w.get("comment") or ""}
            for w in logs
        ]
        if args.as_json:
            emit({"ok": True, "issue": args.issue_key, "count": len(rows),
                  "totalSeconds": sum(w.get("timeSpentSeconds", 0) for w in logs),
                  "worklogs": rows}, as_json=True)
            return
        if not rows:
            emit(None, as_json=False, text=f"{args.issue_key}: no worklogs.")
            return
        lines = [f"[{r['id']}] {r['author']}  {str(r['started'])[:16]}  {r['timeSpent']}"
                 + (f"  - {str(r['comment']).strip()}" if r["comment"] else "") for r in rows]
        emit(None, as_json=False,
             text=f"{args.issue_key} worklogs ({len(rows)}):\n" + "\n".join(lines))
        return

    # --time provided: add a worklog (write).
    if args.comment:
        client.guard_no_secret_leak(args.comment)
    # Fetch current state first (safety rule).
    client.get_json(f"issue/{args.issue_key}", {"fields": "summary"})

    request_body = {"timeSpent": args.time_spent}
    if args.comment:
        request_body["comment"] = args.comment
    if args.started:
        request_body["started"] = args.started

    if args.dry_run:
        emit(
            {"ok": True, "action": "worklog", "dryRun": True, "issue": args.issue_key,
             "request": request_body},
            as_json=args.as_json,
            text=(f"[dry-run] Would log {args.time_spent} on {args.issue_key}"
                  + (f" - {args.comment}" if args.comment else "") + "."),
        )
        return

    created = client.add_worklog(args.issue_key, time_spent=args.time_spent,
                                 comment=args.comment, started=args.started)
    emit(
        {"ok": True, "action": "worklog", "issue": args.issue_key,
         "worklogId": created.get("id"), "timeSpent": created.get("timeSpent"),
         "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"Logged {created.get('timeSpent') or args.time_spent} on "
             f"{args.issue_key} (id {created.get('id')}).",
    )


def cmd_history(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira history")
    add_common_args(parser)
    parser.add_argument("issue_key")
    parser.add_argument("--limit", type=int, default=50,
                        help="Show at most N most-recent change events.")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    summary, histories = client.get_changelog(args.issue_key)
    if args.limit:
        histories = histories[-args.limit:]

    events = []
    for h in histories:
        changes = [{"field": it.get("field"), "from": it.get("fromString"),
                    "to": it.get("toString")} for it in (h.get("items") or [])]
        events.append({
            "created": h.get("created"),
            "author": (h.get("author") or {}).get("displayName")
                      or (h.get("author") or {}).get("name") or "-",
            "changes": changes,
        })

    if args.as_json:
        emit({"ok": True, "issue": args.issue_key, "summary": summary,
              "count": len(events), "history": events}, as_json=True)
        return
    if not events:
        emit(None, as_json=False, text=f"{args.issue_key}: no change history.")
        return
    blocks = []
    for e in events:
        head = f"{str(e['created'])[:16]}  {e['author']}"
        rows = [f"  {c['field']}: {c['from'] or '-'} -> {c['to'] or '-'}"
                for c in e["changes"]]
        blocks.append(head + "\n" + "\n".join(rows))
    emit(None, as_json=False,
         text=f"{args.issue_key} history ({len(events)}):\n\n" + "\n\n".join(blocks))


def cmd_filters(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira filters")
    add_common_args(parser)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    filters = client.favourite_filters()
    rows = [{"id": f.get("id"), "name": f.get("name"),
             "owner": (f.get("owner") or {}).get("displayName"),
             "jql": f.get("jql")} for f in filters]
    emit(
        {"ok": True, "count": len(rows), "filters": rows},
        as_json=args.as_json,
        text=(f"Favourite filters ({len(rows)}):\n" +
              "\n".join(f"  [{r['id']}] {r['name']}  - {r['jql']}" for r in rows))
             if rows else "No favourite filters.",
    )


def cmd_filter(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira filter")
    add_common_args(parser)
    parser.add_argument("filter_id")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    flt = client.get_filter(args.filter_id)
    jql = flt.get("jql") or ""
    if not jql:
        raise JiraOpsError("not_found", f"Filter {args.filter_id} has no JQL or is not visible.")
    name = flt.get("name") or args.filter_id
    _search_and_emit(profile, jql, args.limit, args.as_json,
                     f"Filter '{name}' [{args.filter_id}]")


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
        "comments": cmd_comments,
        "update": cmd_update,
        "create": cmd_create,
        "assign": cmd_assign,
        "link": cmd_link,
        "link-types": cmd_link_types,
        "attach": cmd_attach,
        "worklog": cmd_worklog,
        "history": cmd_history,
        "filters": cmd_filters,
        "filter": cmd_filter,
    }
    handler = dispatch.get(command)
    if not handler:
        raise JiraOpsError("config", f"Unknown command: {command}")
    handler(rest)


if __name__ == "__main__":
    run(main)
