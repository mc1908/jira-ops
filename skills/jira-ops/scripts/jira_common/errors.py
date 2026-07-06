"""Normalized error categories, exit codes, and a JiraOpsError exception.

Exit codes are stable so callers (agents, scripts) can branch without parsing
prose. 0 is success; category codes start at 10.
"""

from __future__ import annotations

from typing import Optional

# Stable process exit codes per error category.
EXIT_OK = 0
EXIT_USAGE = 2  # argparse default for bad args
EXIT_CONFIG = 10
EXIT_AUTH = 11
EXIT_AUTHORIZATION = 12
EXIT_NETWORK = 13
EXIT_TLS = 14
EXIT_NOT_FOUND = 15
EXIT_INVALID_JQL = 16
EXIT_TRANSITION_NOT_FOUND = 17
EXIT_VALIDATION = 18
EXIT_RATE_LIMITED = 19
EXIT_SERVER = 20
EXIT_UNKNOWN = 30

CATEGORY_EXIT = {
    "config": EXIT_CONFIG,
    "auth": EXIT_AUTH,
    "authorization": EXIT_AUTHORIZATION,
    "network": EXIT_NETWORK,
    "tls": EXIT_TLS,
    "not_found": EXIT_NOT_FOUND,
    "invalid_jql": EXIT_INVALID_JQL,
    "transition_not_found": EXIT_TRANSITION_NOT_FOUND,
    "validation": EXIT_VALIDATION,
    "rate_limited": EXIT_RATE_LIMITED,
    "server": EXIT_SERVER,
    "unknown": EXIT_UNKNOWN,
}

# Short, human next-step hints per category.
CATEGORY_HINT = {
    "config": "Run bootstrap or 'jira setup' to create/repair the config.",
    "auth": "Token missing or invalid. Run 'jira auth set-token' with a fresh PAT.",
    "authorization": "Your account lacks permission for this action in Jira.",
    "network": "Check connectivity, base URL, and any required proxy settings.",
    "tls": "Set 'caCertPath' in config to your corporate CA bundle (do not disable TLS).",
    "not_found": "Check the issue/project key or that you can see it.",
    "invalid_jql": "Fix the JQL syntax or field/status names for this instance.",
    "transition_not_found": "List transitions first; names vary by workflow.",
    "validation": "Check required fields and value formats for this issue type.",
    "rate_limited": "Rate limited by Jira. Retry after a short delay.",
    "server": "Jira returned a server error. Retry later.",
    "unknown": "Unexpected error. Re-run with --json for details.",
}


class JiraOpsError(Exception):
    """A normalized, user-facing error."""

    def __init__(
        self,
        category: str,
        message: str,
        *,
        status: Optional[int] = None,
        jira_messages: Optional[list] = None,
    ) -> None:
        super().__init__(message)
        self.category = category if category in CATEGORY_EXIT else "unknown"
        self.message = message
        self.status = status
        self.jira_messages = jira_messages or []

    @property
    def exit_code(self) -> int:
        return CATEGORY_EXIT.get(self.category, EXIT_UNKNOWN)

    @property
    def hint(self) -> str:
        return CATEGORY_HINT.get(self.category, CATEGORY_HINT["unknown"])

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "category": self.category,
            "status": self.status,
            "message": self.message,
            "jiraMessages": self.jira_messages,
            "hint": self.hint,
        }
