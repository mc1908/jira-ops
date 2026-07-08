#!/usr/bin/env python3
"""Project commands: list projects, view metadata, create-meta, user lookup.

Invoked as:
  jira projects                 List visible projects
  jira projects --key PROJ      Show one project's metadata
  jira projects --key PROJ --createmeta   Required/allowed fields for creation
  jira users --query NAME       Look up users (resolve assignee usernames)
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


def cmd_projects(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira projects")
    add_common_args(parser)
    parser.add_argument("--key", help="Show metadata for a single project.")
    parser.add_argument("--createmeta", action="store_true",
                        help="With --key: list issue types and creatable fields.")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)

    if args.key and args.createmeta:
        data = client.get_json(
            f"issue/createmeta",
            {"projectKeys": args.key, "expand": "projects.issuetypes.fields"},
        )
        projects = data.get("projects", [])
        summary = []
        for proj in projects:
            for it in proj.get("issuetypes", []):
                fields = it.get("fields", {})
                required = [f.get("name", fid) for fid, f in fields.items() if f.get("required")]
                summary.append({
                    "issueType": it.get("name"),
                    "id": it.get("id"),
                    "requiredFields": required,
                })
        emit(
            {"ok": True, "project": args.key, "createMeta": summary},
            as_json=args.as_json,
            text="\n".join(
                f"{s['issueType']:<14} required: {', '.join(s['requiredFields']) or '-'}"
                for s in summary
            ) or "No creatable issue types visible.",
        )
        return

    if args.key:
        proj = client.get_json(f"project/{args.key}")
        payload = {
            "ok": True,
            "project": {
                "key": proj.get("key"),
                "name": proj.get("name"),
                "id": proj.get("id"),
                "lead": (proj.get("lead") or {}).get("displayName"),
                "issueTypes": [it.get("name") for it in proj.get("issueTypes", [])],
            },
        }
        p = payload["project"]
        emit(payload, as_json=args.as_json,
             text=(f"{p['key']}  {p['name']}\n  Lead: {p['lead']}\n"
                   f"  Issue types: {', '.join(p['issueTypes']) or '-'}"))
        return

    projects = client.paginate("project", key="values", max_results=args.limit)
    rows = [{"key": p.get("key"), "name": p.get("name")} for p in projects]
    emit(
        {"ok": True, "count": len(rows), "projects": rows},
        as_json=args.as_json,
        text=(f"Projects ({len(rows)}):\n" +
              "\n".join(f"  {r['key']:<12} {r['name']}" for r in rows)) if rows
             else "No visible projects.",
    )


def cmd_users(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira users")
    add_common_args(parser)
    parser.add_argument("--query", required=True,
                        help="Username, display name, or email fragment to search.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    users = client.search_users(args.query, max_results=args.limit)
    rows = [{"name": u.get("name"), "displayName": u.get("displayName"),
             "email": u.get("emailAddress"), "active": u.get("active", True)}
            for u in users]
    emit(
        {"ok": True, "query": args.query, "count": len(rows), "users": rows},
        as_json=args.as_json,
        text=(f"Users matching '{args.query}' ({len(rows)}):\n" +
              "\n".join(f"  {r['name']:<20} {r['displayName']}"
                        f"{'' if r['active'] else '  (inactive)'}" for r in rows))
             if rows else f"No users matching '{args.query}'.",
    )


def main() -> None:
    ensure_venv()
    if len(sys.argv) < 2:
        raise JiraOpsError("config", "Missing command.")
    command, rest = sys.argv[1], sys.argv[2:]
    dispatch = {
        "projects": cmd_projects,
        "users": cmd_users,
    }
    handler = dispatch.get(command)
    if not handler:
        raise JiraOpsError("config", f"Unknown command: {command}")
    handler(rest)


if __name__ == "__main__":
    run(main)
