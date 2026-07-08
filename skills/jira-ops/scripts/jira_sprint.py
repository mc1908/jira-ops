#!/usr/bin/env python3
"""Agile commands: boards, sprints, sprint (details + breakdown), backlog.

Uses the Jira Agile REST API (/rest/agile/1.0), which is separate from the
core /rest/api/2 used by the issue commands. Read-only sprint planning support.

Invoked as:
  jira boards  [--project KEY] [--type scrum|kanban] [--json]
  jira sprints (--board ID | --project KEY) [--state active|future|closed] [--json]
  jira sprint  (--id ID | --project KEY) [--state active] [--issues] [--limit N] [--json]
  jira backlog (--board ID | --project KEY) [--limit N] [--json]
  jira sprint-add --id SPRINT_ID --issue KEY [--issue KEY ...] [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cli import add_common_args, ensure_venv, load_profile, resolve_project, run  # noqa: E402
from jira_common.client import JiraClient  # noqa: E402
from jira_common.errors import JiraOpsError  # noqa: E402
from jira_common.formatting import emit, issue_summary_dict, issue_table  # noqa: E402

_ISSUE_FIELDS = "summary,status,assignee,priority,updated"


# --------------------------------------------------------------------------- #
# Agile resolution helpers
# --------------------------------------------------------------------------- #
def _boards(client: JiraClient, profile, project: str | None, board_type: str | None):
    params: dict = {}
    if project:
        params["projectKeyOrId"] = project
    if board_type:
        params["type"] = board_type
    return client.paginate(f"{profile.agile_base}/board", key="values",
                           params=params, max_results=100)


def _one_board(client: JiraClient, profile, project: str, board_type: str = "scrum"):
    boards = _boards(client, profile, project, board_type)
    if not boards:
        # Fall back to any board type before giving up.
        boards = _boards(client, profile, project, None)
    if not boards:
        raise JiraOpsError("not_found", f"No board found for project {project}.")
    return boards[0]


def _sprints(client: JiraClient, profile, board_id, state: str | None):
    params: dict = {}
    if state:
        params["state"] = state
    return client.paginate(f"{profile.agile_base}/board/{board_id}/sprint",
                           key="values", params=params, max_results=100)


def _sprint_issues(client: JiraClient, profile, sprint_id, limit: int):
    return client.paginate(f"{profile.agile_base}/sprint/{sprint_id}/issue",
                           key="issues", params={"fields": _ISSUE_FIELDS},
                           max_results=limit)


def _status_breakdown(issues: list) -> dict:
    counts: dict = {}
    for issue in issues:
        status = ((issue.get("fields") or {}).get("status") or {}).get("name", "Unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _sprint_line(sprint: dict) -> str:
    dates = ""
    start, end = sprint.get("startDate"), sprint.get("endDate")
    if start or end:
        dates = f"  {str(start)[:10]} -> {str(end)[:10]}"
    return (f"  {str(sprint.get('id')):<6} {str(sprint.get('state', '?')):<7} "
            f"{sprint.get('name', '?')}{dates}")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_boards(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira boards")
    add_common_args(parser)
    parser.add_argument("--project", help="Filter to a project key.")
    parser.add_argument("--type", dest="board_type", choices=["scrum", "kanban"],
                        help="Board type filter.")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    project = args.project or profile.default_project
    boards = _boards(client, profile, project, args.board_type)
    rows = [{"id": b.get("id"), "name": b.get("name"), "type": b.get("type")} for b in boards]
    emit(
        {"ok": True, "count": len(rows), "boards": rows},
        as_json=args.as_json,
        text=(f"Boards ({len(rows)}):\n" +
              "\n".join(f"  {str(r['id']):<6} {r['type']:<7} {r['name']}" for r in rows))
             if rows else "No boards visible.",
    )


def cmd_sprints(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira sprints")
    add_common_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--board", type=int, help="Board id.")
    group.add_argument("--project", help="Resolve the project's scrum board.")
    parser.add_argument("--state", choices=["active", "future", "closed"],
                        help="Filter by sprint state.")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    if args.board:
        board_id, board_name = args.board, f"board {args.board}"
    else:
        board = _one_board(client, profile, resolve_project(args.project, profile))
        board_id, board_name = board.get("id"), board.get("name", "board")

    sprints = _sprints(client, profile, board_id, args.state)
    rows = [{"id": s.get("id"), "name": s.get("name"), "state": s.get("state"),
             "startDate": s.get("startDate"), "endDate": s.get("endDate")} for s in sprints]
    header = f"Sprints on {board_name} (id {board_id})"
    if args.state:
        header += f" [{args.state}]"
    emit(
        {"ok": True, "board": board_id, "count": len(rows), "sprints": rows},
        as_json=args.as_json,
        text=(f"{header}:\n" + "\n".join(_sprint_line(s) for s in sprints))
             if sprints else f"{header}: none.",
    )


def _pick_sprint(client: JiraClient, profile, project: str, state: str) -> dict:
    board = _one_board(client, profile, project)
    sprints = _sprints(client, profile, board.get("id"), state)
    if not sprints:
        raise JiraOpsError(
            "not_found",
            f"No {state} sprint on board '{board.get('name')}' (id {board.get('id')}).")
    return sprints[0]


def cmd_sprint(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira sprint")
    add_common_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--id", dest="sprint_id", type=int, help="Sprint id.")
    group.add_argument("--project", help="Resolve a sprint from the project's board.")
    parser.add_argument("--state", default="active", choices=["active", "future", "closed"],
                        help="With --project: which sprint to pick (default active).")
    parser.add_argument("--issues", action="store_true", help="Also list every issue.")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    if args.sprint_id:
        sprint = client.get_json(f"{profile.agile_base}/sprint/{args.sprint_id}")
    else:
        sprint = _pick_sprint(client, profile, resolve_project(args.project, profile), args.state)

    sprint_id = sprint.get("id")
    issues = _sprint_issues(client, profile, sprint_id, args.limit)
    breakdown = _status_breakdown(issues)

    payload = {
        "ok": True,
        "sprint": {
            "id": sprint_id,
            "name": sprint.get("name"),
            "state": sprint.get("state"),
            "startDate": sprint.get("startDate"),
            "endDate": sprint.get("endDate"),
            "goal": sprint.get("goal"),
        },
        "total": len(issues),
        "byStatus": breakdown,
    }
    if args.issues:
        payload["issues"] = [issue_summary_dict(i, profile) for i in issues]

    lines = [
        f"Sprint: {sprint.get('name')} ({sprint.get('state')})  id {sprint_id}",
    ]
    if sprint.get("startDate") or sprint.get("endDate"):
        lines.append(f"  Dates:  {str(sprint.get('startDate'))[:10]} -> "
                     f"{str(sprint.get('endDate'))[:10]}")
    if sprint.get("goal"):
        lines.append(f"  Goal:   {sprint.get('goal')}")
    lines.append(f"  Issues: {len(issues)} total")
    for status, count in breakdown.items():
        lines.append(f"    {status:<16} {count}")
    if args.issues and issues:
        lines.append("")
        lines.append(issue_table(issues, profile))

    emit(payload, as_json=args.as_json, text="\n".join(lines))


def cmd_backlog(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira backlog")
    add_common_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--board", type=int, help="Board id.")
    group.add_argument("--project", help="Resolve the project's scrum board.")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    if args.board:
        board_id, board_name = args.board, f"board {args.board}"
    else:
        board = _one_board(client, profile, resolve_project(args.project, profile))
        board_id, board_name = board.get("id"), board.get("name", "board")

    issues = client.paginate(f"{profile.agile_base}/board/{board_id}/backlog",
                             key="issues", params={"fields": _ISSUE_FIELDS},
                             max_results=args.limit)
    emit(
        {"ok": True, "board": board_id, "count": len(issues),
         "issues": [issue_summary_dict(i, profile) for i in issues]},
        as_json=args.as_json,
        text=(f"Backlog on {board_name} (id {board_id}) ({len(issues)}):\n" +
              issue_table(issues, profile)) if issues
             else f"Backlog on {board_name} (id {board_id}): empty.",
    )


def cmd_sprint_add(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira sprint-add")
    add_common_args(parser)
    parser.add_argument("--id", dest="sprint_id", type=int, required=True,
                        help="Target sprint id (see 'sprints').")
    parser.add_argument("--issue", action="append", dest="issues", required=True,
                        help="Issue key to move into the sprint (repeatable).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    # Fetch the sprint first (confirms it exists and surfaces its name/state).
    sprint = client.get_json(f"{profile.agile_base}/sprint/{args.sprint_id}")
    keys = [k.strip() for k in args.issues]
    label = f"{args.sprint_id} ({sprint.get('name')})"

    if args.dry_run:
        emit(
            {"ok": True, "action": "sprint-add", "dryRun": True, "sprint": args.sprint_id,
             "issues": keys, "request": {"issues": keys}},
            as_json=args.as_json,
            text=f"[dry-run] Would move {', '.join(keys)} into sprint {label}.",
        )
        return

    client.add_to_sprint(args.sprint_id, keys)
    emit(
        {"ok": True, "action": "sprint-add", "sprint": args.sprint_id,
         "name": sprint.get("name"), "issues": keys},
        as_json=args.as_json,
        text=f"Moved {', '.join(keys)} into sprint {label}.",
    )


def main() -> None:
    ensure_venv()
    if len(sys.argv) < 2:
        raise JiraOpsError("config", "Missing command.")
    command, rest = sys.argv[1], sys.argv[2:]
    dispatch = {
        "boards": cmd_boards,
        "sprints": cmd_sprints,
        "sprint": cmd_sprint,
        "backlog": cmd_backlog,
        "sprint-add": cmd_sprint_add,
    }
    handler = dispatch.get(command)
    if not handler:
        raise JiraOpsError("config", f"Unknown command: {command}")
    handler(rest)


if __name__ == "__main__":
    run(main)
