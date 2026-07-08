# jira-ops Improvement Feedback

**Source:** Dev with AI · Session 16 demo preparation
**Date:** 2026-07-08
**Trigger:** Seeding a demo issue (`FASTACTR67-578`) required editing the `summary`
and `description` fields. The skill has no command for that, so a throwaway script
(`scripts/seed_demo_issue.py`) had to bypass the skill's own client helpers and
issue a raw `PUT /rest/api/2/issue/{key}` with a hand-built `requests.Session`.

This document captures two concrete improvements so the next person does not have
to reach around the skill to do a routine, API-supported operation.

---

## Observations From The Workaround

What went wrong / was awkward, in order:

1. **No field-update command.** `jira.py` exposes `comment` and `transition` as the
   only write paths. Editing `summary`, `description`, `labels`, `priority`,
   `assignee`, or any other field is simply not reachable through the skill.
2. **`put_json` raised on a successful `204`.** `PUT /issue/{key}` returns
   `204 No Content` on success, but the client's `request()` treated the response
   as an error before `put_json` could normalize it. The raw `requests` call
   confirmed the write actually succeeded (HTTP 204) — the helper just could not
   report it. (Root cause worth checking: error mapping runs before the 204/empty
   handling in `put_json`.)
3. **Path-shape inconsistency.** Internally the skill calls `client.get_json("issue/KEY", ...)`
   (relative to `/rest/api/2`), but the workaround used the absolute
   `/rest/api/2/issue/KEY`. A GET with an absolute path plus `fields` params failed
   through the client, so verification also had to use a raw session. The base-path
   convention is not obvious to a caller and is easy to get wrong.

Net effect: a one-line, fully API-supported edit turned into a ~60-line bespoke
script that duplicated auth, TLS, and session handling the skill already owns.

---

## Improvement 1 — Add A Flexible Field-Update Command

Add a first-class `update` (a.k.a. `edit`) command that can set arbitrary editable
fields on an issue, with the same safety model as `comment` and `transition`.

### Proposed CLI

```
python scripts/jira.py update <ISSUE-KEY> [field options] [--dry-run]
```

Common fields as named flags (ergonomic, discoverable):

| Flag | Field | Notes |
|------|-------|-------|
| `--summary "text"` | `summary` | Title |
| `--description "text"` | `description` | Wiki markup / plain text (Data Center, not ADF) |
| `--priority "High"` | `priority` | By name |
| `--assignee username` | `assignee` | Data Center uses `username`, not `accountId` |
| `--label LABEL` (repeatable) | `labels` | `--label a --label b`; support `--label -old` to remove |
| `--due 2026-08-01` | `duedate` | ISO date |

Plus a generic escape hatch for anything not covered by a flag:

```
--field "customfield_10021=Team A"        # simple set
--field-json '{"fixVersions":[{"name":"1.2"}]}'   # raw JSON merged into fields
```

### Required behavior (mirror existing safety rules)

- **Fetch current state first.** Re-read the issue before writing (already the
  documented rule for every write command).
- **`--dry-run` prints the exact `fields` payload** that would be sent, without
  writing — same UX as `comment --dry-run`.
- **Confirm before write.** No silent writes; require explicit intent.
- **`guard_no_secret_leak()`** must run over all string field values (summary,
  description, comment-like fields) before sending, exactly as `comment` does.
- **Handle `204 No Content` as success** — do not raise. Fix `put_json` so an
  empty/`204` body is normalized to `{"ok": True}` *before* error mapping, and add
  a regression test for the 204 path.
- **Emit** a consistent result object: `{"ok": true, "action": "update", "issue": KEY,
  "fields": [changed field names], "url": browse_url}` for `--json` callers.

### Suggested placement

Route `update` to `jira_issue.py` (next to `comment`) in the `_COMMANDS` map in
`scripts/jira.py`, and add the row to the Quick Reference table in `SKILL.md`:

```
| Update fields | python scripts/jira.py update ABC-123 --summary "..." --description "..." (--dry-run) |
```

With this in place, seeding the demo issue would have been a single supported call:

```
python scripts/jira.py update FASTACTR67-578 \
  --summary "[DEMO SEED] jira-ops live demo — safe write target (do not delete)" \
  --description "This issue is a seeded test fixture ..." --dry-run
```

---

## Improvement 2 — A Guideline For Extending The Skill On Demand

The deeper issue is structural: the skill covers a fixed menu of operations, and
anything outside that menu — even when the Jira REST API fully supports it — forces
a caller to bypass the skill. The skill should be able to **grow its own surface
area** in a controlled, consistent way when a genuine need appears, instead of
accreting one-off scripts.

Add a short contributor-facing guideline (e.g. `references/extending.md`, linked
from the "When to load references" table in `SKILL.md`) that codifies the following.

### Decision rule: when to extend vs. work around

1. **Is it a Jira REST operation the current commands don't expose?**
   If yes and it will be needed more than once, **add/extend a command** rather
   than writing a throwaway script.
2. **Does an existing sub-script own this resource?** Extend that module:
   - Issue-level reads/writes → `jira_issue.py`
   - Transitions → `jira_transition.py`
   - Boards / sprints / backlog → `jira_sprint.py`
   - Projects → `jira_project.py`
   - Auth / setup → `jira_auth.py`
   Only create a new `jira_<area>.py` when a genuinely new resource area appears,
   and register it in the `_COMMANDS` map in `jira.py`.
3. **Never bypass the shared client.** All HTTP must go through `JiraClient`
   (`get_json` / `post_json` / `put_json`) so auth, retries, pagination, TLS/proxy,
   secret redaction, and error mapping stay consistent. If the client can't express
   the call, **improve the client** — do not open a raw `requests.Session`.

### Non-negotiable invariants every new command must honor

- **Fetch-before-write:** re-read current state before any mutation.
- **`--dry-run`** on every write command, printing the exact payload.
- **`guard_no_secret_leak()`** over any user-provided string that gets sent.
- **`--json`** machine-readable output with a stable `{"ok", "action", ...}` shape.
- **Documented exit codes** — reuse the existing category → exit-code map
  (`10` config, `11` auth, `12` authorization, … `20` server).
- **Data Center specifics:** `username` (not `accountId`); wiki markup / plain text
  bodies (not ADF); relative `/rest/api/2` paths via the client's base URL.
- **No secrets in argv;** tokens via stdin/prompt/env only.

### Keep the client as the single extension point

Most capability gaps are really *client* gaps. Prefer adding small, well-named
helpers to `JiraClient` (e.g. `update_issue(key, fields)`, `add_label(key, label)`)
that the sub-scripts call, rather than embedding raw request logic in commands.
This keeps HTTP concerns in one place and makes new commands thin and consistent.

### Definition of done for any extension

- New command appears in `jira.py --help` and the `SKILL.md` Quick Reference.
- `--dry-run` and `--json` both work and are shown in `references/examples.md`.
- Error and `204`/empty-body paths are covered by a test.
- No new direct `requests` usage outside `JiraClient`.

### Why this matters

Following this rule turns "the skill can't do X, so I wrote a script around it"
into "the skill learned X, safely, and everyone gets it next time." The skill grows
**logically** (each resource area owns its module), **flexibly** (generic
`--field` / client helpers cover the long tail), and **maintainably** (one client,
one safety model, one set of invariants).

---

## Summary

| # | Ask | Outcome |
|---|-----|---------|
| 1 | Add a flexible `update` command for field edits (incl. summary/description and a generic `--field` escape hatch), and fix `put_json` to treat `204` as success | Routine field edits become a single safe, previewable, supported call |
| 2 | Publish an extension guideline so the skill grows through its own modules + shared client instead of one-off workarounds | Capability expands on demand while staying consistent, safe, and maintainable |
