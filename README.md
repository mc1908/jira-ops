# jira-ops

A lightweight agent skill for **Jira Data Center / Server** that uses only the
official REST API (`/rest/api/2`) with Personal Access Token auth. No Jira CLI,
no MCP, no Cloud-specific flows. Cross-platform Python core, Windows-first secret
handling.

## Install

```
npx skills add mc1908/jira-ops        # into ./.agents/skills/jira-ops/
npx skills add mc1908/jira-ops -g     # global: ~/.agents/skills/jira-ops/
```

Works with any agent following the [Agent Skills Spec](https://agentskills.io/)
(GitHub Copilot agent mode, Codex CLI, Claude Code) via the `.agents/skills/`,
`.github/skills/`, and `.claude/skills/` discovery paths.

## Setup

```
python scripts/bootstrap.py                                   # venv + dependencies
python scripts/jira.py setup --base-url "https://your-jira-host" --name default
python scripts/jira.py auth set-token --token-stdin           # PAT via stdin
python scripts/jira.py auth test-auth                         # validate /myself
```

The PAT is stored in the OS secret store when available, otherwise a
DPAPI-encrypted file (Windows) or a `0600` file (POSIX) under the platform config
directory:

- Windows: `%APPDATA%\jira-ops\`
- Linux/macOS: `${XDG_CONFIG_HOME:-~/.config}/jira-ops/`
- Override with `JIRA_OPS_HOME`.

The token is never written to the repo and never printed.

## Common commands

```
python scripts/jira.py auth whoami
python scripts/jira.py mine --preset my-open
python scripts/jira.py search --jql "project = ABC AND status = Open"
python scripts/jira.py view ABC-123
python scripts/jira.py transitions ABC-123
python scripts/jira.py transition ABC-123 --to "In Review" --dry-run
python scripts/jira.py comment ABC-123 --body "Deployed to staging." --dry-run
python scripts/jira.py projects
```

Add `--json` to any command for machine-readable output. Write commands
(`comment`, `transition`) support `--dry-run` to preview the exact request.

## Corporate network

- Custom CA: `--ca-cert "C:\path\ca-bundle.pem"` (or set `REQUESTS_CA_BUNDLE`).
- Proxy: `--proxy "http://proxy:8080"` (or standard `HTTPS_PROXY`/`NO_PROXY`).
- TLS verification stays on by default; do not disable it as a shortcut.

## Security

- PAT stored outside the repo via OS secret store or encrypted fallback.
- `Authorization` headers are redacted from errors; tokens are never logged.
- Tokens can be provided via `--token-stdin` or the `JIRA_OPS_TOKEN` env var for
  automation. Rotate any PAT that has been exposed.

## License

See [LICENSE](LICENSE).
