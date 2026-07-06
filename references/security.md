# Security & credential handling

## Where the PAT lives

Resolution order when reading a token:

1. `JIRA_OPS_TOKEN` environment variable (for CI/automation; never logged)
2. OS secret store via `keyring` (if installed and a real backend is present)
3. Encrypted fallback file under the config dir:
   - Windows: DPAPI (`CryptProtectData`) via ctypes — user-scoped, no extra deps
   - POSIX: a `0600` file, base64-obfuscated (documented as not strongly encrypted)

The token is **never** written into the repo and **never** printed. `Authorization`
headers are redacted from error output.

## Config vs secrets

- Non-secret config: `<config-dir>/jira-ops/config.json`
- Secret fallback: `<config-dir>/jira-ops/secrets/<host>.token`
- `<config-dir>`:
  - Windows `%APPDATA%\jira-ops`
  - Linux/macOS `${XDG_CONFIG_HOME:-~/.config}/jira-ops`
  - Override via `JIRA_OPS_HOME`

## TLS & proxy (corporate networks)

- `verifyTls` stays `true` by default. Do not disable it as a shortcut.
- Point `caCertPath` at your corporate CA bundle, or set `REQUESTS_CA_BUNDLE`.
- Set `proxy` in config, or use standard `HTTPS_PROXY` / `NO_PROXY` env vars.
- A `tls` error (exit 14) means the CA chain is not trusted — fix the CA bundle.

## Rotating a token

```
python scripts/jira.py auth clear-token
python scripts/jira.py auth set-token --token-stdin
python scripts/jira.py auth test-auth
```

Rotate immediately any PAT that has been pasted into chat, a ticket, or shell
history.

## Providing the token without a prompt

```
# stdin (preferred for automation)
"YOUR_PAT" | python scripts/jira.py auth set-token --token-stdin

# environment (session-scoped; avoid persisting)
$env:JIRA_OPS_TOKEN = "YOUR_PAT"; python scripts/jira.py auth test-auth
```
