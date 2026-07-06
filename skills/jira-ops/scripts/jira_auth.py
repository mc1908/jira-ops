#!/usr/bin/env python3
"""Profile setup and PAT authentication commands.

Invoked as:
  jira setup                 Interactive guided setup (base URL, project, token)
  jira setup --base-url URL [--name --default-project --api-version --ca-cert --proxy --no-verify-tls]
  jira auth set-token   [--token-stdin]   (reads PAT from stdin/env/secure prompt)
  jira auth test-auth
  jira auth whoami
  jira auth clear-token
  jira auth reset         Wipe all config + secrets (fresh-state reset; add --venv to also remove .venv)
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
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


def _prompt(label: str, *, default: str | None = None, required: bool = False) -> str:
    """Prompt for a line of input, with an optional default and required check."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"{label}{suffix}: ").strip()
        except (EOFError, OSError) as exc:
            raise JiraOpsError(
                "config",
                "Interactive input is not available. Re-run 'jira setup' with "
                "flags (e.g. --base-url ...) instead.",
            ) from exc
        if not value and default is not None:
            return default
        if value or not required:
            return value
        sys.stderr.write("  A value is required.\n")


def _test_identity(profile) -> None:
    """Validate stored token by calling /myself; print a friendly result."""
    try:
        client = JiraClient(profile)
        me = client.get_json("myself")
        sys.stdout.write(
            f"Validated as {me.get('displayName')} ({me.get('name')}).\n"
        )
    except JiraOpsError as exc:
        sys.stdout.write(
            f"Saved, but validation failed: [{exc.category}] {exc.message}\n"
            f"  hint: {exc.hint}\n"
        )


def _run_interactive_setup(args) -> None:
    """Collect all profile + token details in one guided session."""
    sys.stdout.write("Interactive Jira setup — press Enter to accept [defaults].\n\n")
    name = args.name or _prompt("Profile name", default="default")
    base_url = args.base_url or _prompt(
        "Jira base URL (e.g. https://jira.example.com)", required=True)
    default_project = args.default_project or (
        _prompt("Default project key (optional, e.g. ABC)", default="") or None)
    ca_cert = args.ca_cert or (
        _prompt("Corporate CA bundle path (optional)", default="") or None)
    proxy = args.proxy or (
        _prompt("HTTP(S) proxy URL (optional)", default="") or None)
    verify_tls = not args.no_verify_tls

    cfg = config_mod.upsert_profile(
        name,
        base_url,
        api_version=args.api_version,
        verify_tls=verify_tls,
        ca_cert_path=ca_cert,
        proxy=proxy,
        default_project=default_project,
    )
    profile = cfg.get(name)
    backend = auth_mod.describe_backend(profile)
    sys.stdout.write(
        f"\nProfile '{name}' saved -> {config_mod.paths.config_path()}\n"
        f"  base URL:        {base_url}\n"
        f"  default project: {default_project or '(none)'}\n"
        f"  secret backend:  {backend}\n\n"
    )

    has_token = auth_mod.token_exists(profile)
    if has_token:
        sys.stdout.write(
            "A PAT is already stored for this profile. Enter a new one to "
            "rotate it, or skip to keep the current token.\n")
        question, default = "Update the stored PAT now?", "N"
    else:
        question, default = "Enter your PAT now?", "Y"

    if _prompt(question, default=default).lower().startswith("y"):
        token = _read_secret(False)
        stored = auth_mod.store_token(profile, token)
        verb = "updated" if has_token else "stored"
        sys.stdout.write(f"Token {verb} via {stored}.\n")
        _test_identity(profile)
    else:
        sys.stdout.write(
            "Skipped. To set or update the PAT later:\n"
            "  jira auth set-token      # prompts securely; re-run any time to rotate\n"
            "  jira auth test-auth      # validate against /myself\n")


def cmd_setup(argv: list) -> None:
    parser = argparse.ArgumentParser(prog="jira setup")
    add_common_args(parser)
    parser.add_argument("--name", default=None, help="Profile name (default: default).")
    parser.add_argument("--base-url", default=None,
                        help="Jira base URL, e.g. https://jira.example.com")
    parser.add_argument("--default-project", default=None,
                        help="Project key used when --project is omitted (e.g. ABC).")
    parser.add_argument("--api-version", default="2")
    parser.add_argument("--ca-cert", default=None, help="Path to corporate CA bundle.")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--no-verify-tls", action="store_true",
                        help="Disable TLS verification (discouraged; prefer --ca-cert).")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Guided prompts for every setting (also default when "
                             "--base-url is omitted).")
    args = parser.parse_args(argv)

    # Interactive when explicitly asked or when the base URL was not supplied.
    if args.interactive or not args.base_url:
        _run_interactive_setup(args)
        return

    name = args.name or "default"
    cfg = config_mod.upsert_profile(
        name,
        args.base_url,
        api_version=args.api_version,
        verify_tls=not args.no_verify_tls,
        ca_cert_path=args.ca_cert,
        proxy=args.proxy,
        default_project=args.default_project,
    )
    profile = cfg.get(name)
    backend = auth_mod.describe_backend(profile)
    payload = {
        "ok": True,
        "action": "setup",
        "profile": name,
        "baseUrl": args.base_url,
        "defaultProject": profile.default_project,
        "backend": backend,
        "configPath": str(config_mod.paths.config_path()),
    }
    text = (
        f"Profile '{name}' saved -> {config_mod.paths.config_path()}\n"
        f"  base URL: {args.base_url}\n"
        f"  default project: {profile.default_project or '(none)'}\n"
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
    replacing = auth_mod.token_exists(profile)
    token = _read_secret(args.token_stdin)
    backend = auth_mod.store_token(profile, token)
    verb = "updated" if replacing else "stored"

    result = {"ok": True, "action": "set-token", "profile": profile.name,
              "backend": backend, "replaced": replacing}
    if not args.no_test:
        client = JiraClient(profile)  # resolves token from store
        me = client.get_json("myself")
        result["identity"] = {
            "name": me.get("name"),
            "displayName": me.get("displayName"),
            "email": me.get("emailAddress"),
        }
    text = f"Token {verb} via {backend} for profile '{profile.name}'."
    if replacing:
        text += " Previous PAT was overwritten (rotated)."
    if "identity" in result:
        ident = result["identity"]
        text += f"\nValidated as {ident.get('displayName')} ({ident.get('name')})."
    if os.environ.get("JIRA_OPS_TOKEN"):
        text += ("\nNote: JIRA_OPS_TOKEN is set and takes precedence over the "
                 "stored token until you unset it.")
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


def cmd_reset(argv: list) -> None:
    parser = argparse.ArgumentParser(
        prog="jira auth reset",
        description="Remove ALL jira-ops config and secrets for a clean slate. "
                    "Useful before testing a fresh install.")
    parser.add_argument("--venv", action="store_true",
                        help="Also delete the skill-local .venv directory.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt.")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    config_dir = config_mod.paths.config_dir()
    from jira_common.setup import venv_dir  # local import to keep setup module optional
    venv_path = venv_dir()

    if not args.yes and sys.stdin.isatty():
        sys.stdout.write("Will permanently delete:\n")
        sys.stdout.write(f"  {config_dir}  "
                         f"{'(exists)' if config_dir.exists() else '(not present)'}\n")
        if args.venv:
            sys.stdout.write(f"  {venv_path}  "
                             f"{'(exists)' if venv_path.exists() else '(not present)'}\n")
            sys.stdout.write("  Note: .venv will be shown as a manual step because the\n"
                             "  running Python interpreter holds locks on its files.\n")
        answer = _prompt("Continue?", default="N")
        if not answer.lower().startswith("y"):
            sys.stdout.write("Aborted.\n")
            return

    removed_dirs = []
    if config_dir.exists():
        shutil.rmtree(config_dir)
        removed_dirs.append(str(config_dir))

    lines = ["Reset complete."]
    if removed_dirs:
        lines += [f"  Deleted: {d}" for d in removed_dirs]
    else:
        lines.append("  Config directory was already absent.")

    if args.venv and venv_path.exists():
        # Cannot rmtree the venv in-process: Windows locks .pyd files loaded by
        # the running interpreter. Print the one-liner to finish manually.
        lines.append("")
        lines.append("Delete the venv manually (run after this command exits):")
        if os.name == "nt":
            lines.append(f"  Remove-Item -Recurse -Force \"{venv_path}\"")
        else:
            lines.append(f"  rm -rf \"{venv_path}\"")
    elif args.venv:
        lines.append("  .venv was already absent.")

    lines.append("")
    lines.append("Then run 'python scripts/bootstrap.py' to set up again.")
    payload = {"ok": True, "action": "reset", "removed": removed_dirs,
               "venvPendingManualDelete": str(venv_path) if args.venv else None}
    emit(payload, as_json=args.as_json, text="\n".join(lines))


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
        elif sub == "reset":
            cmd_reset(sub_rest)
        else:
            raise JiraOpsError("config", f"Unknown auth subcommand: {sub}")
        return
    raise JiraOpsError("config", f"Unknown command: {command}")


if __name__ == "__main__":
    run(main)
