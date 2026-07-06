"""Platform-neutral resolution of the jira-ops config directory.

Resolution order for the base directory:
1. ``$JIRA_OPS_HOME`` if set (explicit override)
2. Windows: ``%APPDATA%\\jira-ops``
3. ``$XDG_CONFIG_HOME/jira-ops`` if XDG_CONFIG_HOME is set
4. ``~/.config/jira-ops``

This is intentionally not tied to any specific agent runtime (no ``~/.codex``).
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "jira-ops"
CONFIG_FILENAME = "config.json"
SECRETS_DIRNAME = "secrets"


def config_dir() -> Path:
    """Return the base config directory for jira-ops (not created)."""
    override = os.environ.get("JIRA_OPS_HOME")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def config_path() -> Path:
    """Full path to the config.json file."""
    return config_dir() / CONFIG_FILENAME


def secrets_dir() -> Path:
    """Directory for encrypted-fallback token files."""
    return config_dir() / SECRETS_DIRNAME


def ensure_config_dir() -> Path:
    """Create the config directory (and secrets subdir) if missing."""
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Best-effort restrictive permissions on POSIX.
    if os.name != "nt":
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass
    return d


def resolve_relative(path_value: str) -> Path:
    """Resolve a config-relative path (e.g. ``secrets/host.token``).

    Absolute paths and ``~`` are honored as-is; otherwise the value is treated
    as relative to the config directory.
    """
    p = Path(path_value).expanduser()
    if p.is_absolute():
        return p
    return config_dir() / p
