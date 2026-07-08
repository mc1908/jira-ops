# SOP: Daily standup / status summary

**Goal:** Compose a concise, personal standup update from live Jira data. This is
a **composition** task, not a scripted command — the agent orchestrates the data
commands below, then writes the narrative in prose. Adapt to the user's phrasing,
scope, and level of detail; do not emit a rigid template blindly.

## 1. Clarify scope (only if unclear)

Infer from the request when possible; ask only when genuinely ambiguous:

- **Window** — "since yesterday" (default), since Friday, this sprint, etc.
- **Project / board** — the default project unless the user names another.
- **Destination** — just show the summary (default), or also post it somewhere
  (e.g. a comment on a ticket) if the user asks.

## 2. Gather data (read-only)

Run only what you need; prefer `--json` so you can parse reliably.

| Signal | Command |
|--------|---------|
| Recently moved (proxy for "yesterday") | `python scripts/jira.py mine --preset recently-updated-by-me --json` |
| Currently in progress ("today") | `python scripts/jira.py mine --preset my-in-progress --json` |
| Blocked items | `python scripts/jira.py mine --preset my-blocked --json` |
| Queue / next up | `python scripts/jira.py mine --preset my-open --json` |
| What changed on a specific issue | `python scripts/jira.py history KEY --json` |
| Time logged (if the team tracks it) | `python scripts/jira.py worklog KEY --json` |
| Sprint context (goal, dates, burn) | `python scripts/jira.py sprint --project ABC --json` |

Use `history` / `worklog` selectively to confirm *what* actually changed on the
key tickets, rather than guessing from status alone.

## 3. Compose the summary

Default structure (adapt freely to the user's style):

- **Yesterday / Since last update** — what progressed; cite issue keys and the
  concrete change (moved to In Review, PR merged, tests green).
- **Today / Next** — what you're picking up now (in-progress first, then queue).
- **Blockers** — blocked items with the reason and what's needed to unblock.

Guidelines:

- Keep it to a few tight bullets; a standup is skimmable, not a changelog.
- Always reference issue keys (e.g. `ABC-123`) so teammates can click through.
- Group by theme/epic if there are many items; omit noise.
- State facts from the data; do not invent progress that isn't in Jira.

## 4. Deliver (and optionally post)

- Present the summary to the user for review.
- If they want it recorded on a ticket, use `comment` with an appropriate
  template (e.g. `--template implementation-update` or `handoff`) and **always
  `--dry-run` first**, then send on confirmation. See the "Drafting status
  updates" section in `SKILL.md`.

## Example (shape, not a fixed template)

```
Standup — 2026-07-08
Yesterday:
  - ABC-123 moved to In Review (retry + pagination wired, tests green).
  - ABC-130 closed (flaky test fixed).
Today:
  - ABC-140 (In Progress): finish the client backoff.
  - Pick up ABC-145 next.
Blockers:
  - ABC-138 blocked on staging access (need infra to grant it).
```
