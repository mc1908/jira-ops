# jira-ops

A lightweight agent skill for **Jira Data Center / Server** that uses only the
official REST API (`/rest/api/2`) with Personal Access Token auth. No Jira CLI,
no MCP, no Cloud-specific flows. Cross-platform Python core, Windows-first secret
handling.

## Install

```bash
npx skills add mc1908/jira-ops        # project install → .agents/skills/jira-ops/
npx skills add mc1908/jira-ops -g     # global install
```

Works with any agent that follows the [Agent Skills Spec](https://agentskills.io/)
(GitHub Copilot, Codex, Claude Code, Cursor, etc.) via the standard skills
discovery paths.

The CLI installs the full skill directory — `SKILL.md`, `scripts/`, `assets/`,
and `references/` — into your agent's skills folder. No manual clone needed.

### Manual install / update

```powershell
# PowerShell — download archive (no nested .git)
$dest = ".agents\skills\jira-ops"
Invoke-WebRequest https://github.com/mc1908/jira-ops/archive/refs/heads/main.zip -OutFile jira-ops.zip
Expand-Archive jira-ops.zip -DestinationPath .
Move-Item jira-ops-main\skills\jira-ops $dest
Remove-Item jira-ops.zip, jira-ops-main -Recurse -Force
```

```bash
# bash — download archive
curl -L https://github.com/mc1908/jira-ops/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=2 -C .agents/skills/jira-ops jira-ops-main/skills/jira-ops
```

Or with git (remove `.git` to avoid a nested repo inside an existing repo):

```bash
git clone https://github.com/mc1908/jira-ops.git _jira-ops-tmp
cp -r _jira-ops-tmp/skills/jira-ops .agents/skills/jira-ops
rm -rf _jira-ops-tmp
```

### Update

```bash
npx skills update jira-ops
```

## Setup

The fastest path is the guided setup, which collects everything (base URL,
profile name, default project, optional CA/proxy) and your PAT in one session:

> Run every command from the **skill root** — the folder that contains
> `SKILL.md` (e.g. `C:\ai\skills\jira-ops>`). The `scripts/...` paths are
> relative to it; you never `cd` into `scripts/`. (Absolute paths work from any
> directory too, since config/venv/token resolve independently of the cwd.)

```
python scripts/bootstrap.py            # venv + dependencies, then guided setup
python scripts/bootstrap.py -i         # re-run the guided setup any time
```

Prefer flags? Configure it non-interactively instead:

```
python scripts/jira.py setup --base-url "https://your-jira-host" \
    --name default --default-project ABC
python scripts/jira.py auth set-token --token-stdin           # PAT via stdin
python scripts/jira.py auth test-auth                         # validate /myself
```

### Default project

Set `--default-project ABC` (or answer the prompt during guided setup) so
project-scoped commands work without repeating `--project` every time:

```
python scripts/jira.py sprint          # active sprint for the default project
python scripts/jira.py backlog         # its backlog
python scripts/jira.py search          # its open issues
```

Pass `--project OTHER` on any command to override the default for that call.

The PAT is stored in the OS secret store when available, otherwise a
DPAPI-encrypted file (Windows) or a `0600` file (POSIX) under the platform config
directory:

- Windows: `%APPDATA%\jira-ops\`
- Linux/macOS: `${XDG_CONFIG_HOME:-~/.config}/jira-ops/`
- Override with `JIRA_OPS_HOME`.

The token is never written to the repo and never printed.

### Update or rotate your PAT

Re-run `set-token` at any time — it overwrites the stored token and immediately
re-validates it. There is no separate "update" command; setting is updating.

```
python scripts/jira.py auth set-token          # prompts securely, then validates
python scripts/jira.py auth set-token --token-stdin < new_pat.txt   # non-interactive
python scripts/jira.py auth clear-token         # remove the stored PAT
python scripts/jira.py auth whoami              # confirm the active identity
```

- Guided setup (`bootstrap.py -i`) detects an existing token and offers to keep
  or rotate it.
- `JIRA_OPS_TOKEN` (env) takes precedence over the stored token while it is set —
  useful for CI, but unset it to fall back to the stored PAT.
- Rotate immediately if a PAT is ever exposed, and revoke the old one in Jira
  (Profile → Personal Access Tokens).

## Common commands

```
python scripts/jira.py auth whoami
python scripts/jira.py mine --preset my-open
python scripts/jira.py search --jql "project = ABC AND status = Open"
python scripts/jira.py view ABC-123
python scripts/jira.py transitions ABC-123
python scripts/jira.py transition ABC-123 --to "In Review" --dry-run
python scripts/jira.py comment ABC-123 --body "Deployed to staging." --dry-run
python scripts/jira.py update ABC-123 --summary "New title" --priority High --dry-run
python scripts/jira.py create --project ABC --type Task --summary "New task" --dry-run
python scripts/jira.py projects
python scripts/jira.py sprint --project ABC        # active sprint + status breakdown
python scripts/jira.py backlog --project ABC       # backlog for planning
```

Add `--json` to any command for machine-readable output. Write commands
(`comment`, `transition`, `update`, `create`) support `--dry-run` to preview the exact request.

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
