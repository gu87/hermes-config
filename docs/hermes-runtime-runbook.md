# Hermes Runtime Runbook

Last updated: 2026-05-18

This is the operational runbook for Gu's local Hermes setup after the Hermes Agent 0.14 upgrade. It records where the system lives, how to check health, and how to restart services without relying on memory.

## Paths

| Item | Path |
|------|------|
| Config repository | `/Users/gu/.hermes` |
| Hermes Agent production source | `/Users/gu/.Hermes/hermes-agent` |
| Hermes Agent virtualenv Python | `/Users/gu/.Hermes/hermes-agent/venv/bin/python` |
| WebUI source | `/Users/gu/hermes-webui` |
| WebUI state | `/Users/gu/.hermes/webui` |
| OpenChronicle source | `/Users/gu/OpenChronicle` |
| OpenChronicle CLI | `/Users/gu/.local/bin/openchronicle` |

## Services

| Service | launchd label | Purpose | Notes |
|---------|---------------|---------|-------|
| WebUI | `ai.hermes.webui` | Hermes WebUI | `http://127.0.0.1:8787/` |
| Main gateway | `ai.hermes.gateway-piero` | Feishu-facing main profile | Profile: `piero` |
| Technical gateway | `ai.hermes.gateway-nesta` | Technical profile | Profile: `nesta` |
| Review/API gateway | `ai.hermes.gateway-ambrosini` | Review profile and API server | Profile: `ambrosini` |
| OpenChronicle | `com.openchronicle.daemon` | Local memory/search MCP backend | MCP URL: `http://127.0.0.1:8742/mcp` |

## Ports

| Port | Service |
|------|---------|
| `8787` | Hermes WebUI |
| `8742` | OpenChronicle MCP |
| `8642` | Hermes API server, currently owned by the active API gateway profile |

## Health Checks

```bash
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway list
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main mcp test openchronicle
/Users/gu/.local/bin/openchronicle status
curl -fsS http://127.0.0.1:8787/ >/dev/null
```

Expected healthy state:

- `piero`, `nesta`, and `ambrosini` gateways are running.
- Feishu is connected for active Feishu-facing profiles.
- OpenChronicle reports running/healthy.
- Hermes MCP test for `openchronicle` connects and discovers tools.
- WebUI GET succeeds and returns content on `127.0.0.1:8787`.

## Restart Commands

Restart gateways through Hermes CLI:

```bash
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile piero gateway restart
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile nesta gateway restart
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile ambrosini gateway restart
```

Restart launchd services when the CLI path is not enough:

```bash
launchctl kickstart -k gui/$(id -u)/ai.hermes.webui
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway-piero
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway-nesta
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway-ambrosini
launchctl kickstart -k gui/$(id -u)/com.openchronicle.daemon
```

## Logs

| Service | Log path |
|---------|----------|
| WebUI stdout | `/Users/gu/.hermes/webui.log` |
| WebUI stderr | `/Users/gu/.hermes/webui.error.log` |
| Piero gateway | `/Users/gu/.hermes/profiles/piero/logs/gateway.log` |
| Nesta gateway | `/Users/gu/.hermes/profiles/nesta/logs/gateway.log` |
| Ambrosini gateway | `/Users/gu/.hermes/profiles/ambrosini/logs/gateway.log` |
| OpenChronicle launchd stdout | `/Users/gu/.openchronicle/logs/launchd.out.log` |
| OpenChronicle launchd stderr | `/Users/gu/.openchronicle/logs/launchd.err.log` |

## Upgrade And Rollback

The latest upgrade record is `/Users/gu/.hermes/docs/hermes-agent-upgrade-2026-05-18.md`.

Current production Hermes Agent commit at the time of that record:

```text
4ba3e9ca856953bcada786854667cc013763fc19
```

Pre-upgrade rollback branch:

```text
codex/hermes-upgrade-backup-20260518
```

Rollback is destructive and requires explicit confirmation before running. Use the commands in the upgrade record, then restart gateways.

## Operating Notes

- Do not push local Hermes Agent customizations to upstream `origin`.
- If publishing Hermes Agent changes, use the user's fork remote after explicit confirmation.
- Do not treat memory as runtime truth. For service status, run the health checks above.
