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

## ⚠ Check for full installation first

This skill ships Python scripts that must be present alongside this `SKILL.md`.
**Before doing anything else**, verify the `scripts/` directory exists next to this
file:

```
ls <skill-root>/scripts/      # should contain jira.py, bootstrap.py, etc.
```

If `scripts/` is **missing**, the `skills` CLI only installed this `SKILL.md`.
Replace it with the full repo — and **remove `.git`** afterwards if this skill
lives inside an existing git repository (to avoid a nested repo):

```powershell
# PowerShell — download archive (no nested git, recommended)
Invoke-WebRequest https://github.com/mc1908/jira-ops/archive/refs/heads/main.zip -OutFile jira-ops.zip
Expand-Archive jira-ops.zip -DestinationPath . ; Move-Item jira-ops-main <skill-root> ; Remove-Item jira-ops.zip
```

```bash
# bash — download archive
curl -L https://github.com/mc1908/jira-ops/archive/refs/heads/main.tar.gz | \
  tar -xz && mv jira-ops-main <skill-root>
```

Or clone and then strip the nested `.git`:

```bash
git clone https://github.com/mc1908/jira-ops.git <skill-root>
Remove-Item -Recurse -Force <skill-root>\.git   # PowerShell
# rm -rf <skill-root>/.git                      # bash
```

For GitHub Copilot (project install), the skill root is `.agents/skills/jira-ops/`.
For a global install on Windows it is `%USERPROFILE%\.copilot\skills\jira-ops\`.
Once the full repo is in place, proceed with the setup below.

All behavior lives in Python scripts under `scripts/`. Prefer these scripts over
ad-hoc `curl`/REST calls so auth, pagination, retries, and secret redaction stay
consistent.

## Interpreter contract (read first)

After setup, a skill-local virtual environment exists at `<skill-root>/.venv/`.
The entrypoint `scripts/jira.py` **auto re-execs into that venv**, so always call:

```
python scripts/jira.py <command> [options]
```

Run every command from the **skill root** (the folder containing this
`SKILL.md`, e.g. `C:\...\jira-ops>`). The `scripts/` path is relative to it — do
**not** `cd` into `scripts/`. Commands are otherwise working-directory
independent (config, venv, and token resolve by absolute path), so an absolute
path like `python <skill-root>/scripts/jira.py ...` also works from anywhere.

Do not call the other `scripts/*.py` modules directly; go through `jira.py`.
Add `--json` to any command for machine-readable output.

## First-time setup

If a command reports missing config or dependencies, run setup once. The guided
flow collects the base URL, profile name, **default project**, optional CA/proxy,
and the PAT in a single session:

```
python scripts/bootstrap.py                               # venv + deps, then guided setup
python scripts/bootstrap.py -i                            # re-run guided setup any time
```

Non-interactive equivalent:

```
python scripts/jira.py setup --base-url "https://JIRA_HOST" --name default \
  --default-project ABC                                   # default project (optional)
python scripts/jira.py auth set-token --token-stdin       # PAT via stdin (not argv)
python scripts/jira.py auth test-auth                     # validates GET /myself
```

- Set a **default project** so `sprint`, `backlog`, and `search` work without
  `--project`. Override per call with `--project OTHER`.
- The PAT is stored in the OS secret store if available, else a DPAPI-encrypted
  file (Windows) / `0600` file (POSIX) under the platform config dir — never in
  the repo, never echoed.
- **Update / rotate the PAT** any time by re-running `auth set-token` (it
  overwrites the old one and re-validates). Remove it with `auth clear-token`.
  `JIRA_OPS_TOKEN` in the environment overrides the stored token when set.
- For a corporate CA, pass `--ca-cert "C:\path\ca-bundle.pem"`. Behind a proxy,
  pass `--proxy`. Never disable TLS as a shortcut.
- **Before first commit**, confirm `.venv/` is in the repo's `.gitignore`.
  The bootstrap creates a local virtual environment that must never be committed.
  If the workspace `.gitignore` does not already contain `.venv/`, add it:
  ```
  echo '.venv/' >> .gitignore
  ```

## Quick reference

| Intent | Command |
|--------|---------|
| Who am I | `python scripts/jira.py auth whoami` |
| Set / update PAT | `python scripts/jira.py auth set-token` (re-run to rotate) |
| Remove PAT | `python scripts/jira.py auth clear-token` |
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
| Boards | `python scripts/jira.py boards --project ABC` |
| Sprints | `python scripts/jira.py sprints --project ABC --state active` |
| Active sprint status | `python scripts/jira.py sprint --project ABC` |
| Sprint issue list | `python scripts/jira.py sprint --project ABC --issues` |
| Backlog (plan next) | `python scripts/jira.py backlog --project ABC` |
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

## Sprint planning

Sprint/board data uses Jira's **Agile REST API** (`/rest/agile/1.0`), so these
commands need a **scrum board** to exist for the project.

- *"How many active issues in the active sprint for project ABC?"*
  `python scripts/jira.py sprint --project ABC` prints the active sprint, total
  issue count, and a per-status breakdown. Add `--issues` for the full list.
- *"Plan the next sprint from the backlog."* Read candidates with
  `python scripts/jira.py backlog --project ABC`, and inspect the upcoming
  sprint with `python scripts/jira.py sprints --project ABC --state future`.
- If a project has several boards, resolve the id with `boards --project ABC`
  and pass `--board ID` explicitly.

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
