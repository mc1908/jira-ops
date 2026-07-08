# jira-ops Feature Gap Analysis

**Date:** 2026-07-08
**Question:** Given what the skill offers today versus what the Jira Data Center
REST API can do, which gaps are worth building **now** (so users don't have to
reach around the skill) versus leaving for on-demand extension or ruling out?

This is a decision document. It maps the current command surface against the
Jira DC REST surface (`/rest/api/2` + `/rest/agile/1.0`), then classifies each
gap as **Build now**, **Later (extend on demand)**, or **Out of scope**, with
value / effort / risk and the reasoning. Implementation should follow the
invariants in [`references/extending.md`](../skills/jira-ops/references/extending.md).

---

## 1. What the skill offers today

| Area | Commands |
|------|----------|
| Auth / setup | `setup`, `auth set-token` / `test-auth` / `whoami` / `clear-token` / `reset`, `health` |
| Read issues | `search` (JQL / preset / project), `mine` (presets), `view` (single issue detail) |
| Write issues | `comment` (+ 4 templates), `update` (fields + label add/remove + `--field`/`--field-json`), `create` |
| Workflow | `transitions` (list), `transition` (by name/id, optional comment) |
| Projects | `projects` (list, metadata, `--createmeta`) |
| Agile (read-only) | `boards`, `sprints`, `sprint` (breakdown), `backlog` |

**Cross-cutting foundations already in place:** shared `JiraClient`
(`get_json`/`post_json`/`put_json`, pagination, retries, TLS/proxy, error
mapping, `guard_no_secret_leak`), `--dry-run` on writes, `--json` everywhere,
stable exit-code categories, Data Center specifics (`username`, wiki markup).

---

## 2. API capability map & gaps

Legend — **Value**: how often a developer/agent needs it in day-to-day flow.
**Effort**: implementation size against current patterns. **Risk**: blast radius
/ safety concern.

### Issue lifecycle

| Capability | REST | Status | Value | Effort | Risk |
|-----------|------|--------|-------|--------|------|
| Read comments on an issue | `GET /issue/{key}/comment` (or `view?expand`) | **Gap** | High | S | None (read) |
| Add comment | `POST /issue/{key}/comment` | Covered (`comment`) | — | — | — |
| Edit / delete a comment | `PUT`/`DELETE /issue/{key}/comment/{id}` | Gap | Low | S | Med (mutating others' words) |
| Set/clear fields | `PUT /issue/{key}` | Covered (`update`) | — | — | — |
| Assign / unassign | `PUT /issue/{key}/assignee` | Partial (via `update --assignee`) | Med | S | Low |
| Link issues (blocks/relates/dupes) | `POST /issueLink`, `GET /issueLinkType` | **Gap** | High | S–M | Low |
| Create sub-task | `POST /issue` with `parent` | Partial (via `create --field parent=...`) | Med | S | Low |
| Log work / time tracking | `POST /issue/{key}/worklog` | Gap | Med | M | Low |
| Attach a file | `POST /issue/{key}/attachments` (multipart) | **Gap** | Med–High | M | Low |
| Watch / unwatch | `POST`/`DELETE /issue/{key}/watchers` | Gap | Low | S | Low |
| Issue history / changelog | `GET /issue/{key}?expand=changelog` | Gap | Med | S | None (read) |
| Editable-field discovery | `GET /issue/{key}/editmeta` | Gap | Low–Med | S | None (read) |
| Delete issue | `DELETE /issue/{key}` | **Out of scope** (documented) | — | — | High |

### Search & metadata resolution

| Capability | REST | Status | Value | Effort | Risk |
|-----------|------|--------|-------|--------|------|
| Resolve users (assignee lookup) | `GET /user/search?username=` | **Gap** | Med–High | S | None |
| Resolve field / status / priority / type IDs | `GET /field`, `/status`, `/priority`, `/issuetype` | Gap | Med | S | None |
| Run a saved filter | `GET /filter/{id}` then search | Gap | Low–Med | S | None |
| Bulk transition / edit | loop or `POST /bulk` | Later | Med | L | Med |

### Agile (currently read-only)

| Capability | REST | Status | Value | Effort | Risk |
|-----------|------|--------|-------|--------|------|
| Move issue(s) into a sprint | `POST /sprint/{id}/issue` | **Gap** | High (scrum) | S | Low |
| Move issue(s) to backlog | `POST /backlog/issue` | Gap | Med | S | Low |
| Create / start / close a sprint | `POST /sprint`, `POST /sprint/{id}` | Later | Med | M | Med |
| Rank / reorder backlog | `PUT /issue/rank` | Later | Low | M | Med |
| Epics: list, add issues to epic | `GET /epic/...`, `POST /epic/{key}/issue` | Later | Med | M | Low |

### Project / release management

| Capability | REST | Status | Value | Effort | Risk |
|-----------|------|--------|-------|--------|------|
| List versions / components | `GET /project/{key}/versions` / `/components` | Gap | Med | S | None |
| Create / release a version | `POST /version`, `PUT /version/{id}` | Later | Low–Med | M | Med (release admin) |
| Manage components | `POST/PUT/DELETE /component` | Out of scope | Low | M | Med (admin) |

### Reporting

| Capability | REST | Status | Value | Effort | Risk |
|-----------|------|--------|-------|--------|------|
| Standup / work summary | compose from `mine` + changelog | Gap | Med | M | None |

---

## 3. Recommendation — build now

> **Status (2026-07-08): all five implemented.** Commands `comments`, `link` /
> `link-types`, `sprint-add`, `users`, and `assign` shipped with the standard
> safety model (client helpers, `--dry-run` on writes, `--json`).

These close **routine, in-scope, low-risk** loops the skill half-covers today.
Each is small against existing patterns and keeps the "day-to-day developer
workflow" focus from [`DESIGN.md`](DESIGN.md).

1. **Read comments** — `view --comments` (or a `comments KEY` command).
   *Why now:* you can add a comment but not read the thread; `view` shows the
   description only. This is the single most jarring asymmetry. Read-only, tiny,
   completes the comment loop.

2. **Link issues** — `link KEY --to OTHER --type "Blocks"` (+ `link-types` to
   list). *Why now:* dependency/duplicate linking is core triage work and has no
   workaround short of raw REST. Add a `link_issues` client helper; supports
   `--dry-run`.

3. **Move issues into a sprint** — `sprint-add --id N --issue KEY [--issue ...]`
   (agile `POST /sprint/{id}/issue`). *Why now:* sprint planning is read-only
   today; reading the backlog then being unable to pull an item into the sprint
   forces a bypass. First agile **write** — small, high value for scrum teams.

4. **User lookup** — `users --query name` (`GET /user/search`). *Why now:*
   `--assignee` needs an exact Data Center `username`; agents guessing usernames
   is a common failure. A lookup makes `create`/`update`/`assign` reliable.
   Read-only, small.

5. **Assign convenience** — `assign KEY --to username` / `--to -` to unassign.
   *Why now:* reassignment is frequent enough to deserve a first-class verb even
   though `update --assignee` exists; pairs naturally with user lookup. Thin
   wrapper, `--dry-run`.

**Suggested build order:** (1) read comments and (4) user lookup first (pure
reads, immediate ergonomic win), then (2) link, (3) sprint-add, (5) assign as
writes with the standard safety model.

---

## 4. Later — extend on demand

Legitimate but **less frequent, larger, or higher-risk**; the extension
guideline exists precisely so these can be added when a real need appears:

- **Worklog / time tracking** — valuable only for teams that log time; skip until asked.
- **Attachments** — genuinely useful (logs/screenshots) but needs a new
  multipart path in `JiraClient` (`X-Atlassian-Token: no-check`, no JSON body),
  so it is the first item that requires a **client change**, not just a command.
- **Changelog / issue history**, **editmeta**, **watchers**, **saved filters**,
  **versions/components listing** — small reads, but niche; add per demand.
- **Create/start/close sprints, backlog ranking, epics** — agile *management*
  (beyond moving issues), heavier and more workflow-specific.
- **Bulk transition/edit** — powerful but higher blast radius; needs careful
  confirmation UX before it belongs in the default surface.
- **Standup/summary command** — nice-to-have that the DESIGN goals mention; can
  be composed today from `mine` + templates, so defer a dedicated command.

---

## 5. Out of scope (deliberate non-goals)

- **Issue deletion** (`DELETE /issue`) — irreversible, cascades to sub-tasks,
  breaks the reversible/previewable write model; admin, not dev flow. Recorded in
  [`references/extending.md`](../skills/jira-ops/references/extending.md). Prefer
  close/resolve via `transition` or an "obsolete" label.
- **Component / project admin, workflow/scheme editing, user & permission
  admin** — the DESIGN Non-Goals explicitly exclude broad admin automation.
- **Cloud-specific features** (ADF bodies, `accountId`, `/rest/api/3`) — out by
  design; this skill targets Data Center only.

---

## 6. Invariants for anything built from this list

Every new command must honor the existing contract (see
[`references/extending.md`](../skills/jira-ops/references/extending.md)):

- Route all HTTP through `JiraClient`; prefer a small typed helper
  (`link_issues`, `add_to_sprint`, `search_users`) over inline requests.
- Fetch-before-write on mutations; `--dry-run` printing the exact payload.
- `guard_no_secret_leak()` over any user string sent to Jira.
- `--json` with a stable `{"ok","action",...}` shape; reuse the exit-code map.
- Data Center specifics: `username` (not `accountId`), wiki markup (not ADF),
  relative `/rest/api/2` paths (agile via `profile.agile_base`).
- Update the `SKILL.md` Quick Reference, `references/examples.md`, and the
  endpoints table when the command lands.

---

## 7. Summary

| Gap | Recommendation |
|-----|----------------|
| Read comments | **Build now** |
| Link issues (+ link types) | **Build now** |
| Move issues into a sprint | **Build now** |
| User lookup | **Build now** |
| Assign / unassign verb | **Build now** |
| Worklog, attachments, changelog, watchers, filters, versions/components, epics, sprint lifecycle, bulk, standup | Later (extend on demand) |
| Issue deletion, admin, Cloud features | Out of scope |

Building the five "now" items removes the most common reasons an agent would
otherwise bypass the skill, while keeping the surface focused, safe, and
consistent. Everything else is intentionally deferred to the extension path.
