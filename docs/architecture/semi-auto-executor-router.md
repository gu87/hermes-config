# 半自动 Executor Router 设计

版本：v0.5-draft
日期：2026-06-04

---

## 一、设计目标

用户创建 Task 后，Router 根据任务内容推荐合适的 executor，展示推荐理由和备选项，由用户确认后再执行。Router 不自动发起 run，不绕过 worktree/diff review/permission gate，用户选择始终优先于系统推荐。

---

## 二、RouterOutput 结构

```typescript
interface RouterOutput {
  recommendedExecutor: ExecutorType
  confidence: 'high' | 'medium' | 'low'
  reason: string                          // 一句话，显示给用户
  alternatives: AlternativeExecutor[]
  unavailableReason?: string              // 推荐 executor 不可用时说明
  fallback?: ExecutorType                 // 若推荐不可用，自动降级到此项
}

interface AlternativeExecutor {
  executor: ExecutorType
  reason: string
  available: boolean
}
```

Router 输出是纯数据，不触发任何 run 创建。Orchestrator 在用户确认后才调用 `createRun`。

---

## 三、支持的 Executor 类型

| ExecutorType | 说明 | 调用方式 |
|---|---|---|
| `claude-code` | Claude Code CLI | 子进程 stdout JSON lines |
| `codex-cli` | Codex CLI | 子进程 stdout JSON lines |
| `opencode` | opencode CLI | 子进程 stdout，结构化程度中等 |
| `deepseek-tui` | DeepSeek TUI | 子进程 stdout，非结构化 |
| `hermes-local` | Hermes 内部 agent | HTTP REST + SSE `/v1/runs` |

当前可用状态（2026-06-04）：

| Executor | 可用 |
|---|---|
| `claude-code` | ✅ |
| `codex-cli` | ✅ |
| `opencode` | ✅ |
| `deepseek-tui` | ✅ |
| `hermes-local` | ✅ |
| ~~codex-app~~ | ❌ 暂不可用 |

---

## 四、初始推荐规则

Router v0.5 使用基于关键词和任务类型的规则引擎，不使用 LLM 推理（避免推荐过程本身消耗 token）。

### 规则表

| 任务类型 | 判断依据（关键词/模式） | 推荐 Executor | 备选 |
|---|---|---|---|
| 架构设计 / ADR / 方案 review | `architecture`, `design`, `ADR`, `review`, `方案`, `架构`, `设计` | `claude-code` | `opencode` |
| 复杂实现 / 大范围重构 | `refactor`, `implement`, `migrate`, `重构`, `迁移`, `实现`, 文件数 > 5 估计 | `codex-cli` | `claude-code` |
| 本地开源 agent 验证 / 备选实现 | `validate`, `alternative`, `compare`, `验证`, `对比`, `备选` | `opencode` | `claude-code` |
| 快速 bug scan / small fix | `bug`, `fix`, `typo`, `crash`, `error`, `修复`, 文件数 ≤ 2 估计 | `deepseek-tui` | `opencode` |
| Hermes 内部流程 / adapter / scheduler | `hermes`, `adapter`, `orchestrat`, `scheduler`, `gateway`, `managed-agent` | `hermes-local` | `claude-code` |

### 规则匹配顺序

1. 精确匹配 Hermes 内部关键词 → `hermes-local`（最高优先级，避免用外部 executor 改 Hermes 自身）
2. 匹配设计/review 关键词 → `claude-code`
3. 匹配重构/实现关键词 → `codex-cli`
4. 匹配验证/对比关键词 → `opencode`
5. 匹配 bug/fix 且范围小 → `deepseek-tui`
6. 无匹配 → `claude-code`（默认 fallback，confidence: low）

### Confidence 定义

- `high`：命中 2+ 个关键词，且任务范围明确
- `medium`：命中 1 个关键词，或范围模糊
- `low`：无命中，使用默认 fallback

---

## 五、Executor 可用性检查

Router 在生成 `RouterOutput` 前先查询 `AdapterRegistry` 中各 executor 的 `checkHealth()` 结果（缓存 60 秒，不阻塞 UI）。

若推荐 executor 不可用：
- `unavailableReason` 填入原因（如 `"claude-code CLI 未安装，运行 'npm i -g @anthropic-ai/claude-code' 安装"`）
- `fallback` 设为第一个可用的 `alternatives`
- UI 高亮显示不可用状态，建议用户选择 fallback，但不自动切换

---

## 六、用户确认流程

```
用户输入 prompt
       │
       ▼
Router.recommend(prompt, taskContext)
       │
       ▼
┌──────────────────────────────────────┐
│  推荐执行器：Codex CLI  (高置信度)    │
│  理由：任务包含大范围重构             │
│                                      │
│  ◉ Codex CLI  ← 推荐                 │
│  ○ Claude Code                       │
│  ○ opencode                          │
│                                      │
│  [确认执行]  [取消]                   │
└──────────────────────────────────────┘
       │ 用户点击"确认执行"
       ▼
Orchestrator.createRun(threadId, prompt, selectedExecutor)
```

- 对话框在用户提交 prompt 后立即出现，不需要额外点击"推荐"按钮。
- 用户可以在对话框内切换 executor，切换时 `reason` 文字更新。
- 用户上次选择的 executor 在同一 session 内记忆，作为下次同类任务的默认选项（不持久化到 DB）。

---

## 七、Router 职责边界

**Router 负责：**
- 分析 prompt 文本和任务 context（project path、task title、估计文件范围）
- 生成 `RouterOutput`（推荐 + 备选 + 理由 + 可用性）
- 返回纯数据，不产生副作用

**Router 不负责：**
- 创建 run（由 Orchestrator 负责）
- 创建 worktree（由 Orchestrator 在 `startRun` 前负责）
- 执行 executor health check（读取 AdapterRegistry 缓存结果）
- 用户偏好持久化（session 内存，不写 DB）
- 多 Agent 协作调度（不在 v0.5 范围内）

---

## 八、扩展点（v1.0+）

- **LLM-backed routing**：用小模型（haiku/flash）分析复杂 prompt，替代关键词规则。触发条件：prompt > 200 字 且规则 confidence 为 low。
- **历史学习**：记录用户对推荐的接受/覆盖情况，调整关键词权重。
- **任务依赖路由**：同一 Task Thread 内连续 run 的 executor 可以不同（如先 claude-code 设计，再 codex-cli 实现）。
- **团队规则**：通过 `.hermes/router-policy.yaml` 覆盖默认规则，优先级高于内置规则表。
