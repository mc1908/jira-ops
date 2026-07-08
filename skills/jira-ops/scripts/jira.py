#!/usr/bin/env python3
"""jira-ops entrypoint. Dispatches to sub-commands and ensures the venv.

Usage:
  python scripts/jira.py <command> [options]

Commands:
  setup                 Create/update a profile (interactive or via flags)
  auth <sub>            set-token | test-auth | clear-token | whoami | reset
  search               Search issues by JQL or preset
  mine                 List issues assigned to you (preset shortcuts)
  view <ISSUE-KEY>     Show issue details
  comment <ISSUE-KEY>  Add a comment (supports --dry-run)
  comments <ISSUE-KEY> List comments on an issue
  update <ISSUE-KEY>   Edit fields: summary/description/labels/etc. (--dry-run)
  create               Create a new issue (--project --type --summary, --dry-run)
  assign <KEY>         Set/clear assignee (--to username | --to -) (--dry-run)
  link <KEY>           Link issues (--to OTHER --type "Blocks") (--dry-run)
  link-types           List configured issue link types
  attach <KEY>         Attach file(s) to an issue (--file PATH) (--dry-run)
  transitions <KEY>    List available transitions
  transition <KEY>     Move issue by transition id or status name (--dry-run)
  projects             List visible projects
  users                Look up users (--query NAME) to resolve usernames
  boards               List agile boards (optionally for a project)
  sprints              List sprints on a board/project (active|future|closed)
  sprint               Sprint details + status breakdown (active sprint by project)
  sprint-add           Move issues into a sprint (--id --issue, --dry-run)
  backlog              List a board/project backlog for sprint planning
  health               Local readiness check (no network)
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cli import ensure_venv  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent

_COMMANDS = {
    "setup": "jira_auth.py",
    "auth": "jira_auth.py",
    "search": "jira_issue.py",
    "mine": "jira_issue.py",
    "view": "jira_issue.py",
    "comment": "jira_issue.py",
    "comments": "jira_issue.py",
    "update": "jira_issue.py",
    "create": "jira_issue.py",
    "assign": "jira_issue.py",
    "link": "jira_issue.py",
    "link-types": "jira_issue.py",
    "attach": "jira_issue.py",
    "projects": "jira_project.py",
    "users": "jira_project.py",
    "transitions": "jira_transition.py",
    "transition": "jira_transition.py",
    "boards": "jira_sprint.py",
    "sprints": "jira_sprint.py",
    "sprint": "jira_sprint.py",
    "sprint-add": "jira_sprint.py",
    "backlog": "jira_sprint.py",
    "health": "bootstrap.py",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(__doc__ or "")
        return

    command = sys.argv[1]
    target = _COMMANDS.get(command)
    if not target:
        sys.stderr.write(f"Unknown command: {command}\n\n{__doc__}")
        sys.exit(2)

    # Bootstrap/health must run without requiring the venv first.
    if command != "health":
        ensure_venv()

    # Re-shape argv so the sub-script sees: <script> <command> <rest...>
    sys.argv = [str(_SCRIPTS / target), command, *sys.argv[2:]]
    runpy.run_path(str(_SCRIPTS / target), run_name="__main__")


if __name__ == "__main__":
    main()
