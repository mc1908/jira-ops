# Setup & troubleshooting

> Run all commands from the **skill root** — the folder containing `SKILL.md`
> (e.g. `C:\ai\skills\jira-ops>`). The `scripts/...` paths are relative to it;
> do not `cd` into `scripts/`. An absolute path
> (`python C:\...\jira-ops\scripts\jira.py ...`) works from any directory because
> config, venv, and token all resolve independently of the current directory.

## Guided setup (recommended)

```
python scripts/bootstrap.py       # venv + deps, then prompts for everything
python scripts/bootstrap.py -i    # re-run the guided setup any time
```

The guided flow collects the base URL, profile name, **default project**,
optional CA bundle / proxy, and your PAT — then validates against `/myself`.

## Full setup (non-interactive)

```
python scripts/bootstrap.py
python scripts/jira.py setup --base-url "https://your-jira-host" --name default \
    --default-project ABC
python scripts/jira.py auth set-token --token-stdin
python scripts/jira.py auth test-auth
```

`bootstrap.py` is idempotent: it creates `<skill-root>/.venv`, installs
`assets/requirements.txt`, and runs a local health check. It prints the exact
interpreter path, but you should invoke everything through `scripts/jira.py`,
which auto re-execs into the venv.

## Default project

Set once with `--default-project ABC` (or in guided setup) so `sprint`,
`backlog`, and `search` resolve the project automatically. Stored as
`defaultProject` on the profile in `config.json`. Override per call with
`--project OTHER`.

## Health check (no network)

```
python scripts/jira.py health
```

Reports Python version, venv presence, dependency import, and config validity.

## Common issues

| Symptom | Fix |
|---------|-----|
| `[config] No config found` | Run `jira setup ...` |
| `[auth] No token stored` | Run `jira auth set-token` |
| `[auth]` on test-auth (401) | PAT invalid/expired — set a fresh one |
| `[authorization]` (403) | Account lacks permission for the action |
| `[tls]` (14) | Set `caCertPath` to the corporate CA bundle |
| `[network]` (13) | Check base URL, connectivity, proxy |
| `[invalid_jql]` (16) | Adjust status/field names for this instance |
| `[transition_not_found]` (17) | Run `transitions KEY` first; names vary |

## Multiple profiles

`config.json` supports multiple named profiles. Pass `--profile NAME` to any
command; otherwise the `defaultProfile` is used.

```
python scripts/jira.py setup --name staging --base-url "https://staging-jira" 
python scripts/jira.py mine --profile staging
```

## Non-interactive automation

Set `JIRA_OPS_TOKEN` to skip token storage/prompt, and `JIRA_OPS_NO_VENV=1` to
run against the current interpreter (e.g. inside CI where deps are preinstalled).
