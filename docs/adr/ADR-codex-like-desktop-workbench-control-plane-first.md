# ADR: Build A Control-plane-first Codex-like Desktop Workbench

Date: 2026-06-03
Status: Proposed

## Context

Hermes already has a local multi-agent runtime, gateway entrypoints, Feishu integration, managed agent routing, workspace/session/session-binding models, task/run concepts, and an optional Codex app-server transport.

The requested direction is a Codex-like desktop workbench. Existing research shows that the Codex-like quality comes from the product model, not from merely using Electron:

- Work is scoped to a workspace/cwd.
- Session history is persistent and resumable.
- Runtime execution is live and inspectable.
- Tools, approvals, logs, files, diffs, artifacts, and subagents are visible.
- The app behaves like an agent control plane, not a chat wrapper.

## Decision

Hermes Desktop should be designed as a control-plane-first workbench.

The initial implementation should prioritize:

1. Three-pane workbench IA: sessions/tasks/workspaces, thread/run trace, workspace rail.
2. Structured runtime events as the UI contract.
3. Distinct ids for session, runtime session, task, and run.
4. Reuse of existing Hermes workspace/session/session-binding concepts.
5. First-class rendering for tools, approvals, artifacts, logs, and multi-agent state.

The implementation should not start by forking a full desktop distribution or by building a generic chat UI.

## Rationale

Hermes's differentiator is not a single-agent chat interface. It is local orchestration across named agents, entrypoints, approvals, tasks, and runtime evidence.

A chat-first design would hide most of that value. A control-plane-first design makes Hermes's strengths visible and operable:

- Users can see what is running.
- Users can inspect why a result happened.
- Users can approve or stop risky actions.
- Users can recover failed preview/log/tool states.
- Users can connect Feishu, CLI, and desktop work to the same session/task lineage.

## Consequences

Positive:

- Aligns with Codex.app-like user experience.
- Preserves Hermes's existing architecture instead of replacing it.
- Keeps Feishu and desktop session continuity possible.
- Avoids premature installer/provider/updater complexity.
- Creates a stable backend contract before UI investment.

Negative:

- Requires a structured event projection layer before the UI feels complete.
- More upfront modeling than a simple chat screen.
- Some existing community desktop components can only be reused selectively.

## Implementation Constraints

- Phase 0 produces documentation only.
- No business/runtime code changes before the contract is accepted.
- Desktop ids must not conflict with existing Hermes managed agent ids.
- OpenAI-compatible chat endpoints remain compatibility surfaces, not the primary desktop contract.
- Feishu gateway/session binding should be extended, not replaced.

## Alternatives Considered

### Fork official Hermes Desktop

Rejected for Phase 1. It has strong IA and UX references, but also includes release bootstrap, installer/update concerns, and a backend contract that should not be copied directly into this Hermes deployment.

### Fork community Hermes Desktop

Rejected as full base. It is useful as a component and IPC reference, but its information architecture is a function-navigation dashboard rather than a runtime workbench.

### Build a simple chat page first

Rejected. It would be faster initially but would postpone the hard and valuable parts: runtime trace, task/run linkage, workspace inspection, approvals, and multi-agent visibility.

### Make Feishu the only UI

Rejected for this workbench. Feishu remains valuable as the primary IM entrypoint, but desktop is better suited for file, diff, preview, logs, and long-running runtime inspection.

## Follow-up Decision Needed

Before implementation begins, decide whether Phase 1 should expose the desktop contract through:

1. Existing `/v1/runs` endpoints plus schema tightening.
2. A new desktop projection API.
3. A local IPC adapter that reads runtime/event stores directly.

Recommendation: start with option 1 and add option 2 only if the existing run event stream cannot represent required desktop events cleanly.

