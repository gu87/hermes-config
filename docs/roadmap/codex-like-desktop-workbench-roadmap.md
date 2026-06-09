# Codex-like Hermes Desktop Workbench Roadmap

Date: 2026-06-03
Branch: `feature/codex-like-desktop-workbench`
Status: Phase 0 documentation plan

## Guiding Principle

Build the smallest useful agent workbench first.

Do not begin with installation, theming, provider management, remote SSH, voice, or a full desktop distribution. Begin with the loop the user actually needs:

1. Pick a workspace/session/task.
2. Ask Hermes to do work.
3. Watch the agent trace.
4. Inspect files/logs/artifacts.
5. Approve/deny risky actions.
6. Resume, branch, or dispatch the next run.

## Non-goals For Initial Implementation

- No main/master code changes.
- No direct business logic changes before the workbench contract is decided.
- No full fork of official/community desktop as the first step.
- No provider/OAuth/updater/installer scope in Phase 1.
- No Discord-first pivot.
- No replacement of Feishu gateway/session binding.
- No new agent execution engine.

## Phase 0: Audit And Decisions

Goal: establish the product model and implementation constraints before coding.

Deliverables:

- `docs/research/phase-0-codex-like-desktop-workbench-audit.md`
- `docs/roadmap/codex-like-desktop-workbench-roadmap.md`
- `docs/adr/ADR-codex-like-desktop-workbench-control-plane-first.md`

Validation:

- `git status --short --branch` confirms branch is `feature/codex-like-desktop-workbench`.
- `git diff --name-only` contains only allowed doc paths.

## Phase 1: Desktop-facing Runtime Contract

Goal: define a stable contract for UI before building UI.

Recommended outputs:

- Documented event schema:
  - `run.started`
  - `run.status`
  - `message.delta`
  - `reasoning.delta`
  - `tool.started`
  - `tool.progress`
  - `tool.completed`
  - `tool.failed`
  - `approval.requested`
  - `approval.resolved`
  - `agent.spawned`
  - `agent.progress`
  - `agent.completed`
  - `artifact.created`
  - `run.completed`
  - `run.failed`
- Session summary shape.
- Session snapshot shape.
- Task summary/detail shape.
- Artifact reference shape.
- Permission/approval shape.

Implementation stance:

- Prefer adapting existing `/v1/runs` and `/v1/runs/{run_id}/events`.
- Add a desktop projection endpoint only if existing run events cannot provide enough structure.
- Keep OpenAI-compatible chat endpoints as compatibility, not the primary workbench contract.

Validation:

- A fixture JSON file can represent one full run with message, reasoning, tool, approval, artifact, and completion events.
- A small read-only script or test can consume the fixture and validate schema.

## Phase 2: Local Workbench Shell MVP

Goal: make the first screen a usable workbench, not a landing page or feature hub.

Minimum layout:

```text
┌──────────────┬──────────────────────────────┬─────────────────────┐
│ Sessions     │ Thread / Run Trace            │ Workspace Rail       │
│ Tasks        │ Composer                      │ Files / Logs / Output │
│ Workspaces   │ Tool Blocks / Approvals       │                     │
└──────────────┴──────────────────────────────┴─────────────────────┘
Status: gateway | model | running | context | branch | cwd
```

MVP capabilities:

- List local workspace/session summaries.
- Create a new session in a cwd.
- Submit a prompt and receive live run events.
- Render assistant message streaming.
- Render tool blocks as compact rows with expandable details.
- Render approval request and resolution state.
- Show gateway health and current running timer.
- Show at least one workspace rail: files, logs, or artifacts.

Validation:

- Start local dev server.
- Open with the in-app browser.
- Verify empty state, prompt submission, streaming event rendering, and status bar at desktop and narrow widths.

## Phase 3: Session, Task, And Run Integration

Goal: connect the workbench to Hermes's stronger task/run model.

Capabilities:

- Left rail toggles between Sessions and Tasks.
- Task card opens linked session/run trace.
- Task detail shows latest run, retries, assignee agent, status, result, and artifacts.
- Manual dispatch from task detail.
- Resume historical session by stored id before attaching runtime.
- Preserve Feishu/CLI/mac app entrypoint metadata in session detail.

Validation:

- Create or load sample task.
- Dispatch once.
- Confirm `task_id`, `run_id`, and `session_id` remain distinct in UI and data.

## Phase 4: Workspace Rail And Preview Loop

Goal: make agent outputs inspectable and repairable.

Capabilities:

- File tree bound to current `cwd`/workspace.
- Changed-file list per run.
- Diff or file preview for tool-created artifacts.
- Logs panel scoped to current run/gateway.
- Optional preview URL panel for H5/web artifacts.
- "Send logs to agent" action for preview/server failures.

Validation:

- Run a task that writes a harmless fixture file in a test workspace.
- Verify changed file appears in run trace and rail.
- Verify logs/artifact can be inserted into a follow-up prompt.

## Phase 5: Multi-agent Visibility

Goal: make Hermes's multi-agent advantage visible.

Capabilities:

- Agents overlay with current spawn tree.
- Agent fleet view: idle/running/failed/recent.
- Per-agent run duration, model, tools, permissions, and last event.
- Review/gate decisions shown inline with task/run.
- Failure reroute and retry history visible.

Validation:

- Simulate or run a task involving primary + reviewer/gate.
- Confirm user can understand which agent did what and why the run status changed.

## Phase 6: Feishu/Desktop Continuity

Goal: let Feishu and desktop observe the same work rather than acting as separate products.

Capabilities:

- Feishu thread session appears in desktop session list.
- Desktop-created session can expose entrypoint metadata for Feishu binding later.
- Approval state is consistent between Feishu card and desktop workbench where applicable.
- Thread-scoped sessions are displayed as first-class sessions.

Validation:

- Use a stored `SessionBindingValue` fixture or live Feishu session.
- Confirm desktop resolves and displays the correct workspace/session/thread metadata.

## Phase 7: Packaging And Distribution

Goal: package only after the local workbench loop is useful.

Capabilities:

- Local app startup command.
- Basic settings for Hermes home, gateway URL, and runtime health.
- Build command.
- Optional signing/updater later.

Validation:

- Fresh local run on the same machine can connect to existing Hermes runtime without reconfiguring secrets.

## Recommended Immediate Next Step

After Phase 0, do Phase 1 only: define and validate the desktop-facing runtime event schema using fixtures and existing `/v1/runs` behavior. This keeps the next step small and prevents UI work from guessing the backend contract.

