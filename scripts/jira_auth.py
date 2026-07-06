#!/usr/bin/env python3
"""Profile setup and PAT authentication commands.

Invoked as:
  jira setup   [--name --base-url --api-version --ca-cert --proxy --no-verify-tls]
  jira auth set-token   [--token-stdin]   (reads PAT from stdin/env/secure prompt)
  jira auth test-auth
  jira auth whoami
  jira auth clear-token
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cli import add_common_args, ensure_venv, load_profile, run  # noqa: E402
from jira_common import auth as auth_mod  # noqa: E402
from jira_common import config as config_mod  # noqa: E402
from jira_common.client import JiraClient  # noqa: E402
from jira_common.errors import JiraOpsError  # noqa: E402
from jira_common.formatting import emit  # noqa: E402


def _read_secret(token_stdin: bool) -> str:
    if token_stdin:
        data = sys.stdin.readline().strip()
        if not data:
            raise JiraOpsError("auth", "No token received on stdin.")
        return data
    env_token = os.environ.get("JIRA_OPS_TOKEN")
    if env_token:
        return env_token.strip()
    try:
        return getpass.getpass("Jira PAT (input hidden): ").strip()
    except (EOFError, OSError) as exc:
        raise JiraOpsError(
            "auth", "Cannot read PAT interactively; use --token-stdin."
        ) from exc


def cmd_setup(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira setup")
    add_common_args(parser)
    parser.add_argument("--name", default="default", help="Profile name.")
    parser.add_argument("--base-url", required=True, help="Jira base URL, e.g. https://jira.example.com")
    parser.add_argument("--api-version", default="2")
    parser.add_argument("--ca-cert", default=None, help="Path to corporate CA bundle.")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--no-verify-tls", action="store_true",
                        help="Disable TLS verification (discouraged; prefer --ca-cert).")
    args = parser.parse_args(argv)

    cfg = config_mod.upsert_profile(
        args.name,
        args.base_url,
        api_version=args.api_version,
        verify_tls=not args.no_verify_tls,
        ca_cert_path=args.ca_cert,
        proxy=args.proxy,
    )
    profile = cfg.get(args.name)
    backend = auth_mod.describe_backend(profile)
    payload = {
        "ok": True,
        "action": "setup",
        "profile": args.name,
        "baseUrl": args.base_url,
        "backend": backend,
        "configPath": str(config_mod.paths.config_path()),
    }
    text = (
        f"Profile '{args.name}' saved -> {config_mod.paths.config_path()}\n"
        f"  base URL: {args.base_url}\n"
        f"  secret backend: {backend}\n"
        f"Next: jira auth set-token   then   jira auth test-auth"
    )
    emit(payload, as_json=args.as_json, text=text)


def cmd_set_token(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira auth set-token")
    add_common_args(parser)
    parser.add_argument("--token-stdin", action="store_true",
                        help="Read the PAT from stdin instead of a prompt.")
    parser.add_argument("--no-test", action="store_true",
                        help="Skip immediate validation.")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    token = _read_secret(args.token_stdin)
    backend = auth_mod.store_token(profile, token)

    result = {"ok": True, "action": "set-token", "profile": profile.name, "backend": backend}
    if not args.no_test:
        client = JiraClient(profile)  # resolves token from store
        me = client.get_json("myself")
        result["identity"] = {
            "name": me.get("name"),
            "displayName": me.get("displayName"),
            "email": me.get("emailAddress"),
        }
    text = f"Token stored via {backend} for profile '{profile.name}'."
    if "identity" in result:
        ident = result["identity"]
        text += f"\nValidated as {ident.get('displayName')} ({ident.get('name')})."
    emit(result, as_json=args.as_json, text=text)


def cmd_test_auth(argv: list, *, whoami: bool = False) -> None:
    parser = argparse.ArgumentParser(prog="jira auth test-auth")
    add_common_args(parser)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    client = JiraClient(profile)
    me = client.get_json("myself")
    identity = {
        "name": me.get("name"),
        "displayName": me.get("displayName"),
        "email": me.get("emailAddress"),
        "timeZone": me.get("timeZone"),
    }
    payload = {"ok": True, "action": "whoami" if whoami else "test-auth",
               "profile": profile.name, "baseUrl": profile.base_url, "identity": identity}
    text = (
        f"Authenticated to {profile.base_url} as "
        f"{identity['displayName']} ({identity['name']})."
    )
    emit(payload, as_json=args.as_json, text=text)


def cmd_clear_token(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira auth clear-token")
    add_common_args(parser)
    args = parser.parse_args(argv)
    profile = load_profile(args.profile)
    removed = auth_mod.clear_token(profile)
    payload = {"ok": True, "action": "clear-token", "profile": profile.name, "removed": removed}
    emit(payload, as_json=args.as_json,
         text=("Token removed." if removed else "No stored token found."))


def main() -> None:
    ensure_venv()
    if len(sys.argv) < 2:
        raise JiraOpsError("config", "Missing command.")
    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "setup":
        cmd_setup(rest)
        return
    if command == "auth":
        if not rest:
            raise JiraOpsError("config", "auth requires a subcommand.")
        sub, sub_rest = rest[0], rest[1:]
        if sub == "set-token":
            cmd_set_token(sub_rest)
        elif sub == "test-auth":
            cmd_test_auth(sub_rest)
        elif sub == "whoami":
            cmd_test_auth(sub_rest, whoami=True)
        elif sub == "clear-token":
            cmd_clear_token(sub_rest)
        else:
            raise JiraOpsError("config", f"Unknown auth subcommand: {sub}")
        return
    raise JiraOpsError("config", f"Unknown command: {command}")


if __name__ == "__main__":
    run(main)
