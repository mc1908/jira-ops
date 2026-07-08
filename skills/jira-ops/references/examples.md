# JQL & workflow examples

## Presets (in `scripts/jira_common/presets.py`)

| Preset | JQL |
|--------|-----|
| `my-open` | `assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC, updated DESC` |
| `my-in-progress` | `assignee = currentUser() AND status = "In Progress" ORDER BY updated DESC` |
| `my-stale` | `assignee = currentUser() AND resolution = Unresolved AND updated < -5d ORDER BY updated ASC` |
| `my-blocked` | `assignee = currentUser() AND resolution = Unresolved AND (labels = blocked OR status = Blocked)` |
| `recently-updated-by-me` | `assignee = currentUser() AND updated >= -7d ORDER BY updated DESC` |
| `reported-by-me-open` | `reporter = currentUser() AND resolution = Unresolved ORDER BY created DESC` |

Field and status names vary per instance. If a preset returns an
`invalid_jql` error, adjust the status/label names to match your workflow (e.g.
`"In Review"`, `"Code Review"`, `Blocked`) and edit `presets.py`.

## Handy raw queries

```
# Open items in a project
python scripts/jira.py search --jql "project = ABC AND resolution = Unresolved ORDER BY priority DESC"

# Release scope
python scripts/jira.py search --jql 'fixVersion = "2025.10" AND resolution = Unresolved'

# Recently changed across a project
python scripts/jira.py search --jql "project = ABC AND updated >= -3d ORDER BY updated DESC"
```

## Transition workflow

```
python scripts/jira.py transitions ABC-123          # see valid moves + ids
python scripts/jira.py transition ABC-123 --to "In Review" --dry-run
python scripts/jira.py transition ABC-123 --to "In Review" --comment "PR merged"
```

Match `--to` against either the transition name or the destination status name
(case-insensitive). Use `--id` when names are ambiguous.

## Comment templates

```
python scripts/jira.py comment ABC-123 --template test-result \
  --summary "Ran regression suite" --test "pytest -q" \
  --result "142 passed, 0 failed" --next-step "await review" --dry-run
```

Templates render Jira wiki markup: `implementation-update`, `test-result`,
`blocked`, `handoff`.

## Editing fields

```
# Set common fields (preview first)
python scripts/jira.py update ABC-123 --summary "New title" \
  --description "Rewritten body." --priority High --assignee jsmith --dry-run

# Add and remove labels in one call ('-' prefix removes)
python scripts/jira.py update ABC-123 --label backend --label -stale

# Set a due date
python scripts/jira.py update ABC-123 --due 2026-08-01

# Escape hatch for fields without a flag
python scripts/jira.py update ABC-123 --field customfield_10021="Team A"
python scripts/jira.py update ABC-123 --field-json '{"fixVersions":[{"name":"1.2"}]}'
```

Data Center specifics: `--assignee` takes a `username` (not a Cloud `accountId`),
and `--description` is wiki markup / plain text (not ADF). `update` re-reads the
issue first, runs the secret-leak guard over string values, and returns
`{"ok": true, "action": "update", "issue": KEY, "fields": [...], "url": ...}` with
`--json`. To add a *new* command like this, see `references/extending.md`.
