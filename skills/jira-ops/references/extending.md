# Extending the skill on demand

The skill covers a fixed menu of operations. When you hit a genuine capability
gap that the Jira REST API supports, **grow the skill through its own modules and
shared client** — do not reach around it with a throwaway script that duplicates
auth, TLS, pagination, and error handling.

## Decision rule: extend vs. work around

1. **Is it a Jira REST operation the current commands don't expose?**
   If yes and it will be needed more than once, add/extend a command rather than
   writing a one-off script.
2. **Does an existing sub-script own this resource?** Extend that module:
   - Issue-level reads/writes → `jira_issue.py`
   - Transitions → `jira_transition.py`
   - Boards / sprints / backlog → `jira_sprint.py`
   - Projects → `jira_project.py`
   - Auth / setup → `jira_auth.py`

   Only create a new `jira_<area>.py` when a genuinely new resource area appears,
   and register it in the `_COMMANDS` map in `jira.py`.
3. **Never bypass the shared client.** All HTTP must go through `JiraClient`
   (`get_json` / `post_json` / `put_json`, or a typed helper like
   `update_issue`) so auth, retries, pagination, TLS/proxy, secret redaction, and
   error mapping stay consistent. If the client can't express the call, **improve
   the client** — do not open a raw `requests.Session`.

## Keep `JiraClient` as the single extension point

Most capability gaps are really *client* gaps. Prefer adding small, well-named
helpers to `JiraClient` (e.g. `update_issue(key, fields=...)`) that the
sub-scripts call, rather than embedding raw request logic in commands. This keeps
HTTP concerns in one place and makes new commands thin and consistent.

`put_json` normalizes an empty/`204 No Content` body to `{"ok": True}` *after* the
`>=400` error mapping in `request()` — so reaching the return means the write
succeeded. Reuse it for any PUT-based edit.

## Non-negotiable invariants every new command must honor

- **Fetch-before-write:** re-read current state before any mutation.
- **`--dry-run`** on every write command, printing the exact payload.
- **`guard_no_secret_leak()`** over any user-provided string that gets sent.
- **`--json`** machine-readable output with a stable `{"ok", "action", ...}` shape.
- **Documented exit codes** — reuse the category → exit-code map (`10` config,
  `11` auth, `12` authorization, … `20` server; see `SKILL.md`).
- **Data Center specifics:** `username` (not `accountId`); wiki markup / plain
  text bodies (not ADF); relative `/rest/api/2` paths resolved by the client's
  base URL.
- **No secrets in argv;** tokens via stdin / prompt / env only.

## Definition of done for any extension

- New command appears in `jira.py --help` and the `SKILL.md` Quick Reference.
- `--dry-run` and `--json` both work and are shown in `references/examples.md`.
- The command routes through `JiraClient`; no new direct `requests` usage.
- Error and `204`/empty-body paths behave (empty body → `{"ok": True}`).

## Worked example: the `update` command

`update` (in `jira_issue.py`) is the reference implementation of this guideline:

- Named flags for common fields (`--summary`, `--description`, `--priority`,
  `--assignee`, `--label`, `--due`) plus a generic escape hatch (`--field
  key=value`, `--field-json '{...}'`) for the long tail.
- Builds a `fields` object for direct sets and an `update` object for label
  add/remove verbs (`--label x` adds, `--label -x` removes).
- Runs `guard_no_secret_leak()` over every string value, re-reads the issue,
  supports `--dry-run`, and calls `JiraClient.update_issue()` — no raw HTTP.

## Commands vs. SOPs: pick the right extension type

Not every capability should be a script. Decide by the nature of the work:

- **Deterministic API operation** (one request, predictable payload, e.g.
  `create`, `assign`, `attach`) → add a **command** (this document's main path).
- **Multi-step, judgment-driven workflow** that composes several commands and
  produces prose or decisions from dynamic context (e.g. a daily standup, a
  release-notes draft, a triage pass) → write an **SOP**, not a script.
  Scripting synthesis work is brittle: it freezes the format, can't adapt to the
  user's phrasing or scope, and duplicates data commands the skill already has.
  Let the deterministic commands own the *data* and let the agent own the
  *composition*, guided by the SOP.

### How to add an SOP

- Put each SOP in its own file under `references/sop/<name>.md` (one procedure
  per file) so the surface stays organized and extensible.
- Keep `SKILL.md` lean: add a single row to the **Standard procedures (SOPs)**
  table pointing at the file — do **not** inline the procedure. This preserves
  **progressive disclosure** (the agent loads a full SOP only when the task
  calls for it).
- Structure an SOP as: goal → clarify scope → gather data (which read-only
  commands to run) → compose → deliver (and any optional write, always with
  `--dry-run` first). Emphasize that it is guidance to adapt, not a fixed
  template to emit verbatim.
- Reuse existing commands inside the SOP; if the SOP reveals a genuine
  *deterministic* gap, add that piece as a command per the rules above.

## Deliberate non-goal: issue deletion

Issue deletion (`DELETE /issue/{key}`) is intentionally **not** implemented and
should stay out of scope. It is irreversible and cascades to sub-tasks, so it
breaks the skill's reversible, previewable write model (`--dry-run` cannot make a
hard delete safe), and it is rare admin work rather than day-to-day developer flow
(see Non-Goals in `docs/DESIGN.md`). Prefer safer alternatives: close/resolve via
`transition`, or mark obsolete with an `update` label. If a genuine repeated need
ever appears, gate it far harder than a normal write — interactive typed-key
confirmation (no `--force`/`--yes` bypass), a distinct exit-code category, and an
explicit note here that it is an admin escape hatch, not a routine command.

