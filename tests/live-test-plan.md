# jira-ops Live Test Plan

**Target instance:** the configured Jira Data Center profile.
**Safe project:** `FASTACTR67`
**Safe existing issue (write target):** `FASTACTR67-578` — seeded fixture
(`[DEMO SEED] ... safe write target (do not delete)`).

This plan enumerates live test cases for every command. It is written so each
case can be turned directly into an executable test (e.g. `pytest` invoking the
CLI and asserting on exit code + `--json` output). Cases have stable IDs
(`LT-NN`), an exact command, expected exit code, and machine-checkable assertions.

> **Now implemented as a pytest suite** in this directory
> (`conftest.py`, `test_readonly.py`, `test_dryrun.py`, `test_writes.py`,
> `test_errors.py`). Opt-in via env flags:
>
> ```
> # read-only + dry-run + error suites (side-effect free)
> JIRA_OPS_LIVE=1 python -m pytest tests/
>
> # add the real-write suite (creates/reverts on the safe targets)
> JIRA_OPS_LIVE=1 JIRA_OPS_LIVE_WRITE=1 python -m pytest tests/
> ```
>
> Without `JIRA_OPS_LIVE` every case is skipped, so a default `pytest` run
> touches nothing.

> **Scope & safety**
> - All **writes target only `FASTACTR67` / `FASTACTR67-578`**. Never write to
>   any other project or issue during these tests.
> - Every write case runs its **`--dry-run` variant first** and asserts on the
>   previewed payload before the real call.
> - Deletion is **not supported** by the skill (by design), so some artifacts
>   (links, attachments, worklogs) cannot be removed via the CLI — see
>   [Cleanup](#8-cleanup--teardown). Prefer reverting where possible; otherwise
>   record the artifact for manual/UI cleanup.
> - No real PAT is ever placed in argv. Use a stored token or `JIRA_OPS_TOKEN`.

---

## 1. Harness conventions (for the future executable suite)

- **Invocation:** `python scripts/jira.py <cmd> ... --json`, run from the skill
  root (`skills/jira-ops/`).
- **Assertions:**
  - `returncode` == expected exit code (see the map in
    [`SKILL.md`](../skills/jira-ops/SKILL.md) → *Exit codes*).
  - For success cases, parsed stdout JSON has `ok == true` and the documented
    keys (`action`, `issue`, etc.).
  - For error cases, parsed JSON has the expected `category` / non-zero exit.
- **Fixtures the harness should provide:**
  - `PROJECT = "FASTACTR67"`, `ISSUE = "FASTACTR67-578"`.
  - `ME` = value of `auth whoami` (`name`).
  - `ORIGINAL_578` = snapshot from `view FASTACTR67-578 --json` captured in
    setup, used to restore mutated fields in teardown.
  - A small temp file for the attachment test.
- **Isolation:** consider a dedicated test **profile** (`--profile test`) pointing
  at the same instance so it never disturbs a human's default profile.
- **Marking:** tag write cases (`@pytest.mark.write`) and destructive-artifact
  cases (`@pytest.mark.dirty`) so read-only runs can be selected in CI.

---

## 2. Preconditions

| ID | Check | Command | Expect |
|----|-------|---------|--------|
| PRE-01 | Local readiness (no network) | `python scripts/jira.py health` | exit 0 |
| PRE-02 | Auth valid | `python scripts/jira.py auth test-auth --json` | exit 0, `ok:true` |
| PRE-03 | Identity captured | `python scripts/jira.py auth whoami --json` | exit 0; capture `name` → `ME` |
| PRE-04 | Safe project visible | `python scripts/jira.py projects --key FASTACTR67 --json` | exit 0, `project.key == "FASTACTR67"` |
| PRE-05 | Write target exists + snapshot | `python scripts/jira.py view FASTACTR67-578 --json` | exit 0; capture `ORIGINAL_578` (summary, description, assignee, labels) |

If PRE-01/02 fail, stop — the environment (config/PAT/VPN) is not ready.

---

## 3. Read-only suite (safe, no cleanup)

| ID | Purpose | Command | Expect |
|----|---------|---------|--------|
| LT-01 | Whoami | `auth whoami --json` | exit 0, `name` present |
| LT-02 | List projects | `projects --json` | exit 0, `count >= 1` |
| LT-03 | Project metadata | `projects --key FASTACTR67 --json` | exit 0, `project.key == FASTACTR67` |
| LT-04 | Create metadata | `projects --key FASTACTR67 --createmeta --json` | exit 0, `createMeta` non-empty (capture a valid `issueType`) |
| LT-05 | User lookup | `users --query <ME-fragment> --json` | exit 0, `count >= 1` |
| LT-06 | Search by JQL | `search --jql "project = FASTACTR67 ORDER BY created DESC" --json` | exit 0, `issues` is a list |
| LT-07 | Search by project shortcut | `search --project FASTACTR67 --json` | exit 0 |
| LT-08 | Mine (open) | `mine --preset my-open --json` | exit 0 |
| LT-09 | View issue | `view FASTACTR67-578 --json` | exit 0, `issue.key == FASTACTR67-578` |
| LT-10 | Read comments | `comments FASTACTR67-578 --json` | exit 0, `comments` is a list |
| LT-11 | Change history | `history FASTACTR67-578 --json` | exit 0, `history` is a list |
| LT-12 | List worklogs | `worklog FASTACTR67-578 --json` | exit 0, `worklogs` is a list |
| LT-13 | List transitions | `transitions FASTACTR67-578 --json` | exit 0, `transitions` is a list (capture ids/names) |
| LT-14 | Link types | `link-types --json` | exit 0, `linkTypes` non-empty (capture a valid name, e.g. `Relates`) |
| LT-15 | Favourite filters | `filters --json` | exit 0, `filters` is a list |
| LT-16 | Boards | `boards --project FASTACTR67 --json` | exit 0, `boards` is a list |
| LT-17 | Sprints | `sprints --project FASTACTR67 --json` | exit 0 (may be empty if no scrum board) |
| LT-18 | Active sprint | `sprint --project FASTACTR67 --json` | exit 0 **or** exit 15 (no active sprint / no board) — both acceptable |
| LT-19 | Backlog | `backlog --project FASTACTR67 --json` | exit 0 or 15 |

> LT-17–19 depend on a scrum board existing for `FASTACTR67`. If none exists,
> the expected outcome is a clean `not_found` (exit 15), not a crash.

---

## 4. Write suite — dry-run only (no state change)

Each asserts exit 0, `dryRun:true`, and the previewed `request`/`fields`.

| ID | Command | Assert |
|----|---------|--------|
| LT-20 | `comment FASTACTR67-578 --body "live-test dry-run" --dry-run --json` | `action:"comment"`, `request.body` echoes text |
| LT-21 | `update FASTACTR67-578 --summary "LT temp" --dry-run --json` | `action:"update"`, `fields` contains `summary` |
| LT-22 | `create --project FASTACTR67 --type <LT-04 type> --summary "LT create" --dry-run --json` | `action:"create"`, `request.fields.project.key == FASTACTR67` |
| LT-23 | `assign FASTACTR67-578 --to <ME> --dry-run --json` | `action:"assign"`, `to == ME` |
| LT-24 | `link FASTACTR67-578 --to FASTACTR67-578 --type "<LT-14 name>" --dry-run --json` | `action:"link"` (self-link only in dry-run; never send) |
| LT-25 | `attach FASTACTR67-578 --file <tempfile> --dry-run --json` | `action:"attach"`, file name+size listed |
| LT-26 | `worklog FASTACTR67-578 --time "5m" --comment "LT" --dry-run --json` | `action:"worklog"`, `request.timeSpent == "5m"` |
| LT-27 | `sprint-add --id <sprint-id> --issue FASTACTR67-578 --dry-run --json` | `action:"sprint-add"` (only if a sprint id is available from LT-17) |

---

## 5. Write suite — real writes with revert

Run only after the dry-run counterpart passes. Capture created ids for teardown.

| ID | Action | Command | Assert | Revert / cleanup |
|----|--------|---------|--------|------------------|
| LT-30 | Add comment | `comment FASTACTR67-578 --body "live-test LT-30 (safe to ignore)" --json` | exit 0, `commentId` present | Comment cannot be deleted via CLI → leave; note id |
| LT-31 | Update field + restore | `update FASTACTR67-578 --summary "LT-31 temp summary" --json` | exit 0, `fields` includes `summary` | Restore with `update FASTACTR67-578 --summary "<ORIGINAL_578.summary>"` |
| LT-32 | Assign to me + restore | `assign FASTACTR67-578 --to <ME> --json` | exit 0, `to == ME` | Restore original assignee (`--to <orig>` or `--to -` if was unassigned) |
| LT-33 | Add label + remove | `update FASTACTR67-578 --label lt-marker --json` | exit 0 | `update FASTACTR67-578 --label -lt-marker --json` |
| LT-34 | Log work | `worklog FASTACTR67-578 --time "5m" --comment "LT-34" --json` | exit 0, `worklogId` present | Worklog not removable via CLI → note id for manual cleanup |
| LT-35 | Attach file | `attach FASTACTR67-578 --file <tempfile> --json` | exit 0, `attached[0].filename` matches | Attachment not removable via CLI → note id |
| LT-36 | Create throwaway issue | `create --project FASTACTR67 --type <LT-04 type> --summary "LT-36 throwaway (safe to close)" --json` | exit 0, capture `issue` → `NEW_KEY` | Not deletable → transition `NEW_KEY` toward Done and label `lt-artifact` |
| LT-37 | Link two test issues | `link FASTACTR67-578 --to <NEW_KEY> --type "<LT-14 name>" --json` | exit 0 | Link not removable via CLI → note for UI cleanup |
| LT-38 | Transition + revert | `transition FASTACTR67-578 --to "<reversible status from LT-13>" --json` | exit 0, `to` matches | Transition back to `<ORIGINAL_578.status>` if the workflow allows |

> LT-38 and the LT-36 close step depend on the project's workflow; treat as
> **conditional** — skip gracefully if no reversible transition is available
> rather than forcing an invalid move.

---

## 6. Error-path suite (negative tests)

| ID | Purpose | Command | Expect |
|----|---------|---------|--------|
| LT-40 | Invalid JQL | `search --jql "project = FASTACTR67 AND bogusfield = x" --json` | exit 16 (`invalid_jql`) |
| LT-41 | Unknown issue | `view FASTACTR67-99999999 --json` | exit 15 (`not_found`) |
| LT-42 | Missing issue type on create | `create --project FASTACTR67 --summary "no type" --json` | exit 10 (`config`), message tells agent to pick/ask type |
| LT-43 | Bad transition name | `transition FASTACTR67-578 --to "NoSuchStatus" --json` | exit 17 (`transition_not_found`) |
| LT-44 | Missing attachment file | `attach FASTACTR67-578 --file .\does-not-exist.bin --json` | exit 10 (`config`), "file not found" |
| LT-45 | Unknown filter | `filter 99999999 --json` | exit 15 (`not_found`) or documented error |
| LT-46 | Secret-leak guard | `comment FASTACTR67-578 --body "<the live PAT>" --dry-run --json` | exit 18 (`validation`), refuses to send |

> LT-46 must construct the body from the live token **in-process** (never on the
> command line / logs); it asserts the guard fires. Skip if the token is not
> retrievable in the harness.

---

## 7. Coverage matrix

Every command should have at least one case:

| Command | Read | Dry-run | Real write | Error |
|---------|------|---------|-----------|-------|
| health / auth / whoami | PRE-01..03, LT-01 | — | — | — |
| projects / createmeta | LT-02..04 | — | — | — |
| users | LT-05 | — | — | — |
| search / mine | LT-06..08 | — | — | LT-40 |
| view | LT-09 | — | — | LT-41 |
| comments | LT-10 | — | — | — |
| history | LT-11 | — | — | — |
| worklog | LT-12 | LT-26 | LT-34 | — |
| transitions / transition | LT-13 | — | LT-38 | LT-43 |
| link / link-types | LT-14 | LT-24 | LT-37 | — |
| comment | — | LT-20 | LT-30 | LT-46 |
| update | — | LT-21, LT-33 | LT-31, LT-33 | — |
| create | LT-04 (meta) | LT-22 | LT-36 | LT-42 |
| assign | — | LT-23 | LT-32 | — |
| attach | — | LT-25 | LT-35 | LT-44 |
| filters / filter | LT-15 | — | — | LT-45 |
| boards / sprints / sprint / backlog | LT-16..19 | — | — | — |
| sprint-add | — | LT-27 | (conditional) | — |

---

## 8. Cleanup / teardown

Run in reverse order of creation; tolerate already-clean state.

1. **Restore `FASTACTR67-578`** to `ORIGINAL_578`: summary (LT-31), assignee
   (LT-32), remove `lt-marker` label (LT-33), transition back (LT-38).
2. **Throwaway issue `NEW_KEY`** (LT-36): transition toward Done and add
   `lt-artifact` label. It cannot be deleted via the skill (by design).
3. **Record for manual/UI cleanup** (not removable via CLI): the LT-30 comment,
   LT-34 worklog, LT-35 attachment, LT-37 link.
4. Re-run `view FASTACTR67-578 --json` and diff against `ORIGINAL_578` to confirm
   the reverts landed.

> This CLI-cleanup limitation is expected: deletion/removal of comments,
> worklogs, attachments, and links is intentionally out of scope (see
> `references/extending.md`). The plan minimizes irreversible artifacts by using
> `--dry-run` first and keeping real writes on the two designated safe targets.

---

## 9. Notes for turning this into code

- One test module per suite section (`test_readonly.py`, `test_dryrun.py`,
  `test_writes.py`, `test_errors.py`) sharing a `conftest.py` with the fixtures
  in §1.
- A small helper `run(*args) -> (returncode, json_or_none)` that shells out to
  `python scripts/jira.py ... --json` and parses stdout.
- Gate real-write and dirty tests behind an env flag (e.g.
  `JIRA_OPS_LIVE_WRITE=1`) so the default run is read-only and side-effect free.
- Keep `PROJECT` / `ISSUE` in one place; fail fast in setup if they are not
  visible so the suite never accidentally targets the wrong instance.
