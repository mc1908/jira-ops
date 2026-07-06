"""Concise terminal + JSON output helpers."""

from __future__ import annotations

import json as _json
import sys
from typing import Any, List, Optional

from .config import Profile


def emit(payload: Any, *, as_json: bool, text: str = "") -> None:
    """Print either JSON or human text to stdout."""
    if as_json:
        sys.stdout.write(_json.dumps(payload, indent=2, default=str) + "\n")
    else:
        sys.stdout.write((text if text else _stringify(payload)) + "\n")


def _stringify(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return _json.dumps(payload, indent=2, default=str)


def _field(fields: dict, name: str) -> Any:
    return (fields or {}).get(name)


def _named(obj: Optional[dict], key: str = "name") -> str:
    if not obj:
        return "-"
    return obj.get(key) or obj.get("displayName") or "-"


def issue_summary_dict(issue: dict, profile: Optional[Profile] = None) -> dict:
    fields = issue.get("fields", {}) or {}
    key = issue.get("key", "?")
    status = _named(_field(fields, "status"))
    assignee = _named(_field(fields, "assignee"))
    reporter = _named(_field(fields, "reporter"))
    priority = _named(_field(fields, "priority"))
    labels = _field(fields, "labels") or []
    out = {
        "key": key,
        "summary": _field(fields, "summary") or "",
        "status": status,
        "assignee": assignee,
        "reporter": reporter,
        "priority": priority,
        "labels": labels,
    }
    if profile is not None:
        out["url"] = profile.browse_url(key)
    return out


def issue_table(issues: List[dict], profile: Optional[Profile] = None) -> str:
    if not issues:
        return "No issues."
    rows = [issue_summary_dict(i, profile) for i in issues]
    key_w = max(len(r["key"]) for r in rows)
    status_w = min(18, max(len(r["status"]) for r in rows))
    lines = []
    for r in rows:
        summary = r["summary"]
        if len(summary) > 60:
            summary = summary[:57] + "..."
        lines.append(
            f"{r['key']:<{key_w}}  {r['status'][:status_w]:<{status_w}}  "
            f"{r['assignee']:<14.14}  {summary}"
        )
    return "\n".join(lines)


def issue_detail(issue: dict, profile: Optional[Profile] = None) -> str:
    d = issue_summary_dict(issue, profile)
    fields = issue.get("fields", {}) or {}
    lines = [
        f"{d['key']}  {d['summary']}",
        f"  Status:   {d['status']}",
        f"  Assignee: {d['assignee']}",
        f"  Reporter: {d['reporter']}",
        f"  Priority: {d['priority']}",
        f"  Labels:   {', '.join(d['labels']) if d['labels'] else '-'}",
    ]
    updated = fields.get("updated")
    if updated:
        lines.append(f"  Updated:  {updated}")
    if d.get("url"):
        lines.append(f"  URL:      {d['url']}")
    desc = fields.get("description")
    if desc:
        text = str(desc).strip()
        if len(text) > 800:
            text = text[:800] + "\n  ...(truncated)"
        lines.append("")
        lines.append("Description:")
        lines.append("  " + text.replace("\n", "\n  "))
    return "\n".join(lines)
