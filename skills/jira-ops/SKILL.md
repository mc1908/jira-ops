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
python <skill-root>/scripts/jira.py <command> [options]
```

**Determine `<skill-root>` from the location of this `SKILL.md` file** — it is
the directory that contains `SKILL.md`. Never assume a relative `scripts/` path
from the current working directory; always use the absolute path to
`scripts/jira.py`. Common locations:

| Install method | Typical `<skill-root>` |
|---|---|
| `npx skills add` (project install) | `<project-root>/.agents/skills/jira-ops` |
| `npx skills add -g` (global) | `~/.agents/skills/jira-ops` |
| Manual / dev repo | path where `SKILL.md` lives |

Config, venv, and token all resolve by absolute path — cwd never matters.

Do not call the other `scripts/*.py` modules directly; go through `jira.py`.
Add `--json` to any command for machine-readable output.

## First-time setup

If a command reports missing config or dependencies, run setup once. The guided
flow collects the base URL, profile name, **default project**, optional CA/proxy,
and the PAT in a single session:

```
python <skill-root>/scripts/bootstrap.py                  # venv + deps, then guided setup
python <skill-root>/scripts/bootstrap.py -i               # re-run guided setup any time
```

Non-interactive equivalent:

```
python <skill-root>/scripts/jira.py setup --base-url "https://JIRA_HOST" --name default \
  --default-project ABC                                   # default project (optional)
python <skill-root>/scripts/jira.py auth set-token --token-stdin  # PAT via stdin (not argv)
python <skill-root>/scripts/jira.py auth test-auth                # validates GET /myself
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

> In the table below `python scripts/jira.py` is shorthand for
> `python <skill-root>/scripts/jira.py` — substitute the actual absolute path
> to the skill root as described in the interpreter contract above.

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
| Saved filters | `python scripts/jira.py filters` / `filter 10123` |
| View a ticket | `python scripts/jira.py view ABC-123` |
| Read comments | `python scripts/jira.py comments ABC-123` |
| Change history | `python scripts/jira.py history ABC-123` |
| List transitions | `python scripts/jira.py transitions ABC-123` |
| Transition | `python scripts/jira.py transition ABC-123 --to "In Review"` |
| Comment | `python scripts/jira.py comment ABC-123 --body "text"` |
| Update fields | `python scripts/jira.py update ABC-123 --summary "..." --description "..."` |
| Create issue | `python scripts/jira.py create --project ABC --type Task --summary "..."` |
| Assign / unassign | `python scripts/jira.py assign ABC-123 --to jsmith` (`--to -` clears) |
| Link issues | `python scripts/jira.py link ABC-123 --to ABC-124 --type "Blocks"` |
| Link types | `python scripts/jira.py link-types` |
| Attach file | `python scripts/jira.py attach ABC-123 --file .\log.txt` |
| Log work | `python scripts/jira.py worklog ABC-123 --time "1h 30m"` |
| List worklogs | `python scripts/jira.py worklog ABC-123` |
| Find a user | `python scripts/jira.py users --query smith` |
| Projects | `python scripts/jira.py projects` |
| Boards | `python scripts/jira.py boards --project ABC` |
| Sprints | `python scripts/jira.py sprints --project ABC --state active` |
| Active sprint status | `python scripts/jira.py sprint --project ABC` |
| Sprint issue list | `python scripts/jira.py sprint --project ABC --issues` |
| Add issue to sprint | `python scripts/jira.py sprint-add --id 42 --issue ABC-123` |
| Backlog (plan next) | `python scripts/jira.py backlog --project ABC` |
| Local health | `python scripts/jira.py health` |

Presets: `my-open`, `my-in-progress`, `my-stale`, `my-blocked`,
`recently-updated-by-me`, `reported-by-me-open`.

## Safety rules (always)

- **Fetch current state first.** Every write command re-reads the issue before acting.
- **Preview writes.** `comment`, `transition`, `update`, `create`, `assign`,
  `link`, `attach`, `worklog`, and `sprint-add` accept `--dry-run` to show the
  exact payload. Use it before real writes unless the user clearly asked to send.
- **Transitions are runtime data.** Never assume names; run `transitions KEY` first.
  Transition by `--to "Status/Transition name"` or `--id`.
- **Confirm before write.** Get user approval before any write command
  (`comment` / `transition` / `update` / `create` / `assign` / `link` / `attach` /
  `worklog` / `sprint-add`).
- **Resolve names, don't guess.** Use `users --query` for exact assignee
  usernames and `link-types` for valid link names before an `assign`/`link`.
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

For multi-step, judgment-driven workflows (e.g. composing a daily standup), follow
the matching **SOP** instead of a single command — see *Standard procedures* below.

## Editing issue fields

Use `update` to set editable fields with the same safety model as `comment` /
`transition` (fetch-before-write, `--dry-run`, secret-leak guard, `--json`):

```
python scripts/jira.py update ABC-123 --summary "New title" \
  --description "Rewritten body (wiki markup)." --priority High \
  --assignee jsmith --label backend --label -stale --due 2026-08-01 --dry-run
```

Named flags: `--summary`, `--description`, `--priority`, `--assignee` (username),
`--label` (repeatable; prefix `-` to remove), `--due`. For anything without a
flag, use the escape hatch: `--field customfield_10021=Team A` (repeatable) or
`--field-json '{"fixVersions":[{"name":"1.2"}]}'` (merged into the payload).

## Creating issues

Use `create` to open a new issue. `--project` (falls back to the default
project), `--type`, and `--summary` are the core inputs; the same
optional/escape-hatch flags as `update` apply:

```
python scripts/jira.py create --project ABC --type Bug \
  --summary "Login retry loops on 500" \
  --description "Steps: ..." --priority High --assignee jsmith \
  --label backend --dry-run
```

- **Choose the issue type deliberately.** There is no default — infer `--type`
  from the request (a defect report → `Bug`, a user-facing feature → `Story`, a
  test case → `Test`, general work → `Task`). If the type is ambiguous, ask the
  user rather than guessing. Valid types vary per project; `projects --key ABC
  --createmeta` lists them.
- Preview with `--dry-run` before the real write; confirm with the user first.
- If creation fails validation, run `projects --key ABC --createmeta` to see the
  required fields and valid issue types for that project.
- Data Center specifics apply: `--assignee` is a `username`, descriptions are
  wiki markup / plain text (not ADF).

## Reading comments, assigning, linking

```
python scripts/jira.py comments ABC-123                     # read the discussion thread
python scripts/jira.py users --query smith                  # find an exact username
python scripts/jira.py assign ABC-123 --to jsmith           # reassign (--to - to clear)
python scripts/jira.py link-types                           # list valid link names
python scripts/jira.py link ABC-123 --to ABC-124 --type "Blocks" --dry-run
```

- `view` shows the description; use `comments KEY` to read the full comment
  thread (author, timestamp, body).
- `assign`/`link` are writes with `--dry-run`. `link KEY --to OTHER --type T`
  reads as *KEY <type.outward> OTHER* (e.g. with `Blocks`, KEY blocks OTHER).
- Look up exact usernames with `users --query` and valid link names with
  `link-types` rather than guessing.

### Attachments

```
python scripts/jira.py attach ABC-123 --file .\build.log --file .\screenshot.png --dry-run
```

- Repeat `--file` to upload several files in one call; `--dry-run` lists the
  names and sizes without uploading. Paths are validated locally first.
- Uploads go through multipart form-data with the required
  `X-Atlassian-Token: no-check` header (handled by the client).

## History, worklogs, and saved filters

```
python scripts/jira.py history ABC-123                 # who changed what, when
python scripts/jira.py worklog ABC-123                 # list logged work
python scripts/jira.py worklog ABC-123 --time "1h 30m" --comment "debugging" --dry-run
python scripts/jira.py filters                         # your favourite saved filters
python scripts/jira.py filter 10123                    # run a saved filter's JQL
```

- `history KEY` reads the changelog (field-level from -> to per event); `--limit`
  keeps the most recent N events.
- `worklog KEY` **lists** entries; adding `--time "1h 30m"` **logs** work (a
  write, so it supports `--dry-run`). `--started` accepts an ISO timestamp.
- `filters` lists favourites; `filter ID` fetches the saved filter and runs its
  JQL like `search`.

## Sprint planning

Sprint/board data uses Jira's **Agile REST API** (`/rest/agile/1.0`), so these
commands need a **scrum board** to exist for the project.

- *"How many active issues in the active sprint for project ABC?"*
  `python scripts/jira.py sprint --project ABC` prints the active sprint, total
  issue count, and a per-status breakdown. Add `--issues` for the full list.
- *"Plan the next sprint from the backlog."* Read candidates with
  `python scripts/jira.py backlog --project ABC`, and inspect the upcoming
  sprint with `python scripts/jira.py sprints --project ABC --state future`.
- *"Pull an item into the sprint."* Resolve the sprint id with `sprints`, then
  `python scripts/jira.py sprint-add --id 42 --issue ABC-123 --dry-run`.
- If a project has several boards, resolve the id with `boards --project ABC`
  and pass `--board ID` explicitly.

## When to load references

| Task | Reference |
|------|-----------|
| Non-trivial JQL, preset tuning | `references/examples.md` |
| Endpoints, createmeta, field IDs | `references/endpoints.md` |
| Auth backends, TLS/proxy, secrets | `references/security.md` |
| Install / troubleshooting setup | `references/setup.md` |
| Adding a new command / capability | `references/extending.md` |

## Standard procedures (SOPs)

Multi-step, judgment-driven workflows are documented as SOPs under
`references/sop/` (kept out of this file for progressive disclosure). Load the
matching SOP and follow it, orchestrating the commands above.

| When the user asks for... | SOP |
|---------------------------|-----|
| A daily standup / status summary | `references/sop/standup.md` |

## Exit codes (for `--json` callers)

`0` ok · `10` config · `11` auth · `12` authorization · `13` network · `14` tls ·
`15` not-found · `16` invalid-jql · `17` transition-not-found · `18` validation ·
`19` rate-limited · `20` server.
