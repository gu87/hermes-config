# Hermes Desktop — Project Context

<!--
  PROJECT.md — Hermes 项目上下文文件
  这是 Hermes 接续项目时第一个读取的文件。
  保持精简。当前状态进 state，决策引用进 active_decisions，详情进 ADR/Wiki。

  维护规则：
  - state: 每条 key-value 必须带 source + last_confirmed + status
  - state 变更: 旧条目 status → superseded，新条目 ADD（ADD-only）
  - active_decisions: 只引用 ADR，不复制内容
  - recent: 快照区，最多保留 3 条，旧条目直接移除（不标记 superseded）
    完整历史以 session/OpenChronicle/Obsidian 为准
  - risks: 有则填，无则留空
-->

## Project

- **slug**: hermes-desktop
- **name**: Hermes Desktop
- **repo**: /Users/gu/.hermes
- **description**: Hermes 桌面客户端 — Codex-like Agent Coding Workbench。第一阶段（v0.1）做最小闭环：Project → Task Thread → Agent Run → Timeline → Changed Files → Review。

## Current State

| key | value | source | last_confirmed | status |
|-----|-------|--------|:--:|:--:|
| git.branch | main | cli:git-branch | 2026-06-08 | current |
| git.last_commit | c084eb3 | cli:git-log | 2026-06-08 | current |
| deployment.target | local-only（尚未部署） | ADR-codex-like-agent-workbench | 2026-06-03 | current |
| phase.active | v0.1 — 最小闭环 | ADR-codex-like-agent-workbench | 2026-06-03 | superseded |
| memory.project_context | ADR 已通过，示例 PROJECT.md 已创建 | ADR-project-context-layer | 2026-06-08 | current |
| memory.closeout_check | v1 已落地（verification-loop + orchestration-closeout） | session-2026-06-08/closeout | 2026-06-08 | current |
| phase.active | v0.1 — dogfood 观察期 | session-2026-06-08/project-context-phase2-closeout | 2026-06-08 | current |

## Active Decisions

| ADR | Title | Status |
|-----|-------|:--:|
| ADR-codex-like-agent-workbench | Hermes Desktop 定位为 Codex-like Agent Coding Workbench | current |
| ADR-codex-like-desktop-workbench-control-plane-first | 桌面工作台控制面优先 | current |
| ADR-verify-task-dual-status-validation | verify-task.py 双层 Status 校验 | current |
| ADR-closeout-memory-check | Closeout Memory Check — ADD-only + Provenance | current |
| ADR-project-context-layer | Project Context Layer — PROJECT.md 最小设计 | current |

## Recent Activity

| Date | Task | Outcome | Source |
|------|------|---------|--------|
| 2026-06-08 | PROJECT.md 最小设计 + 示例创建 | ADR 通过，hermes-desktop 第一个 PROJECT.md 已创建 | session-2026-06-08/project-context-layer |
| 2026-06-08 | Closeout Memory Check v1 最小实现 | 完成 — verification-loop + orchestration-closeout 已更新 | session-2026-06-08/closeout |
| 2026-06-08 | Agent Memory Systems 深度研究 | 完成 — mem0/Zep/Graphiti/Letta 研究报告 + ADR 落地 | session-2026-06-08/research |

## Open Risks

| ID | Description | Severity | Source | Status |
|----|-------------|:--:|--------|:--:|
| RISK-001 | v0.1 尚未接入真实 API，当前为设计/文档阶段 | low | ADR-codex-like-agent-workbench | active |
| RISK-002 | 大量 uncommitted 变更（config/skills/memories），需要 staging plan | medium | cli:git-status | active |
