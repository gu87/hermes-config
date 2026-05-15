---
name: hermes-webui
description: Install, manage, and troubleshoot the Hermes Web UI (github.com/nesquena/hermes-webui) — a dark-themed browser interface with full CLI parity for Hermes Agent.
tags: [hermes, webui, dashboard, self-hosted]
category: hermes
agents: [hermes]
---

# Hermes Web UI — Setup & Operations

Web UI for [Hermes Agent](https://hermes-agent.nousresearch.com/), built by [nesquena](https://github.com/nesquena/hermes-webui). Three-panel layout, dark-themed, 1:1 CLI parity. Python + vanilla JS, no build step.

## Quick Install

```bash
cd ~
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui

# Bootstrap (auto-detects Hermes install, sets up venv, starts server)
python3 bootstrap.py

# Or direct shell launcher
./start.sh
```

## Daemon Management

Use `ctl.sh` for background operation:

```bash
./ctl.sh start              # background daemon, PID at ~/.hermes/webui.pid
./ctl.sh status             # PID, uptime, bound host/port, log path
./ctl.sh logs --lines 100   # tail ~/.hermes/webui.log
./ctl.sh restart
./ctl.sh stop
```

## Access

- **Local**: `http://localhost:8787` (default port)
- **Remote via SSH tunnel**: `ssh -N -L 8787:127.0.0.1:8787 user@server`
- **Password protect**: Set `HERMES_WEBUI_PASSWORD` env var

## Overrides

Set before starting:

| Env var | Default | Description |
|---------|---------|-------------|
| `HERMES_WEBUI_PORT` | `8787` | Port |
| `HERMES_WEBUI_HOST` | `127.0.0.1` | Bind address |
| `HERMES_WEBUI_PASSWORD` | (unset) | Enable auth |
| `HERMES_WEBUI_DEFAULT_MODEL` | `openai/gpt-5.4-mini` | Default model |
| `HERMES_WEBUI_AGENT_DIR` | auto | Path to hermes-agent |
| `HERMES_WEBUI_STATE_DIR` | `~/.hermes/webui` | Sessions & state |
| `HERMES_WEBUI_DEFAULT_WORKSPACE` | `~/workspace` | Default workspace |

## Docker

```bash
# Single container (agent in-process)
cp .env.docker.example .env
docker compose up -d
# http://localhost:8787

# Two-container (agent + WebUI separate)
docker compose -f docker-compose.two-container.yml up -d
```

See `docs/docker.md` for multi-container and failure modes.

## Features

- **Three-panel layout**: Left = sessions/nav, Center = chat, Right = workspace files
- **Model selection**: Switch models from bottom composer bar
- **Profile support**: Multiple agent profiles
- **Context ring**: Circular token usage indicator
- **Workspace browser**: File tree with inline preview
- **Session management**: Projects, tags, tool call cards
- **Tasks/Kanban/Skills/Memory tabs**: Same as CLI
- **Light/dark mode**: Toggle via settings

## Verification

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/
# Expected: 200

tail ~/.hermes/webui.log
```

## Pitfalls

- **bootstrap.py runs in foreground**: It prints `[bootstrap] Web UI is ready: http://localhost:8787` but stays attached. After it's up, immediately switch to daemon: `cd ~/hermes-webui && ./ctl.sh start` — this kills the bootstrap process and relaunches as a background daemon managed by `ctl.sh`.
- **Agent update notification**: First launch shows a yellow bar like "Agent (origin/main): 381 updates available". Can be ignored or clicked "Later". "Update Now" triggers in-place `git pull` on the agent repo.
- **Works with existing config**: Auto-detects `~/.hermes/config.yaml`, existing models, and workspaces. No additional setup needed.
- **Default bind is 127.0.0.1** (loopback). Use SSH tunnel for remote access: `ssh -N -L 8787:127.0.0.1:8787 user@server`.
- **Docker bind mounts**: Need correct UID/GID on macOS (host UID typically starts at 501). Set `UID=$(id -u)` in `.env`.
- **`HERMES_AUTO_INSTALL=1`** enables auto-install of agent deps (disabled by default).
- **No CAPTCHA/verification**: WebUI has no login screen unless `HERMES_WEBUI_PASSWORD` is set. Bind only to 127.0.0.1 if exposed without auth.
- **ctl.sh status shows "stopped" after bootstrap**: This is expected — `ctl.sh` tracks its own PID file. Run `./ctl.sh start` to switch to daemon mode; it will properly register.
- **Verification**: After starting, check `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/` returns `200`, then browse to see the three-panel layout (sidebar conversations, center chat with prompts, right workspace panel).

## UI Overview (first launch)

- **Left sidebar**: "Conversations" panel with `+` button, search bar, and vertical icon nav (Chat/Tasks/Kanban/Skills/Memory/Spaces/Settings/Logs)
- **Center**: Chat area with golden Hermes logo, "What can I help with?" heading, and 3 example prompt buttons
- **Right panel**: Workspace file browser (toggle with sidebar button)
- **Bottom composer**: Message input + model selector (default profile shown with "default" badge) + attach files + voice dictation + send button (disabled until text entered)
- **Dark theme** with golden accent. Light/dark toggle in Settings.
