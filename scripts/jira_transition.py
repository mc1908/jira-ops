#!/usr/bin/env python3
"""Transition commands: list and perform workflow transitions.

Invoked as:
  jira transitions ISSUE-KEY                 List available transitions
  jira transition  ISSUE-KEY --to "In Review"  [--comment "..."] [--dry-run]
  jira transition  ISSUE-KEY --id 41            [--dry-run]

Always fetches current status and available transitions before moving.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cli import add_common_args, ensure_venv, load_profile, run  # noqa: E402
from jira_common.client import JiraClient  # noqa: E402
from jira_common.errors import JiraOpsError  # noqa: E402
from jira_common.formatting import emit  # noqa: E402


def _fetch_transitions(client: JiraClient, issue_key: str) -> list:
    data = client.get_json(f"issue/{issue_key}/transitions")
    return data.get("transitions", [])


def _current_status(client: JiraClient, issue_key: str) -> str:
    issue = client.get_json(f"issue/{issue_key}", {"fields": "status"})
    return (issue.get("fields", {}).get("status") or {}).get("name", "?")


def cmd_transitions(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira transitions")
    add_common_args(parser)
    parser.add_argument("issue_key")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    status = _current_status(client, args.issue_key)
    transitions = _fetch_transitions(client, args.issue_key)
    rows = [{"id": t.get("id"), "name": t.get("name"),
             "to": (t.get("to") or {}).get("name")} for t in transitions]
    emit(
        {"ok": True, "issue": args.issue_key, "status": status, "transitions": rows},
        as_json=args.as_json,
        text=(f"{args.issue_key} is '{status}'. Available transitions:\n" +
              "\n".join(f"  [{r['id']}] {r['name']} -> {r['to']}" for r in rows))
             if rows else f"{args.issue_key} is '{status}'. No transitions available.",
    )


def cmd_transition(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira transition")
    add_common_args(parser)
    parser.add_argument("issue_key")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--to", help="Target status/transition name (case-insensitive).")
    group.add_argument("--id", help="Transition id.")
    parser.add_argument("--comment", help="Optional comment to add with the transition.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    if args.comment:
        client.guard_no_secret_leak(args.comment)

    status = _current_status(client, args.issue_key)
    transitions = _fetch_transitions(client, args.issue_key)

    chosen = None
    if args.id:
        chosen = next((t for t in transitions if str(t.get("id")) == str(args.id)), None)
    else:
        target = args.to.strip().lower()
        chosen = next(
            (t for t in transitions
             if (t.get("name", "").lower() == target
                 or (t.get("to") or {}).get("name", "").lower() == target)),
            None,
        )

    if not chosen:
        available = ", ".join(f"{t.get('name')}->{(t.get('to') or {}).get('name')}"
                              for t in transitions) or "(none)"
        raise JiraOpsError(
            "transition_not_found",
            f"No transition matching '{args.to or args.id}' from '{status}'. "
            f"Available: {available}",
        )

    body = {"transition": {"id": chosen.get("id")}}
    if args.comment:
        body["update"] = {"comment": [{"add": {"body": args.comment}}]}

    target_name = (chosen.get("to") or {}).get("name")
    if args.dry_run:
        emit(
            {"ok": True, "action": "transition", "dryRun": True, "issue": args.issue_key,
             "from": status, "to": target_name, "transitionId": chosen.get("id"),
             "request": body},
            as_json=args.as_json,
            text=(f"[dry-run] Would move {args.issue_key}: '{status}' -> '{target_name}' "
                  f"(transition {chosen.get('id')})."),
        )
        return

    client.post_json(f"issue/{args.issue_key}/transitions", body)
    emit(
        {"ok": True, "action": "transition", "issue": args.issue_key,
         "from": status, "to": target_name, "url": profile.browse_url(args.issue_key)},
        as_json=args.as_json,
        text=f"{args.issue_key} moved: '{status}' -> '{target_name}'.",
    )


def main() -> None:
    ensure_venv()
    if len(sys.argv) < 2:
        raise JiraOpsError("config", "Missing command.")
    command, rest = sys.argv[1], sys.argv[2:]
    if command == "transitions":
        cmd_transitions(rest)
    elif command == "transition":
        cmd_transition(rest)
    else:
        raise JiraOpsError("config", f"Unknown command: {command}")


if __name__ == "__main__":
    run(main)
