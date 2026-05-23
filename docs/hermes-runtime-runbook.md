# Hermes Runtime Runbook

Last updated: 2026-05-23

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
| Main gateway | `ai.hermes.gateway` | Single Feishu-facing entrypoint | Profile: default / 马尔蒂尼 |
| Profile gateway | `ai.hermes.gateway-maldini` | Disabled legacy 马尔蒂尼 profile gateway | Keep profile data for rollback; do not run alongside default because it uses the same Feishu app_id |
| Profile gateway | `ai.hermes.gateway-nesta` | Disabled technical profile gateway | Agent 编制保留；不再常驻独立飞书入口 |
| Profile gateway | `ai.hermes.gateway-piero` | Disabled planning profile gateway | Agent 编制保留；不再常驻独立飞书入口 |
| Profile gateway | `ai.hermes.gateway-ambrosini` | Disabled review profile gateway | Agent 编制保留；不再常驻独立飞书入口 |
| OpenChronicle | `com.openchronicle.daemon` | Local memory/search MCP backend | MCP URL: `http://127.0.0.1:8742/mcp` |

## Ports

| Port | Service |
|------|---------|
| `8787` | Hermes WebUI |
| `8742` | OpenChronicle MCP |
| `8642` | Hermes API server, owned by the default gateway |

## Health Checks

```bash
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway list
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main mcp test openchronicle
/Users/gu/.local/bin/openchronicle status
curl -fsS http://127.0.0.1:8787/ >/dev/null
```

Expected healthy state:

- Only `ai.hermes.gateway` is running as the Feishu entrypoint.
- `ai.hermes.gateway-maldini`, `ai.hermes.gateway-nesta`, `ai.hermes.gateway-piero`, and `ai.hermes.gateway-ambrosini` are disabled unless explicitly re-enabled for rollback/testing.
- Feishu is connected for the default gateway.
- OpenChronicle reports running/healthy.
- Hermes MCP test for `openchronicle` connects and discovers tools.
- WebUI GET succeeds and returns content on `127.0.0.1:8787`.

## Restart Commands

Restart gateways through Hermes CLI:

```bash
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway restart
```

Restart launchd services when the CLI path is not enough:

```bash
launchctl kickstart -k gui/$(id -u)/ai.hermes.webui
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway
launchctl kickstart -k gui/$(id -u)/com.openchronicle.daemon
```

## Logs

| Service | Log path |
|---------|----------|
| WebUI stdout | `/Users/gu/.hermes/webui.log` |
| WebUI stderr | `/Users/gu/.hermes/webui.error.log` |
| Main gateway | `/Users/gu/.hermes/logs/gateway.log` |
| Disabled Maldini profile gateway | `/Users/gu/.hermes/profiles/maldini/logs/gateway.log` |
| Disabled Piero profile gateway | `/Users/gu/.hermes/profiles/piero/logs/gateway.log` |
| Disabled Nesta profile gateway | `/Users/gu/.hermes/profiles/nesta/logs/gateway.log` |
| Disabled Ambrosini profile gateway | `/Users/gu/.hermes/profiles/ambrosini/logs/gateway.log` |
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
- Current operating model: one Feishu entrypoint, many internal managed agents. Keep expert profiles and agent registry entries, but do not keep separate Feishu profile gateways running by default.
