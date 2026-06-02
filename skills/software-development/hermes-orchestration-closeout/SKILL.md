---
name: hermes-orchestration-closeout
description: "Structured closeout protocol for Hermes multi-Agent delegation results."
version: 1.0.0
author: Hermes Agent (adapted from withkynam/vibecode-pro-max-kit orchestration protocol)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, delegation, closeout, subagent, review, risk]
    related_skills: [hermes-subagent-delegation, subagent-driven-development, requesting-code-review]
agents:
- hermes-internal
- codex
- ambrosini
---

# Hermes Orchestration Closeout

Use this skill when a Hermes task involved one or more delegated Agents and the main session needs to decide whether the work is complete, needs review, needs more context, or should be returned to planning.

This is a Hermes-native adaptation of the status and closeout pieces from `withkynam/vibecode-pro-max-kit`. It does not introduce RIPER-5 mode ownership.

## Required Subagent Status

Treat every delegated result as one of:

- `DONE` - task completed and verified within its stated scope.
- `DONE_WITH_CONCERNS` - task completed but has material caveats.
- `BLOCKED` - task cannot proceed without missing input, access, or external state.
- `NEEDS_CONTEXT` - task was under-specified or lacks required files/logs/config.

Rules:

- Do not ignore `BLOCKED` or `NEEDS_CONTEXT`.
- Do not retry the exact same blocked approach three times.
- Treat correctness/security concerns as action items, not as notes.
- Treat observational concerns as notes only when they do not affect correctness, risk, or user intent.

## Closeout Packet

At the end of non-trivial multi-Agent work, produce:

```markdown
## Closeout

Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Classification: ready | needs-review | needs-plan-reconciliation | blocked

Finished:
- ...

Verified:
- ...

Unverified:
- ...

Concerns:
- ...

Next valid state:
- commit | review | test | ask-user | return-to-plan | continue-implementation
```

## Drift Signals

Increase closeout strictness when any of these are true:

- 5+ files changed.
- Agent/model/skill/config files changed.
- Runtime behavior changed.
- User-facing WebUI changed.
- External credentials, tokens, provider routing, or fallback logic changed.
- Any Agent result conflicts with another Agent result.

With two or more signals, recommend review before commit. With three or more signals, recommend an explicit validation checklist.

## Hermes Mapping

- `hermes-internal`: use for technical decomposition and closeout synthesis.
- `codex`: use for architecture/code-review closeout.
- `ambrosini`: use for high-risk acceptance gates.
- `deepseek-tui`: use for small verification scans or log checks, not final arbitration.
