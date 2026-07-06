# Setup & troubleshooting

## Full setup

```
python scripts/bootstrap.py
python scripts/jira.py setup --base-url "https://your-jira-host" --name default
python scripts/jira.py auth set-token --token-stdin
python scripts/jira.py auth test-auth
```

`bootstrap.py` is idempotent: it creates `<skill-root>/.venv`, installs
`assets/requirements.txt`, and runs a local health check. It prints the exact
interpreter path, but you should invoke everything through `scripts/jira.py`,
which auto re-execs into the venv.

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
