# Jira Ops Skill Design

## Goal

Create a local agent skill named `jira-ops` that streamlines common Jira Data Center / Server operations using only Jira's official REST API and safe local PAT-based authentication, while staying as OS-agnostic as practical.

## Why Build Our Own

Existing community Jira skills were discoverable through `npx skills find jira`, but the best-inspected option (`softaworks/agent-toolkit@jira`) explicitly prefers a Jira CLI backend or Atlassian MCP backend. That conflicts with these requirements:

- Use only the official Jira API
- Avoid open-source Jira CLI dependencies
- Avoid MCP dependencies
- Support an internally hosted Jira Data Center instance
- Support easy and safe PAT configuration on Windows

That said, existing Jira skills are still valuable as design references. Even when their transport or tooling is incompatible with our environment, they contain workflow patterns worth reusing.

## External Skill Review and What to Borrow

Inspected reference skills:

- `softaworks/agent-toolkit@jira`
- `alirezarezvani/claude-skills@jira-expert`
- `claude-office-skills/skills@jira-automation`

Key patterns worth borrowing:

- A strong trigger description that catches both explicit Jira requests and implicit issue-key mentions
- A quick-reference layer for common actions so the skill can handle routine tasks with low overhead
- A "fetch current state first" rule before transitions or edits
- A transition workflow that treats available transitions as runtime data, not assumptions
- Reusable JQL patterns for common developer queries such as assigned work, stale issues, blockers, and release scope
- Templates for high-signal comments and issue updates
- A workflow-oriented view of Jira work rather than isolated API calls

Patterns to avoid:

- Backend auto-detection that falls back to Jira CLI or MCP
- Cloud-specific assumptions and tool names
- Overly admin-heavy scope in the MVP
- YAML-heavy static templates that do not reflect the target Jira instance's actual fields and workflow

Design implication:

Our skill should borrow the workflow ergonomics and safety patterns from those skills, while replacing their execution layer with deterministic Python scripts against the official Jira Data Center REST API.

## Scope

The skill should help with frequent day-to-day Jira work such as:

- Validate connectivity and identity
- Find issues assigned to me
- Find work in progress, blocked work, stale work, and sprint-ready work
- Search issues with JQL
- View issue details
- Add comments
- Transition issues
- Create issues
- Update selected fields on issues
- List projects and useful metadata needed for the above tasks
- Draft developer-facing updates from implementation and test context
- Produce concise work summaries suitable for standups or handoff notes

## Non-Goals

- No browser automation
- No Jira Cloud-specific auth flows
- No dependency on third-party Jira CLI tools
- No MCP server requirement
- No direct storage of plaintext PATs in `SKILL.md`, shell history, or repo-tracked config files
- No attempt to automate every Jira admin capability in the first version

## Target Environment

- OS: Windows first, Linux-ready by design
- Jira deployment: internal Jira Data Center / Server
- Auth: Personal Access Token (PAT)
- Transport: HTTPS to the Jira base URL
- Execution style: local scripts invoked by the skill

## Recommended Skill Shape

This skill is distributed as a standalone GitHub repo whose **root is the skill root**,
following the Agent Skills Spec (https://agentskills.io/) so it installs cleanly with:

```text
npx skills add mc1908/jira-ops        # into ./.agents/skills/jira-ops/
npx skills add mc1908/jira-ops -g     # global: ~/.agents/skills/jira-ops/
```

The repo name must equal the skill name (`jira-ops`). On install the CLI copies the
repo contents into `.agents/skills/jira-ops/` in the consumer's project, so `SKILL.md`
lives at the repo root — not nested under `.agents/`.

Repository layout (repo root == skill root):

```text
jira-ops/                     # GitHub repo mc1908/jira-ops
  SKILL.md                    # skill entrypoint; frontmatter name: jira-ops
  README.md                   # human docs + install instructions (not shipped on install)
  LICENSE
  .gitignore                  # what is never committed
  .skillsignore               # what is committed but NOT copied on install
  scripts/
    bootstrap.py
    jira.py                   # thin venv-aware entrypoint
    jira_api.py
    jira_auth.py
    jira_issue.py
    jira_project.py
    jira_transition.py
    jira_common/
      auth.py
      config.py
      client.py
      formatting.py
      presets.py
      setup.py
  assets/
    requirements.txt
  references/
    endpoints.md
    examples.md
    security.md
    setup.md
```

## Distribution and Installation

The skill targets the Agent Skills Spec so it works with any compliant agent
(GitHub Copilot agent mode, Codex CLI, Claude Code) via the discovery paths
`.agents/skills/`, `.github/skills/`, `.claude/skills/`, and `~/.agents/skills/`.

Two-layer exclusion model keeps the published artifact clean:

- `.gitignore` keeps local research and generated files out of the repo entirely:
  the reference skills pulled in under `.agents/` for inspiration, the skills tool
  lockfile, the local `.venv`, caches, and any secret/config artifacts.
- `.skillsignore` keeps committed repo/publishing files out of the *installed*
  payload: `README.md`, `docs/`, `.gitignore`, `.skillsignore`, and any `tests/`.
  What ships to consumers is `SKILL.md`, `scripts/`, `assets/`, `references/`, and
  `LICENSE`.

The design docs in `docs/DESIGN.md` are committed to GitHub for contributor
visibility but excluded from the installed skill via `.skillsignore`. The reference
skills under `.agents/` and the skills tool lockfile stay git-ignored as local
research only.

## SKILL.md Frontmatter and Trigger

The single most important element for invocation is the `description` field. It must front-load Jira intent and issue-key detection so the skill triggers on both explicit and implicit requests.

Draft frontmatter:

```yaml
---
name: jira-ops
description: >-
  Use for Jira Data Center / Server work via the official REST API with PAT auth
  (no Jira CLI, no MCP). Triggers on "jira", "ticket", "issue", "sprint",
  "backlog", issue keys like ABC-123, and requests to search, view, comment on,
  transition, or create issues, draft status/standup updates, or set up/validate
  a Jira PAT.
---
```

`name` must equal the repo and installed-folder name (`jira-ops`) so discovery
paths, the install target, and the skill identity all line up.

### Progressive Disclosure Policy

Keep `SKILL.md` concise and push detail into `references/`. Include an explicit load-decision table so the agent only pays for context it needs.

| Task | Load reference? |
|------|-----------------|
| Who am I / list my issues / view a ticket | No — quick reference is enough |
| Search with a preset | No |
| Compose non-trivial JQL | Yes — `references/examples.md` |
| Create an issue (required/custom fields) | Yes — `references/endpoints.md` (createmeta) |
| Transition by status name | Yes — transition workflow |
| First-time setup / auth failures / TLS | Yes — `references/setup.md`, `references/security.md` |

## High-Level Approach

The skill should act as a thin orchestration layer over reusable Python scripts.

Design principles:

- Keep `SKILL.md` concise and procedural
- Put reusable API logic in scripts, not repeated inline shell commands
- Store only non-secret configuration in files
- Retrieve secrets at runtime from a safer store
- Prefer deterministic script parameters over free-form shell construction
- Optimize for common developer intents first, then expand toward broader project-management operations
- Keep OS-specific logic narrow and isolated behind small Python interfaces

## Self-Bootstrapping Requirement

The skill should not assume the environment is already prepared.

It should be able to:

- detect whether required Python runtime and libraries are available
- install missing Python dependencies when safe to do so
- create or reuse a local virtual environment if needed
- initialize a default config file
- guide the user through PAT setup
- validate the final setup with a real Jira API call

This setup behavior should be built into the skill design, not treated as external documentation.

## Setup Experience

The preferred onboarding flow should feel like:

1. Detect current environment
2. Explain what is missing
3. Install or configure missing prerequisites
4. Prompt for Jira base URL and profile name if config is absent
5. Prompt for PAT entry through a secure input flow
6. Save the PAT through the configured secret backend
7. Test auth with `/rest/api/2/myself`
8. Show a short success summary and suggested first commands

The skill should be able to run this flow automatically when the user says things like:

- "set up Jira"
- "configure the Jira skill"
- "save my PAT"
- "get this ready to use with our Jira"

## OS-Agnostic Strategy

Yes, this should be designed as OS-agnostic as possible.

Recommended approach:

- Use Python for all Jira API logic, formatting, presets, comment drafting, and config handling
- Keep only secret-storage integration OS-specific
- Use a small auth backend abstraction so Windows and Linux can plug in different secret stores later
- Avoid shell-specific behavior in the core workflow

This gives us:

- one implementation of Jira behavior
- one implementation of JQL presets and comment drafting
- one testable client layer
- minimal future Linux work, mostly around credential storage and packaging

## Tooling and Dependency Strategy

To keep setup predictable, the skill should keep external dependencies small and explicit.

Recommended runtime assumptions:

- Python 3.10+ installed
- `pip` available

Recommended Python dependencies:

- `requests`
- `keyring` if chosen for the secret-store abstraction

Optional dependencies should only be installed when their backend is selected.

Secret-backend caveats to plan for:

- `keyring` can fail silently or block in a headless/agent context; always have the
  encrypted fallback ready rather than depending on an interactive keyring prompt.
- The Windows DPAPI encrypted fallback needs `pywin32` or a `ctypes` shim; treat it
  as a Windows-only optional dependency installed with that backend.

Examples:

- Windows-only secret backend helpers
- Linux keyring integration helpers

The skill should prefer:

- standard library where practical
- a local virtual environment over mutating global Python packages
- deterministic install commands from a pinned `requirements.txt`

## Bootstrap Script Design

Add a dedicated bootstrap entrypoint:

- `scripts/bootstrap.py`

Responsibilities:

- check Python version
- check whether required packages are importable
- create a local `.venv` for the skill if needed
- install from `assets/requirements.txt`
- detect available secret-storage backend options
- create the initial config file if missing
- optionally hand off to `jira_auth.py set-token`
- run a final health check

Suggested health checks:

- config file present
- default profile resolves
- PAT can be retrieved
- `/rest/api/2/myself` succeeds

The bootstrap script should be safe to rerun and should behave idempotently.

### Deterministic Interpreter Contract

After bootstrap creates a skill-local `.venv`, every subsequent script call must run
through that same interpreter. This is the most common failure mode for
script-based skills and must be specified explicitly.

- Create the venv at a fixed skill-root-relative path, e.g. `<skill-root>/.venv/`
  (which resolves to `.agents/skills/jira-ops/.venv/` once installed).
- `SKILL.md` should instruct the agent to invoke scripts with the venv interpreter:
  - Windows: `.venv\Scripts\python.exe scripts\<name>.py ...`
  - Linux/macOS: `.venv/bin/python scripts/<name>.py ...`
- Prefer a single thin entrypoint (e.g. `scripts/jira.py`) that re-execs into the
  venv if it is not already the active interpreter, so callers never guess paths.
- Bootstrap should print the exact interpreter path to use on success.

## Automatic Setup Boundaries

The skill should automatically do work when it is low-risk and local:

- create local config directories
- create a local virtual environment
- install Python packages into that local environment
- create non-secret config files
- save credentials through the selected backend

The skill should not silently do high-risk or ambiguous things:

- overwrite an existing config without confirmation
- replace stored credentials without confirmation
- disable TLS verification by default
- install system packages with elevated privileges

When fully automatic install is not possible, the skill should provide exact next steps and continue once the missing prerequisite is available.

## Primary Developer Workflows

The MVP should be designed around realistic developer requests, not just raw REST endpoints.

Core developer use cases:

- "What is assigned to me?"
- "Show me my in-progress tickets"
- "What changed on `ABC-123`?"
- "Add an implementation update to this ticket based on what we changed"
- "Comment on this issue with the test result"
- "Move this ticket to In Progress / In Review / Done if the workflow allows it"
- "Summarize my current Jira work for standup"
- "Find blocked or stale issues assigned to me"
- "Create a bug or follow-up ticket from what we discovered in the codebase"

The skill should treat these as first-class intents with opinionated helpers and reusable query/comment patterns.

## User Experience Principles

The skill should feel lightweight for common tasks:

- Default to the configured profile
- Provide one-command checks like "who am I" and "my issues"
- Return compact summaries instead of full raw JSON unless requested
- Turn implementation context into draft comments instead of making the user hand-write status updates
- Keep write actions explicit and reviewable before sending them

For developer updates, the skill should help transform local context into Jira-safe communication:

- code changes made
- tests run
- test results
- open risks
- next steps

This should enable fast, high-quality comments such as implementation notes, QA notes, or handoff updates.

## Authentication Design

### Preferred Option

Use a credential backend abstraction with platform-specific implementations.

Suggested backend priority:

1. Windows Credential Manager on Windows
2. Secret Service / keyring-compatible store on Linux
3. Encrypted local fallback file when no system secret store is available

Stable secret key name:

```text
jira-pat:https://jira.example.com
```

Desired behavior:

- One setup command stores the PAT once
- Runtime scripts retrieve the PAT by Jira base URL
- Scripts never echo the PAT
- Scripts redact auth headers from errors and logs
- Setup flow uses secure prompt input rather than command-line arguments where possible

### Fallback Option

If the system secret store is unavailable, use an encrypted local token file.

Suggested location (inside the platform config dir, outside the repo):

```text
<config-dir>/jira-ops/secrets/<host>.token
# Windows: %APPDATA%\jira-ops\secrets\jira.example.com.token
# Linux/macOS: ~/.config/jira-ops/secrets/jira.example.com.token
```

Desired behavior:

- Use OS-appropriate encryption where possible
- On Windows, prefer DPAPI for the encrypted fallback
- On Linux, allow a user-scoped encrypted file fallback if no keyring is available
- Keep the token file outside the repo

### Configuration Model

Keep site configuration separate from secrets.

Suggested config file:

```json
{
  "profiles": {
    "default": {
        "baseUrl": "https://jira.example.com",
        "auth": {
        "type": "system-keyring",
        "target": "jira-pat:https://jira.example.com",
        "fallbackEncryptedPath": "secrets/jira.example.com.token"
      },
      "apiVersion": "2",
      "verifyTls": true,
      "caCertPath": null,
      "proxy": null
    }
  },
  "defaultProfile": "default"
}
```

Suggested location:

```text
<config-dir>/jira-ops/config.json
# Windows:     %APPDATA%\jira-ops\config.json
# Linux/macOS: ${XDG_CONFIG_HOME:-~/.config}/jira-ops/config.json
# Override:    set JIRA_OPS_HOME to choose the base directory explicitly
```

The config directory is resolved with a small platform-neutral helper
(`jira_common/paths.py`) and is intentionally not tied to any specific agent
runtime. `fallbackEncryptedPath` is resolved relative to that config directory
unless an absolute path is given.

### Corporate Network Considerations

An internal Data Center instance such as `jira.example.com` will typically
present a certificate signed by a corporate CA and may sit behind an HTTP proxy.

- Keep `verifyTls: true` by default; never disable verification as a shortcut.
- Support a `caCertPath` that maps to the client `verify=<path>` (and honor
  `REQUESTS_CA_BUNDLE` if already set in the environment).
- Support an optional `proxy` setting and honor standard `HTTPS_PROXY` /
  `NO_PROXY` environment variables.
- On a TLS failure, surface a clear next step (point the user at `caCertPath`)
  rather than suggesting `verifyTls: false`.

### Credential Setup Guidance

The skill should explicitly guide the user through PAT setup instead of requiring them to know the backend details.

Preferred behavior:

- prompt for profile name, defaulting to something simple like `default`
- prompt for Jira base URL
- explain which secret backend is being used
- read the PAT from a secure prompt, not from shell history
- save the PAT
- immediately validate it against Jira

If credential save fails, the skill should:

- explain which backend failed
- fall back to the next supported backend if safe
- preserve the already-entered non-secret config

## Script Responsibilities

### `scripts/jira_auth.py`

Responsibilities:

- Save PAT to the configured secret backend
- Validate auth with `GET /rest/api/2/myself`
- Show the resolved account identity after setup
- Avoid exposing secrets in output

Potential commands:

- `set-token`
- `test-auth`
- `clear-token`
- `setup-profile`

### `scripts/jira_api.py`

Responsibilities:

- Load profile config
- Resolve PAT from secret storage
- Build standard headers
- Invoke Jira REST endpoints consistently
- Normalize errors from the HTTP client

This is the shared foundation for all other scripts.

### `scripts/jira_issue.py`

Responsibilities:

- Search issues with JQL (paginated)
- View issue details
- List "my issues" with useful presets
- Create issues after resolving required fields via `createmeta`
- Edit selected fields (allowlisted)
- Add comments (wiki markup / plain text)
- Draft comments from structured implementation context
- Render concise issue summaries for terminal use
- Support `--dry-run` on every write action to preview the exact request payload
- Support `--json` for machine-readable output the agent can parse reliably

### `scripts/jira_project.py`

Responsibilities:

- List visible projects (paginated)
- View project metadata
- Fetch issue types and `createmeta` for a project before issue creation, so the
  create workflow can resolve required and custom field IDs instead of guessing

### `scripts/jira_transition.py`

Responsibilities:

- List available transitions for an issue
- Perform a transition by transition ID or status name
- Validate current status before attempting transition

## Python Implementation Notes

Recommended libraries:

- Standard library first for config, JSON, argparse, and text formatting
- `requests` for HTTP unless there is a reason to prefer `httpx`
- `keyring` for cross-platform secret-store integration if it behaves reliably in the target environments

Packaging recommendations:

- keep a pinned `assets/requirements.txt`
- optionally add a small `pyproject.toml` later if the skill grows beyond script-based usage
- prefer `python -m pip install -r assets/requirements.txt` inside a local virtual environment

Suggested module layout:

- `jira_common/config.py`
  load and validate profile config
- `jira_common/auth.py`
  resolve PAT from system keyring or encrypted fallback
- `jira_common/client.py`
  shared Jira REST client and error normalization
- `jira_common/presets.py`
  JQL presets and update templates
- `jira_common/formatting.py`
  concise terminal summaries and structured output
- `jira_common/setup.py`
  environment checks, venv creation, dependency install orchestration, and health checks

This keeps the command scripts thin and makes unit testing much easier.

## Installation and Configuration Flow

The skill should expose a setup path that another agent can follow with minimal improvisation.

Recommended sequence:

1. Run `bootstrap.py`
2. If dependencies are missing:
   install them into the skill-local virtual environment
3. If config is missing:
   create a default config interactively
4. If credentials are missing:
   call `jira_auth.py setup-profile` or `set-token`
5. Validate with `/myself`
6. Suggest first-use commands such as:
   - list my issues
   - view a ticket
   - add a comment

The skill instructions in `SKILL.md` should tell the agent to prefer this setup path when the skill is not yet configured.

## Intent Presets

The skill should provide a small preset library for common queries and updates.

Suggested read presets:

- `my-open`
- `my-in-progress`
- `my-blocked`
- `my-stale`
- `recently-updated-by-me`
- `project-open`
- `release-scope`

Suggested write-oriented helpers:

- `comment-implementation-update`
- `comment-test-result`
- `comment-blocked-reason`
- `comment-handoff`
- `transition-to-in-progress`
- `transition-to-review`
- `transition-to-done`

These can map to script parameters instead of being hard-coded into `SKILL.md`.

## Official Jira API Surface

Initial endpoints to support:

- `GET /rest/api/2/myself`
- `GET /rest/api/2/project`
- `GET /rest/api/2/project/{projectIdOrKey}`
- `GET /rest/api/2/issue/{issueKey}`
- `POST /rest/api/2/issue`
- `PUT /rest/api/2/issue/{issueKey}`
- `POST /rest/api/2/issue/{issueKey}/comment`
- `GET /rest/api/2/issue/{issueKey}/transitions`
- `POST /rest/api/2/issue/{issueKey}/transitions`
- `GET /rest/api/2/search`
- `POST /rest/api/2/search`
- `GET /rest/api/2/mypermissions` if permission debugging becomes necessary

Notes:

- Use bearer auth with the PAT
- Default to API v2 unless the target instance clearly requires another stable version
- Prefer POST search when JQL length or field selection gets large

### API Client Behavior

The shared client must handle realities of a live Data Center instance:

- Pagination: iterate `startAt` / `maxResults` against `total` for search and
  project listings; never assume the first page is complete. Expose a sane
  default page size and an overall result cap.
- Retries: retry idempotent GETs on transient `429` and `5xx` with bounded
  exponential backoff; honor `Retry-After` when present.
- Write idempotency: writes (comment, transition, create) must not be
  auto-retried blindly. Re-adding the same comment creates duplicates, so a
  retry of a write must be explicit and user-confirmed.
- Data Center identity: assignment and `assignee` use the **username** (`name`),
  not a Cloud `accountId`. Do not copy the Cloud accountId pattern from
  reference skills.
- Comment/field bodies use v2 **wiki markup / plain text**, not Cloud ADF.
  Drafted comments must render correctly in that format.

## Skill Behavior

The skill should trigger when the user asks to:

- interact with Jira Data Center / Server
- search or update Jira issues
- create comments or transition tickets
- set up or validate Jira PAT auth on Windows
- avoid Jira CLI / MCP and use official Jira REST APIs only

The skill should:

- read local config
- use scripts for execution
- confirm destructive or high-impact changes before sending them
- show exact API intent in human-readable terms
- prefer developer-centric presets before asking the user to compose raw JQL
- synthesize draft comments from repo and test context when the user asks for status updates
- stay shell-neutral so the same skill behavior works in Windows PowerShell, bash, or other environments that can run Python
- detect missing configuration and route the user into the setup flow automatically

## JQL Starter Library

The skill should bundle a reference file with a small set of proven JQL patterns tailored to developer workflows.

Suggested starters:

- My open work:
  `assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC, updated DESC`
- My in-progress work:
  `assignee = currentUser() AND status = "In Progress" ORDER BY updated DESC`
- My stale work:
  `assignee = currentUser() AND resolution = Unresolved AND updated < -5d ORDER BY updated ASC`
- My blocked work:
  `assignee = currentUser() AND resolution = Unresolved AND (labels = blocked OR status = Blocked)`
- Release scope:
  `fixVersion = "VERSION" AND resolution = Unresolved ORDER BY priority DESC`

The exact set should remain editable because field names and status names vary by Jira instance.

## Comment and Status Update Design

The skill should support structured status-update drafting rather than only free-form comments.

Suggested input model:

- issue key
- work summary
- files or modules touched
- tests run
- test outcomes
- blockers or risks
- next step

Suggested output styles:

- concise implementation update
- test result update
- blocked update
- handoff update

This is especially useful when the user says things like:

- "update the ticket based on what we changed"
- "leave a comment with the test result"
- "move it to review and mention the validation work"

## Safety Rules

- Never print the PAT
- Never write the PAT into repo files
- Never pass the PAT as a visible command-line argument if stdin or secure prompt is available
- Redact `Authorization` headers from all errors
- Prefer read-only validation before write actions
- Require explicit confirmation for create, edit, transition, or comment actions unless the user clearly asked for them
- Always fetch current issue state before editing, commenting, or transitioning
- Always fetch available transitions before attempting a status move by name
- Avoid overwriting long-form fields like description unless the user explicitly requests replacement behavior

## Output Style

For common read operations, return concise structured summaries:

- issue key
- summary
- status
- assignee
- reporter
- priority
- labels
- direct URL

For write operations, return:

- action attempted
- target issue or project
- result status
- any returned key or transition confirmation

Every command should support a `--json` flag that emits structured output for
agent consumption, and should use consistent, documented process **exit codes**
per error category (network, TLS, auth, authorization, invalid JQL, transition
not found, validation) so callers can branch without parsing prose.

## Implementation Notes

### Credential Storage Recommendation

Recommended priority:

1. System keyring via Python abstraction
2. OS-specific secure fallback encryption
3. Only if necessary, an explicit user-managed secret injection flow

Reasoning:

- A Python keyring abstraction gives us the best chance of Windows/Linux portability
- Windows Credential Manager can sit behind that abstraction on Windows
- Linux secret stores can be added later without changing Jira workflow code
- Encrypted fallback files avoid plaintext repo secrets when no keyring is available

### Setup and Install Recommendation

Recommended priority:

1. local virtual environment
2. pinned requirements install
3. interactive config creation
4. secure PAT save
5. live auth validation

Reasoning:

- keeps the skill self-contained
- reduces dependence on global Python state
- makes the setup repeatable
- gives clear success or failure signals early

## Cross-Platform Tradeoffs

Python makes the skill much more portable, but secret handling is still the hardest cross-platform part.

Expected reality:

- Jira API operations are easy to make cross-platform
- Config handling is easy to make cross-platform
- Secure PAT storage will still need OS-specific adapters and testing

So the right design is:

- Python-first core
- pluggable auth storage
- Windows implemented first
- Linux support added by implementing the Linux secret backend and validating it

### Error Handling

Normalize these categories:

- network failure
- TLS/certificate failure
- authentication failure
- authorization failure
- invalid JQL
- transition not found
- validation or field schema error

Each error should include:

- category
- HTTP status if present
- Jira error messages when available
- a short next-step suggestion

## Testing Strategy

The script-based design is only maintainable if the core layers are testable
without a live Jira instance.

- Unit-test `config.py`, `presets.py`, `formatting.py`, and error normalization
  against fixtures with no network access.
- Mock the HTTP layer (e.g. `requests` responses) to cover pagination, retry,
  and each normalized error category.
- Keep at least one opt-in integration check that runs `/myself` against a real
  instance when a PAT is configured, gated behind an environment flag.
- Never embed real credentials or instance URLs in fixtures or tests.

## Minimal MVP

The first usable version of the skill should support:

1. Bootstrap environment and install dependencies locally
2. Configure profile
3. Save PAT securely
4. Test auth with `/myself`
5. List issues assigned to the current user with presets
6. Search issues with JQL
7. View a ticket
8. Add a comment
9. Draft a comment from implementation/test context
10. Transition a ticket after resolving allowed transitions
11. Preview every write with `--dry-run` and support `--json` output

## Phase 2

Possible next additions:

- create issue
- edit fields safely with allowlisted field names
- assign issue
- fetch board or sprint metadata if your Jira instance uses those APIs reliably
- export compact results for note-taking or markdown reports
- generate standup or handoff summaries from Jira + local repo context
- suggest next Jira action based on implementation completion and test evidence
- richer backend detection and capability reporting
- optional non-interactive setup flags for automation

## Resolved Decisions

1. Ship `keyring` (Windows Credential Manager) and the DPAPI encrypted fallback
   together from the start; the fallback is required for headless/agent runs anyway.
2. Model multi-profile config from day one, but only exercise a single profile in MVP.
3. Dry-run preview is an MVP requirement for all write operations, not optional.
4. Linux: portable encrypted-file fallback first, real desktop keyring later.
5. Bootstrap creates a skill-local `.venv` at a fixed path (self-contained and
   matching the deterministic interpreter contract) rather than a shared user env.

## Recommended Next Step

Build the skill in this folder with:

- a concise `SKILL.md`
- `scripts/bootstrap.py` for setup and health checks
- `scripts/jira_api.py` as the shared API layer
- `scripts/jira_auth.py` for PAT setup and validation
- one or two task scripts for search and issue updates

That gives us a narrow, testable first version aligned with your Jira Data Center environment, while keeping the core implementation portable to Linux later.
