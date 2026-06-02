# Hermes v2.8.1 Phase 0 — Agent Sync Audit

> 执行时间：2026-06-01T22:20 CST
> 声明：只读审计，未修改任何文件

---

## 1. 审计范围

| # | 文件 | 角色 | 路径 |
|---|------|------|------|
| A | **source** | 源码权威定义 | `hermes-agent/configs/managed_agents/agents.yaml` |
| B | **mirror** | 运维副本 | `config/managed-agents.yaml` |
| C | **registry** | 运行时注册表 | `config/agent-registry.json` |

---

## 2. Agent 存在性对比

| Agent ID | A (source) | B (mirror) | C (registry) | 结论 |
|----------|-----------|-----------|-------------|------|
| hermes-internal | ✅ | ✅ | ✅ | 一致 |
| claude | ✅ | ✅ | ✅ | ⚠️ 字段不一致（见 §4） |
| deepseek-tui | ✅ | ✅ | ✅ | ⚠️ 字段不一致（见 §4） |
| **opencode** | ✅ | ❌ **缺失** | ✅ | 🔴 mirror 缺少 |
| codex | ✅ | ✅ | ✅ | 一致 |
| intelligence | ✅ | ✅ | ✅ | 一致 |
| pirlo | ✅ | ✅ | ✅ | 一致 |
| designer | ✅ | ✅ | ✅ | 一致 |
| agent-tars | ✅ | ✅ | ✅ | 一致 |
| ambrosini | ✅ | ✅ | ✅ | 一致 |
| **总计** | **10** | **9** | **10** | |

---

## 3. 三份清单

### 3.1 三边都存在的 Agent（9 个）

hermes-internal, claude, deepseek-tui, codex, intelligence, pirlo, designer, agent-tars, ambrosini

### 3.2 只存在于 source 的 Agent（1 个，但 registry 也有）

**opencode** — 存在于 agents.yaml (source) 和 agent-registry.json (registry)，**仅 mirror (managed-agents.yaml) 缺失**。

### 3.3 字段不一致的 Agent

| Agent | 字段 | A (source) | B (mirror) | C (registry) | 以谁为准 |
|-------|------|-----------|-----------|-------------|---------|
| **claude** | model_ref | `claude_sonnet` | `claude_opus` | `claude_sonnet` | source |
| **claude** | model_strategy.chain | `[claude_sonnet, claude_opus]` | `[claude_opus]` (无 fallback) | `[claude_sonnet, claude_opus]` | source |
| **claude** | role_summary | "标准实现默认 Sonnet，复杂/高风险实现再升级 Opus" | "后端由 CC Switch 控制" | soul says "标准实现默认 Sonnet..." | source |
| **deepseek-tui** | model_ref | `opencode_go_deepseek_flash` | `opencode_go_deepseek_pro` | `opencode_go_deepseek_flash` | source |
| **deepseek-tui** | model_strategy.primary | `opencode_go_deepseek_flash` | `opencode_go_deepseek_pro` | `opencode_go_deepseek_flash` | source |

---

## 4. opencode 专项核查

### 4.1 存在性

| 文件 | 存在 | 位置 |
|------|------|------|
| agents.yaml | ✅ | lines 165-199 |
| agent-registry.json | ✅ | lines 286-353 |
| managed-agents.yaml | ❌ | — |

### 4.2 定义完整性

从 agents.yaml 中提取的 opencode 定义：

| 字段 | 值 | 状态 |
|------|-----|------|
| agent_id | `opencode` | ✅ |
| name | OpenCode 协作执行员 | ✅ |
| role | external_collaboration_worker | ✅ |
| role_summary | 外部 OpenCode CLI 适配器；窄范围代码复核、廉价二审、失败样本采集、协作链路 smoke | ✅ |
| model_ref | `opencode_go_deepseek_flash` | ✅ |
| model_strategy.mode | `external` | ✅ |
| model_strategy.chain | `[opencode_go_deepseek_flash, opencode_go_deepseek_pro]` | ✅ |
| runtime | `opencode_cli` | ✅ |
| permission | `ask` | ✅ |
| can_delegate | `false` | ✅ |
| tools | `[file, terminal]` | ✅ |
| skills | `[codebase-inspection, github-code-review, systematic-debugging]` | ✅ |
| capabilities | `[code_review, external_quick_check, bug_reproduction, collaboration_smoke]` | ✅ |
| risk_allowed | `[R0, R1, R2]` | ✅ |

**结论：opencode 在 source 和 registry 中定义完全、字段齐全。仅 mirror 缺失。**

---

## 5. 快照矛盾修正

之前架构快照和健康检查中存在不一致：

- ❌ 健康检查说："agent-registry 和 agents.yaml 各 10 个 Agent，registry coverage OK"
- ❌ 快照说："opencode 未同步到 agent-registry.json 和 managed-agents.yaml"

**实际以文件内容为准：**
- ✅ agent-registry.json **确实包含 opencode**（lines 286-353）
- ✅ agents.yaml **确实包含 opencode**（lines 165-199）
- ❌ managed-agents.yaml **缺失 opencode**
- ⚠️ managed-agents.yaml 的 claude 和 deepseek-tui 字段与 source 不一致

---

## 6. 修复建议（供 Phase 1 参考）

| 优先级 | 操作 | 说明 |
|--------|------|------|
| 🔴 P0 | 补 managed-agents.yaml → 加 opencode | 解决 mirror drift |
| 🟡 P1 | 修正 managed-agents.yaml claude model_ref | `claude_opus` → `claude_sonnet`，补 chain |
| 🟡 P1 | 修正 managed-agents.yaml claude role_summary | 补齐 "标准实现默认 Sonnet..." |
| 🟡 P1 | 修正 managed-agents.yaml deepseek-tui model_ref | `opencode_go_deepseek_pro` → `opencode_go_deepseek_flash` |
| 🔵 P2 | agent-registry.json 补 routing_rules 中 opencode 相关能力 | `code_review` 当前路由到 codex，是否也要 route 到 opencode 作为 fallback？需确认语义 |
| 🔵 P2 | 增强 hermes-system-doctor.py mirror 校验 | 增加字段级对比（model_ref, chain, permission），不只是 ID 集合 |

---

## 7. 审计结论

**managed-agents.yaml mirror drift 确认存在。** 不是 registry 缺 Agent，是 mirror 缺 opencode + claude/deepseek-tui 字段陈旧。

**Phase 1 可安全执行：只补 mirror，不改 source，不改 registry。**
