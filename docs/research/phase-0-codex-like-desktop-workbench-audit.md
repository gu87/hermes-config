# Phase 0 Audit: Codex-like Hermes Desktop Workbench

Date: 2026-06-03
Branch: `feature/codex-like-desktop-workbench`
Scope: documentation-only Phase 0 audit. No business/runtime code changes.

## Executive Conclusion

Hermes should not begin this work by building another chat page or forking a full desktop distribution. The right first product is a local agent workbench: project/session/task navigation on the left, live thread and agent trace in the center, workspace files/artifacts/preview/logs on the right, and a status bar that makes the runtime visible.

The repository already contains several pieces that make this feasible:

- Gateway/API server already exposes OpenAI-compatible endpoints plus structured run endpoints.
- Managed agent modules already model workspace, session, session binding, policy, routing, review, and gateway entry adapters.
- Codex app-server transport exists as an optional runtime path and already separates wire protocol, session adapter, event projection, approval bridging, and runtime retirement concerns.
- Feishu session binding work gives Hermes a stronger cross-entrypoint session model than a desktop-only app normally has.
- Existing research documents already compared official Hermes Desktop, community Hermes Desktop, and Feishu multi-agent entry patterns.

The main gap is not "can Hermes run agents"; the gap is a product/control-plane contract that turns existing runtime events, sessions, tasks, and files into a coherent desktop workbench.

## Current Repository Signals

### Existing Runtime And Entrypoints

Observed files:

- `hermes-agent/gateway/platforms/api_server.py`
- `hermes-agent/gateway/platforms/feishu.py`
- `hermes-agent/gateway/platforms/discord.py`
- `hermes-agent/agent/managed_agents/gateway.py`
- `hermes-agent/agent/managed_agents/entry_adapter.py`
- `hermes-agent/agent/managed_agents/feishu_entry_adapter.py`
- `hermes-agent/agent/managed_agents/session_binding.py`

The API server already documents:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/approval`
- `POST /v1/runs/{run_id}/stop`
- `GET /health`
- `GET /health/detailed`

This is already close to the backend contract a desktop workbench needs. The missing part is a stable desktop-facing projection layer: session summaries, run events, task/run linkage, artifact references, file diffs, and approval state.

### Existing Workspace/Session Model

Observed files:

- `hermes-agent/agent/managed_agents/workspace.py`
- `hermes-agent/agent/managed_agents/session.py`
- `hermes-agent/agent/managed_agents/session_binding.py`

Current model:

- `Workspace` has `workspace_id`, `name`, `entrypoint`, `external_source_id`.
- `Session` has `session_id`, `workspace_id`, `entrypoint`, `external_channel_id`, `external_thread_id`.
- `SessionBindingValue` maps external entrypoint/channel/thread to `workspace_id` and `session_id`, with source metadata: `card`, `thread`, `alias`, `default`.

Implication: Hermes already has a better foundation than a single-desktop-session app. The desktop should not replace this model with an isolated Electron session table. It should read and extend this model.

### Existing Codex Runtime Work

Observed files:

- `hermes-agent/agent/transports/codex_app_server.py`
- `hermes-agent/agent/transports/codex_app_server_session.py`
- `hermes-agent/agent/transports/codex_event_projector.py`
- `hermes-agent/agent/codex_runtime.py`

The Codex transport is intentionally optional and already shaped around:

- `codex app-server` JSON-RPC over stdio.
- `initialize`, `thread/start`, `turn/start`, `turn/completed`.
- One Codex thread per Hermes session.
- Approval bridging for file changes and exec.
- Event projection into Hermes display/messages.
- Runtime retirement when a subprocess is wedged or auth-broken.

Implication: the desktop workbench should not start by reimplementing Codex-like execution. It should first define how runtime events are surfaced and controlled.

## Prior Research Synthesis

### Official Hermes Desktop Lessons

Existing research in `docs/research/official-hermes-desktop-codex-like-product-audit.md` concluded that the official desktop is Codex.app-like because it treats chat as an agent runtime console, not as a generic messaging page.

High-value patterns to adopt:

- CWD-as-project instead of heavy project management.
- Stored session id separate from runtime session id.
- Optimistic send followed by runtime session creation/resume.
- Thread trace with reasoning, tool blocks, subagent events, and branch/fork actions.
- Right rail for files, terminal, preview, and artifacts.
- Status bar for gateway, running timer, model/context, agents, cron, version.
- Command Center for sessions, logs, usage, system state, and navigation.

Do not copy:

- Release/installer bootstrap complexity.
- Official backend contract wholesale.
- Decorative polish before workbench fundamentals.

### Community Hermes Desktop Lessons

Existing research in `docs/research/community-hermes-desktop-implementation-audit.md` concluded that the community desktop is useful as a component/reference library, but not as the full product base.

Useful pieces:

- Electron + React + preload IPC pattern.
- Chat input, attachment chips, context gauge/folder chip.
- Session cache and session search.
- Kanban task/run/event data shape.
- Gateway status and config health views.

Risks:

- Main IA is function-navigation, not runtime workbench.
- Sessions and Kanban are separate pages, not part of the persistent task context.
- Tool progress is string-based, not structured trace.
- There is no branchable thread or stored/runtime session split.
- Installer/remote/provider complexity would distract Phase 1.

### Feishu Entry Lessons

Existing research in `docs/research/feishu-agent-entry-reference-comparison.md` concluded that Hermes can stay Feishu-first.

For desktop planning, the important point is broader: Hermes sessions must be cross-entrypoint. A Feishu thread, a CLI run, a desktop session, and a future mac app entry should be able to refer to the same workspace/session/task lineage.

This means desktop workbench ids should not be invented in isolation. They should align with:

- `workspace_id`
- `session_id`
- `external_channel_id`
- `external_thread_id`
- `task_id`
- `run_id`

## Phase 0 Risk Register

| Risk | Why It Matters | Phase 0 Recommendation |
| --- | --- | --- |
| Building a chat app instead of a workbench | Would miss the Codex.app value: observe, control, inspect, and recover agent work | Make three-pane workbench the primary IA |
| Forking a desktop repo too early | Imports installer/updater/backend assumptions before Hermes contract is clear | Prototype contract first, then choose UI implementation |
| New desktop-only session model | Would fracture Feishu/CLI/Gateway continuity | Reuse managed `Workspace`, `Session`, and `SessionBinding` concepts |
| String-only streaming events | Cannot render useful tool trace, approvals, files, subagents, retries | Standardize structured run event schema before UI work |
| Task and session treated as the same thing | Hermes already has task/run pipeline; collapsing it loses control-plane value | Keep session/thread for conversation, task/run for execution |
| Right rail postponed too long | Without files/artifacts/logs/preview it remains a chat UI | MVP must include at least one inspectable workspace rail |
| Permissions hidden inside backend | Desktop users need to see what an agent is allowed to do | Surface approval and permission state as first-class UI events |

## Minimum Product Model

Recommended entities:

| Entity | Meaning | Existing Anchor |
| --- | --- | --- |
| Workspace | Local project or external source namespace | `managed_agents/workspace.py` |
| Session | User-visible conversation/thread history | `managed_agents/session.py` |
| Runtime Session | Live backend execution binding | API server/run runtime |
| Task | Goal or work item | task card / kanban concepts |
| Run | One execution attempt by one or more agents | `/v1/runs` |
| Agent | Named profile or runtime participant | managed agents registry |
| Tool Event | Structured evidence of action | run events, Codex projector |
| Artifact | Output file, preview URL, log, diff, report | workspace/files/run outputs |

The key split:

- `stored_session_id`: stable history and URL/list identity.
- `runtime_session_id`: live execution instance, reconnectable/replaceable.
- `task_id`: user/business objective.
- `run_id`: one concrete execution attempt.

## Phase 0 Acceptance Criteria

Phase 0 is complete when:

1. Work branch exists and is not `main`/`master`.
2. No business/runtime source code has been modified.
3. Audit documents identify current repository capabilities and gaps.
4. Roadmap defines a minimal implementation path.
5. ADR records the product/architecture decision before coding starts.

