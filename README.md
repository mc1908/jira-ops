# jira-ops

A lightweight agent skill for **Jira Data Center / Server** that uses only the
official REST API (`/rest/api/2`) with Personal Access Token auth. No Jira CLI,
no MCP, no Cloud-specific flows. Cross-platform Python core, Windows-first secret
handling.

## Install

> **The `skills` CLI only installs `SKILL.md`** — it does not copy `scripts/` or
> other files. Use the download or clone steps below for a full installation.
>
> **Nested-repo warning:** if you install into an existing git repo (the normal
> case for a project-scoped skill), remove the `.git` directory after cloning so
> you don't accidentally create a nested repository.

### Recommended: download archive (no nested git repo)

```powershell
# PowerShell (Windows)
$dest = ".agents\skills\jira-ops"
Invoke-WebRequest https://github.com/mc1908/jira-ops/archive/refs/heads/main.zip -OutFile jira-ops.zip
Expand-Archive jira-ops.zip -DestinationPath .
Move-Item jira-ops-main $dest
Remove-Item jira-ops.zip
```

```bash
# bash (macOS/Linux)
curl -L https://github.com/mc1908/jira-ops/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=1 -C .agents/skills/jira-ops --one-top-level=jira-ops-main
# or with wget:
wget -qO- https://github.com/mc1908/jira-ops/archive/refs/heads/main.tar.gz | \
  tar -xz && mv jira-ops-main .agents/skills/jira-ops
```

### Alternative: git clone (remove `.git` if inside another repo)

```bash
git clone https://github.com/mc1908/jira-ops.git .agents/skills/jira-ops
# Remove nested .git so it doesn't conflict with the outer repo:
Remove-Item -Recurse -Force .agents\skills\jira-ops\.git   # PowerShell
# rm -rf .agents/skills/jira-ops/.git                      # bash
```

Omit the `.git` removal only if you deliberately want a [git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules) relationship.

### Global install (all projects on this machine)

```bash
# Windows (PowerShell)
$dest = "$env:USERPROFILE\.copilot\skills\jira-ops"
Invoke-WebRequest https://github.com/mc1908/jira-ops/archive/refs/heads/main.zip -OutFile jira-ops.zip
Expand-Archive jira-ops.zip -DestinationPath . ; Move-Item jira-ops-main $dest ; Remove-Item jira-ops.zip

# macOS/Linux
mkdir -p ~/.copilot/skills
curl -L https://github.com/mc1908/jira-ops/archive/refs/heads/main.tar.gz | \
  tar -xz && mv jira-ops-main ~/.copilot/skills/jira-ops
```

For other agents replace `.agents/skills/` / `~/.copilot/skills/` with the
agent's skills directory (see the
[skills CLI supported agents](https://www.npmjs.com/package/skills#supported-agents) table).

### Keep up to date

```bash
# Re-download the archive (cleanest, no git history)
# — repeat the install steps above into the same destination, overwriting files.

# Or if you kept .git (submodule style):
cd .agents/skills/jira-ops && git pull
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
python scripts/jira.py projects
python scripts/jira.py sprint --project ABC        # active sprint + status breakdown
python scripts/jira.py backlog --project ABC       # backlog for planning
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
