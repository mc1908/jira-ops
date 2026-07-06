---
name: jira-ops
description: >-
  Use for Jira Data Center / Server work via the official REST API with PAT auth
  (no Jira CLI, no MCP). Triggers on "jira", "ticket", "issue", "sprint",
  "backlog", issue keys like ABC-123, and requests to search, view, comment on,
  transition, or create issues, draft status/standup updates, or set up/validate
  a Jira PAT.
---

# Jira Ops

Deterministic Jira **Data Center / Server** operations over the official REST API
(`/rest/api/2`) using a Personal Access Token. No Jira CLI, no MCP, no Cloud auth.

All behavior lives in Python scripts under `scripts/`. Prefer these scripts over
ad-hoc `curl`/REST calls so auth, pagination, retries, and secret redaction stay
consistent.

## Interpreter contract (read first)

After setup, a skill-local virtual environment exists at `<skill-root>/.venv/`.
The entrypoint `scripts/jira.py` **auto re-execs into that venv**, so always call:

```
python scripts/jira.py <command> [options]
```

Do not call the other `scripts/*.py` modules directly; go through `jira.py`.
Add `--json` to any command for machine-readable output.

## First-time setup

If a command reports missing config or dependencies, run setup once:

```
python scripts/bootstrap.py                               # create .venv + install deps
python scripts/jira.py setup --base-url "https://JIRA_HOST" --name default
python scripts/jira.py auth set-token --token-stdin       # PAT via stdin (not argv)
python scripts/jira.py auth test-auth                     # validates GET /myself
```

- The PAT is stored in the OS secret store if available, else a DPAPI-encrypted
  file (Windows) / `0600` file (POSIX) under the platform config dir — never in
  the repo, never echoed.
- For a corporate CA, pass `--ca-cert "C:\path\ca-bundle.pem"`. Behind a proxy,
  pass `--proxy`. Never disable TLS as a shortcut.

## Quick reference

| Intent | Command |
|--------|---------|
| Who am I | `python scripts/jira.py auth whoami` |
| My open work | `python scripts/jira.py mine --preset my-open` |
| My in-progress | `python scripts/jira.py mine --preset my-in-progress` |
| Stale / blocked | `python scripts/jira.py mine --preset my-stale` / `my-blocked` |
| Search JQL | `python scripts/jira.py search --jql "project = ABC AND status = Open"` |
| Open in a project | `python scripts/jira.py search --project ABC` |
| View a ticket | `python scripts/jira.py view ABC-123` |
| List transitions | `python scripts/jira.py transitions ABC-123` |
| Transition | `python scripts/jira.py transition ABC-123 --to "In Review"` |
| Comment | `python scripts/jira.py comment ABC-123 --body "text"` |
| Projects | `python scripts/jira.py projects` |
| Local health | `python scripts/jira.py health` |

Presets: `my-open`, `my-in-progress`, `my-stale`, `my-blocked`,
`recently-updated-by-me`, `reported-by-me-open`.

## Safety rules (always)

- **Fetch current state first.** Every write command re-reads the issue before acting.
- **Preview writes.** `comment` and `transition` accept `--dry-run` to show the exact
  payload. Use it before real writes unless the user clearly asked to send.
- **Transitions are runtime data.** Never assume names; run `transitions KEY` first.
  Transition by `--to "Status/Transition name"` or `--id`.
- **Confirm before write.** Get user approval before `comment` / `transition`.
- **Never print or commit the PAT.** Read tokens via stdin/prompt, not argv.
- **Data Center specifics:** assignee uses `username` (not Cloud `accountId`);
  comment bodies use wiki markup / plain text (not ADF).

## Drafting status updates

Turn implementation/test context into a Jira comment instead of hand-writing it:

```
python scripts/jira.py comment ABC-123 --template implementation-update \
  --summary "Wired retry + pagination" \
  --change "client.py retries" --change "search() paginates" \
  --test "unit: client" --result "all green" --next-step "review" --dry-run
```

Templates: `implementation-update`, `test-result`, `blocked`, `handoff`.

## When to load references

| Task | Reference |
|------|-----------|
| Non-trivial JQL, preset tuning | `references/examples.md` |
| Endpoints, createmeta, field IDs | `references/endpoints.md` |
| Auth backends, TLS/proxy, secrets | `references/security.md` |
| Install / troubleshooting setup | `references/setup.md` |

## Exit codes (for `--json` callers)

`0` ok · `10` config · `11` auth · `12` authorization · `13` network · `14` tls ·
`15` not-found · `16` invalid-jql · `17` transition-not-found · `18` validation ·
`19` rate-limited · `20` server.
