# Endpoints & field metadata

Base: `<baseUrl>/rest/api/2`. Bearer auth with a PAT. All requests go through
`scripts/jira.py`, which handles auth, pagination, retries, and error mapping.

## Endpoints used

| Purpose | Method + path |
|---------|---------------|
| Identity | `GET /myself` |
| List projects | `GET /project` (paginated via `paginate`) |
| Project metadata | `GET /project/{keyOrId}` |
| Create metadata | `GET /issue/createmeta?projectKeys=KEY&expand=projects.issuetypes.fields` |
| View issue | `GET /issue/{key}?fields=...` |
| Search | `POST /search` `{jql,startAt,maxResults,fields}` |
| Add comment | `POST /issue/{key}/comment` `{body}` |
| List transitions | `GET /issue/{key}/transitions` |
| Do transition | `POST /issue/{key}/transitions` `{transition:{id}}` |
| Create issue | `POST /issue` `{fields:{...}}` (Phase 2) |
| Edit fields | `PUT /issue/{key}` `{fields:{...}}` (Phase 2) |

## Agile endpoints (sprints/boards)

Base: `<baseUrl>/rest/agile/1.0` (separate from `/rest/api/2`). Requires a board
to exist; scrum boards are needed for sprints/backlog.

| Purpose | Method + path |
|---------|---------------|
| List boards | `GET /board?projectKeyOrId=KEY&type=scrum` (paginated, key `values`) |
| Board sprints | `GET /board/{boardId}/sprint?state=active|future|closed` (key `values`) |
| Sprint details | `GET /sprint/{sprintId}` |
| Sprint issues | `GET /sprint/{sprintId}/issue?fields=...` (key `issues`) |
| Board backlog | `GET /board/{boardId}/backlog?fields=...` (key `issues`) |

`sprint --project KEY` resolves the project's first scrum board, picks the sprint
by `--state` (default `active`), then aggregates issues into a per-status
breakdown. Use `boards --project KEY` to disambiguate multi-board projects and
pass `--board ID`.

## Creating issues safely

Always resolve required/custom fields first:

```
python scripts/jira.py projects --key ABC --createmeta
```

This lists issue types and their required field names. Custom fields appear as
`customfield_NNNNN`; use `--json` to see IDs. Build the `fields` object from that
metadata rather than guessing.

## Data Center vs Cloud

- Assignee/reporter use `name` (username), **not** Cloud `accountId`.
- Text fields (description, comment body) use **wiki markup / plain text**, not
  the Cloud ADF document model.
- API version is `2` (Cloud's `3`/ADF is not used here).

## Pagination & limits

- `search` and `paginate` iterate `startAt`/`maxResults` until `total` is reached
  or the result cap (default 500) is hit. Raise `--limit` when needed.
- Idempotent GETs retry on `429`/`5xx` with backoff; writes never auto-retry.
