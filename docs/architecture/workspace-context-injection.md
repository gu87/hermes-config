# Workspace Context 注入架构

版本：v0.6-draft
日期：2026-06-04

---

## 一、设计目标

每个 Project 维护一份结构化上下文（`WorkspaceContext`），在创建 run 时自动拼接到 prompt 前。注入内容对用户完全可见，可按字段 include/exclude，可按 executor 类型裁剪，不隐藏任何内容，不注入 secrets。

---

## 二、WorkspaceContext 数据模型

存放路径：`<project_root>/.hermes/context.yaml`（纳入项目 git，不含 secrets）

```typescript
interface WorkspaceContext {
  project_overview?: string        // 项目一句话描述
  architecture_notes?: string      // 技术栈、模块划分、关键依赖
  adr_summaries?: AdrSummary[]     // 关键决策摘要
  current_sprint?: string          // 当前迭代目标
  common_commands?: CommandEntry[] // 常用命令（build/lint/dev）
  test_commands?: CommandEntry[]   // 测试命令
  forbidden_areas?: string[]       // 不允许 agent 修改的路径/模块
  coding_conventions?: string      // 代码风格约定（简短，< 200 字）
  recent_tasks?: RecentTask[]      // 最近已完成 task 摘要（自动维护）
}

interface AdrSummary {
  id: string        // e.g. "ADR-001"
  title: string
  decision: string  // 一句话
}

interface CommandEntry {
  label: string
  command: string
}

interface RecentTask {
  thread_id: string
  title: string
  executor: ExecutorType
  status: 'done' | 'failed'
  completed_at: string
  summary?: string  // run 结束时由 agent 或用户填写，可选
}
```

`recent_tasks` 由 Orchestrator 在 task done 时自动追加，最多保留 10 条，无需用户手动维护。

---

## 三、Context 注入策略

### 3.1 注入时机

`Orchestrator.createRun(threadId, userPrompt, executorType)` 调用时，由 `ContextInjector.build(userPrompt, context, executorType, includeFlags)` 生成 `injectedPrompt`，存入 `AgentRun.prompt_snapshot`（见第四节）。

### 3.2 按 executor 类型裁剪的注入内容

| 字段 | claude-code | codex-cli | opencode | deepseek-tui | hermes-local |
|---|---|---|---|---|---|
| project_overview | ✅ | ✅ | ✅ | ✅ | ✅ |
| architecture_notes | ✅ 完整 | ⚠️ 摘要（前 300 字） | ✅ 完整 | ❌ | ✅ |
| adr_summaries | ✅ 全部 | ⚠️ 最近 3 条 | ✅ 全部 | ❌ | ✅ |
| current_sprint | ✅ | ✅ | ✅ | ✅ | ✅ |
| common_commands | ✅ | ✅ | ✅ | ✅ | ✅ |
| test_commands | ✅ | ✅ | ✅ | ❌ | ✅ |
| forbidden_areas | ✅ | ✅ | ✅ | ✅ | ✅ |
| coding_conventions | ✅ | ✅ | ✅ | ❌ | ✅ |
| recent_tasks | ✅ 最近 5 条 | ✅ 最近 3 条 | ✅ 最近 5 条 | ❌ | ✅ 最近 5 条 |

裁剪原则：
- `deepseek-tui` 接收最短 prompt（无架构背景），只注入 overview、sprint、命令、forbidden areas。
- `codex-cli` 偏实现，architecture_notes 截断为摘要，减少上下文干扰。
- `claude-code` 和 `opencode` 接收完整 context，用于架构/review 类任务。

### 3.3 避免 prompt 过长

- 注入内容总 token 上限（估算）：`claude-code` 2000 tokens，`codex-cli` 1500 tokens，`opencode` 2000 tokens，`deepseek-tui` 500 tokens。
- 若超出上限，按优先级截断：forbidden_areas > project_overview > current_sprint > common_commands > coding_conventions > adr_summaries > architecture_notes > recent_tasks。
- 截断时 UI 在 Context Preview 中以黄色警告标注哪些字段被截断，以及估算 token 数。

### 3.4 注入格式

```
--- Workspace Context ---
Project: <project_overview>
Sprint: <current_sprint>
Architecture: <architecture_notes>
ADRs:
  - ADR-001: <decision>
  - ADR-003: <decision>
Forbidden: <forbidden_areas 以逗号分隔>
Conventions: <coding_conventions>
Commands:
  build: npm run build
  test: npm test
Recent tasks:
  - [done] 重构 auth 错误处理 (codex-cli)
--- End Context ---

<user prompt>
```

分隔线 `--- Workspace Context ---` 必须存在，方便 executor 和用户识别注入边界。

---

## 四、AgentRun prompt_snapshot

`AgentRun` 增加字段：

```typescript
interface AgentRun {
  // ... 现有字段
  user_prompt: string         // 用户原始输入，不含注入内容
  prompt_snapshot?: string    // 实际发送给 executor 的完整 prompt（含注入）
  context_include_flags?: Record<string, boolean>  // 本次 run 的 include 开关快照
}
```

- `user_prompt` 始终保存用户原始输入。
- `prompt_snapshot` 在 `createRun` 时生成并持久化，之后不变。
- `prompt_snapshot` 在 Timeline 中可通过"查看注入内容"按钮展开，不默认展开。

---

## 五、UI 设计

### 5.1 Project Context 编辑页面

路径：Project 设置 → Context（或 Cmd+, → Context）

布局：
```
┌─ Project Context ──────────────────────────────────────┐
│ Project Overview    [编辑]                              │
│ ────────────────────────────────────────────────       │
│ Architecture Notes  [编辑]                              │
│ ADR Summaries       [+ 添加] [编辑]                     │
│ Current Sprint      [编辑]                              │
│ Common Commands     [+ 添加] [编辑]                     │
│ Test Commands       [+ 添加] [编辑]                     │
│ Forbidden Areas     [+ 添加]                            │
│ Coding Conventions  [编辑]                              │
│ Recent Tasks        [自动维护，最近 10 条]               │
│                                                        │
│ Context Injection   [● 已启用]  [关闭]                  │
└────────────────────────────────────────────────────────┘
```

### 5.2 Context Preview（Run 发起前）

用户输入 prompt 并选择 executor 后，确认对话框底部显示 Context Preview：

```
┌─ Executor 推荐对话框 ─────────────────────────────────┐
│  推荐：Codex CLI  (高置信度)                           │
│  ○ Claude Code  ○ opencode  ○ deepseek-tui            │
│                                                       │
│  ▶ Context Preview  (展开查看注入内容)                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │ --- Workspace Context ---                        │ │
│  │ Project: Hermes agent runtime                    │ │
│  │ Sprint: v0.6 context injection                   │ │
│  │ Forbidden: .env, secrets/, profiles/             │ │
│  │ ...                                              │ │
│  │ --- End Context ---                              │ │
│  │                                                  │ │
│  │ [estimated: ~820 tokens]                         │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  Include / Exclude:                                   │
│  ☑ Overview  ☑ Sprint  ☑ Architecture  ☑ ADRs        │
│  ☑ Commands  ☑ Forbidden  ☑ Conventions  ☑ Recent    │
│                                                       │
│  [确认执行]  [取消]                                    │
└───────────────────────────────────────────────────────┘
```

- Context Preview 默认折叠，用户展开才可见。
- Include/Exclude toggles 修改后实时更新 Preview 和 token 估算。
- 用户在此处的 toggle 调整只影响本次 run，不修改全局设置（需要专门保存才持久化）。

### 5.3 Run Timeline 中的 prompt snapshot 入口

在 Timeline 最顶部，user message 卡片右侧显示：

```
┌ 👤 You ──────────────────────────────── [查看注入内容 ▾] ┐
│ 重构 auth 错误处理                                        │
└──────────────────────────────────────────────────────────┘
```

点击"查看注入内容"展开 `prompt_snapshot`，以灰色背景显示注入部分，用户输入以正常颜色显示。不展开时不占 timeline 视觉空间。

### 5.4 全局关闭 Context Injection

Project 设置中 `Context Injection [● 已启用] [关闭]` 开关：
- 关闭后，所有 run 的 `prompt_snapshot = user_prompt`（不注入任何内容）。
- Status bar 显示 `⊘ Context off` badge 提醒。

---

## 六、安全边界

| 规则 | 说明 |
|---|---|
| 不自动读取 `.env` | `context.yaml` 不包含 secrets 字段；forbidden_areas 默认包含 `.env` |
| 不自动注入 secrets | `ExecutorConfig.env` 由用户手动配置，不从 `context.yaml` 读取 |
| 不隐藏注入内容 | `prompt_snapshot` 始终可查看；Context Preview 在确认前可展开 |
| 用户可关闭 | Project 级别开关；单次 run 级别 toggle |
| `context.yaml` 不含动态内容 | 不读取文件系统、不执行命令；`recent_tasks` 由 Orchestrator 维护，不从外部拉取 |
| forbidden_areas 不可被 executor 覆盖 | Orchestrator 在 `startRun` 前校验 executor config，不允许 executor 声明绕过 forbidden_areas |

---

## 七、与现有架构的集成点

| 位置 | 变更 |
|---|---|
| `AgentRun` 模型 | 新增 `user_prompt`、`prompt_snapshot`、`context_include_flags` |
| `ExecutorConfig` | 新增 `context_snapshot: WorkspaceContext`（只读，供 adapter 可选使用） |
| `Orchestrator.createRun` | 调用 `ContextInjector.build` 后再传给 adapter |
| `AdapterStartResult` | 无变更，adapter 透明接收已注入的 prompt |
| `context.yaml` | 新文件，项目根目录下 `.hermes/context.yaml`，纳入 git |
| Router | `Router.recommend` 可读取 `current_sprint` 辅助 confidence 判断（可选） |
