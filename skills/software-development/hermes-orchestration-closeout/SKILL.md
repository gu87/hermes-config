---
name: hermes-orchestration-closeout
description: "Structured closeout protocol for Hermes multi-Agent delegation results."
version: 1.1.0
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

## Memory Check (v1)

在 Closeout Packet 完成后，检查本次多 Agent 任务是否产生值得保留的长期知识。

**触发条件**：

当 closeout 满足以下任一条件时，加载 `verification-loop` skill 执行 Memory Check：
- `Classification: ready` 且 drift signals ≥ 1
- `Classification: needs-review` 且有关键决策产出
- 任务涉及 Agent/model/skill/config 文件的变更

**输出**：

| 状态 | 含义 | 后续动作 |
|------|------|----------|
| `No Memory Update` | 无需记录 | Silent pass。不需要向人汇报 |
| `Knowledge Update Suggested` | 有值得写入 MEMORY.md 的内容 | 向人展示 Memory Candidate，**不自动写入** |
| `ADR Update Suggested` | 有值得记录为 ADR 的决策 | 向人展示 Memory Candidate + ADR 建议，**不自动写入** |
| `Project State Update Suggested` | 有值得更新 PROJECT.md 的项目状态变更 | 向人展示 Candidate（含 State key / Old value / New value），**不自动写入。等待 user confirmation** |

**子 Agent 权限**：

- ✅ 子 Agent 在 outbox 中可以附带 `memory_candidate` 字段，格式同 verification-loop 中的 Memory Candidate
- ❌ 子 Agent 不允许在任何情况下写入 MEMORY.md、USER.md、Obsidian Wiki、ADR
- ⚠️ 主 Agent（Hermes）仍必须执行去重检查 + 向人汇报，不能直接信任子 Agent 的 Candidate

**默认行为**：

如果没有触发信号，Memory Check 默认输出 `No Memory Update`，不在 closeout 中产生额外输出。

---

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
