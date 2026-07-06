"""Load, validate, and save jira-ops profile configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import paths
from .errors import JiraOpsError


@dataclass
class AuthConfig:
    type: str = "auto"  # auto | system-keyring | encrypted-file
    target: str = ""
    fallback_encrypted_path: str = ""


@dataclass
class Profile:
    name: str
    base_url: str
    auth: AuthConfig = field(default_factory=AuthConfig)
    api_version: str = "2"
    verify_tls: bool = True
    ca_cert_path: Optional[str] = None
    proxy: Optional[str] = None
    default_project: Optional[str] = None

    @property
    def api_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/{self.api_version}"

    @property
    def agile_base(self) -> str:
        """Base for the Jira Agile (boards/sprints/backlog) REST API."""
        return f"{self.base_url.rstrip('/')}/rest/agile/1.0"

    def browse_url(self, issue_key: str) -> str:
        return f"{self.base_url.rstrip('/')}/browse/{issue_key}"


@dataclass
class Config:
    profiles: dict
    default_profile: str

    def get(self, name: Optional[str] = None) -> Profile:
        key = name or self.default_profile
        if key not in self.profiles:
            raise JiraOpsError(
                "config", f"Profile '{key}' not found in config."
            )
        return self.profiles[key]


def _host_of(base_url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(base_url).netloc or base_url


def default_auth(base_url: str) -> AuthConfig:
    host = _host_of(base_url)
    return AuthConfig(
        type="auto",
        target=f"jira-pat:{base_url.rstrip('/')}",
        fallback_encrypted_path=f"secrets/{host}.token",
    )


def _profile_from_dict(name: str, d: dict) -> Profile:
    auth_d = d.get("auth", {}) or {}
    base_url = d.get("baseUrl", "")
    auth = AuthConfig(
        type=auth_d.get("type", "auto"),
        target=auth_d.get("target", f"jira-pat:{base_url.rstrip('/')}"),
        fallback_encrypted_path=auth_d.get(
            "fallbackEncryptedPath", f"secrets/{_host_of(base_url)}.token"
        ),
    )
    return Profile(
        name=name,
        base_url=base_url,
        auth=auth,
        api_version=str(d.get("apiVersion", "2")),
        verify_tls=bool(d.get("verifyTls", True)),
        ca_cert_path=d.get("caCertPath"),
        proxy=d.get("proxy"),
        default_project=d.get("defaultProject"),
    )


def _profile_to_dict(p: Profile) -> dict:
    return {
        "baseUrl": p.base_url,
        "auth": {
            "type": p.auth.type,
            "target": p.auth.target,
            "fallbackEncryptedPath": p.auth.fallback_encrypted_path,
        },
        "apiVersion": p.api_version,
        "verifyTls": p.verify_tls,
        "caCertPath": p.ca_cert_path,
        "proxy": p.proxy,
        "defaultProject": p.default_project,
    }


def config_exists() -> bool:
    return paths.config_path().is_file()


def load() -> Config:
    path = paths.config_path()
    if not path.is_file():
        raise JiraOpsError(
            "config",
            f"No config found at {path}. Run bootstrap or 'jira setup' first.",
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JiraOpsError("config", f"Config unreadable: {exc}") from exc

    profiles_raw = raw.get("profiles", {})
    if not profiles_raw:
        raise JiraOpsError("config", "Config has no profiles.")
    profiles = {
        name: _profile_from_dict(name, d) for name, d in profiles_raw.items()
    }
    default_profile = raw.get("defaultProfile") or next(iter(profiles))
    return Config(profiles=profiles, default_profile=default_profile)


def save(config: Config) -> Path:
    paths.ensure_config_dir()
    path = paths.config_path()
    data = {
        "profiles": {n: _profile_to_dict(p) for n, p in config.profiles.items()},
        "defaultProfile": config.default_profile,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def upsert_profile(
    name: str,
    base_url: str,
    *,
    api_version: str = "2",
    verify_tls: bool = True,
    ca_cert_path: Optional[str] = None,
    proxy: Optional[str] = None,
    default_project: Optional[str] = None,
    make_default: bool = True,
) -> Config:
    """Create/update a profile, preserving other profiles if config exists."""
    if config_exists():
        cfg = load()
    else:
        cfg = Config(profiles={}, default_profile=name)

    # Preserve an existing default project when the caller does not override it.
    existing = cfg.profiles.get(name)
    if default_project is None and existing is not None:
        default_project = existing.default_project

    profile = Profile(
        name=name,
        base_url=base_url,
        auth=default_auth(base_url),
        api_version=api_version,
        verify_tls=verify_tls,
        ca_cert_path=ca_cert_path,
        proxy=proxy,
        default_project=default_project,
    )
    cfg.profiles[name] = profile
    if make_default or not cfg.default_profile:
        cfg.default_profile = name
    save(cfg)
    return cfg
