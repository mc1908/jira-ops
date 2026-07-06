"""Shared library for the jira-ops skill.

Modules:
- paths:      resolve the platform config directory (tool-neutral)
- config:     load/validate/save profile configuration
- errors:     normalized error categories and exit codes
- auth:       resolve/store the PAT via keyring or an encrypted local fallback
- client:     shared Jira REST client (pagination, retries, redaction)
- presets:    JQL presets and comment templates
- formatting: concise terminal + JSON output helpers
- setup:      environment checks, venv creation, dependency install, health check
"""

__all__ = [
    "paths",
    "config",
    "errors",
    "auth",
    "client",
    "presets",
    "formatting",
    "setup",
]
