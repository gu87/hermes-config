# Hermes Agent Upgrade Record - 2026-05-18

## Summary

Hermes Agent production source was upgraded to upstream Hermes 0.14 while preserving the local Hermes 2.8 custom agent behavior.

Production repository:

- Path: `/Users/gu/.Hermes/hermes-agent`
- Branch: `main`
- Current commit: `4ba3e9ca856953bcada786854667cc013763fc19`
- Commit title: `Merge upstream Hermes 0.14 with local agent customizations`

Pre-upgrade rollback branch:

- Branch: `codex/hermes-upgrade-backup-20260518`
- Commit: `41165d82494657c136c67e0a2524d220dce3567a`

## Preserved Local Behavior

- `TaskCard`
- `EventLog`
- `ReviewGate`
- `AgentRouter`
- Named `agent_id` delegation
- Memory boundary rules
- Local prompt and delegation guidance customizations

## Upstream Changes Adopted

- Modular `run_agent.py` forwarding into `agent/*` modules
- Hermes 0.14 provider, gateway, MCP, dashboard, tool, and test updates
- Updated `uv.lock` for the new `pyproject.toml`

## Verification Completed

Source verification:

- `uv lock --check`
- `uv run --locked --extra dev python -c "import run_agent; print('AIAgent', hasattr(run_agent, 'AIAgent'))"`
- Focused pytest smoke covering delegate, router, session event log, memory schema, provider priority

Runtime verification:

- Hermes WebUI reachable at `http://127.0.0.1:8787/`
- `piero` gateway running and Feishu connected
- `ambrosini` gateway running, Feishu connected, API server connected
- `nesta` gateway running and Feishu connected
- User confirmed Feishu replies are normal
- OpenChronicle MCP repaired and reachable at `http://127.0.0.1:8742/mcp`
- `hermes mcp test openchronicle` connected and discovered 8 tools

## OpenChronicle Runtime Fix

Root cause: OpenChronicle daemon was stopped, so Hermes could not reach `127.0.0.1:8742`.

Fix:

- Started OpenChronicle daemon
- Added user LaunchAgent: `/Users/gu/Library/LaunchAgents/com.openchronicle.daemon.plist`

Validation:

- OpenChronicle status: running and healthy
- Port `127.0.0.1:8742` listening
- Hermes MCP test passed

## Rollback

Only run rollback after explicit confirmation:

```bash
cd /Users/gu/.Hermes/hermes-agent
git reset --hard codex/hermes-upgrade-backup-20260518
```

After rollback, restart gateways:

```bash
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile piero gateway restart
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile ambrosini gateway restart
/Users/gu/.Hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile nesta gateway restart
```

## Notes

- No push to upstream `origin` should be done for this local customization branch.
- If publishing, push to the user's fork remote: `fork`.
- Pre-existing untracked image and temp files in `/Users/gu/.Hermes/hermes-agent` were left untouched.
