# 多执行器 Adapter 接口设计评审

日期：2026-06-03
输入：docs/architecture/agent-adapter-layer.md
目的：评审 AgentExecutorAdapter 接口是否足够支持 Claude Code CLI、Codex、DeepSeek TUI、Hermes Local，并给出必要的修订建议。

---

## 一、当前接口回顾

```typescript
interface AgentExecutorAdapter {
  start(run: AgentRun, config: ExecutorConfig): Promise<AdapterStartResult>
  stop(runId: string): Promise<void>
  streamEvents(runId: string): AsyncIterable<RunEvent>
  getStatus(runId: string): Promise<RunStatus>
}
```

---

## 二、各执行器特征分析

### 2.1 Hermes Local

- **调用方式**：HTTP REST + SSE（`/v1/runs`）
- **事件格式**：结构化 JSON SSE，字段已基本对齐 RunEvent schema
- **停止方式**：`POST /v1/runs/{id}/stop`（HTTP，幂等）
- **diff 来源**：SSE 中含 `{"type":"diff",...}` event，或 run 结束后从后端 API 取
- **失败状态**：SSE `{"type":"error",...}` + run status `failed`
- **健康检查**：`/health` endpoint 已有
- **接口适配评估**：✅ 完全匹配，无需扩展

### 2.2 Claude Code CLI

- **调用方式**：子进程 `claude-code --output-format stream-json`
- **事件格式**：stdout JSON lines，每行一个事件，格式：
  ```json
  {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
  {"type":"tool","name":"write_file","input":{...},"output":{...}}
  {"type":"result","subtype":"success","cost_usd":0.12}
  ```
- **停止方式**：`SIGTERM` 到子进程（需要 pid 管理）
- **diff 来源**：无内置 diff event；需要在 run 前后执行 `git diff` 取变更
- **失败状态**：process exit code != 0，或 `{"type":"result","subtype":"error"}`
- **健康检查**：`claude --version`（本地 CLI 可用性）
- **接口适配评估**：
  - ⚠️ `stop(runId)` 需要 adapter 内部维护 `runId → pid` 映射，接口签名够用
  - ⚠️ `streamEvents` 需要 stdout pipe + JSON line parser；stderr 单独消费防止卡死
  - ⚠️ **diff 不来自事件流**，需要在 `start` 前记录 `git rev`，run 结束后由 adapter 主动 `git diff <before>..<after>` 并补发 `diff` event

### 2.3 Codex

- **调用方式**：
  - 方式 A：Codex CLI 子进程（`codex --json-output`）
  - 方式 B：Codex Responses API（HTTP，OpenAI-compatible，本仓库已有 `codex_responses_adapter.py`）
  - 当前 hermes-agent 已有 `codex_runtime.py` + `codex_app_server.py`，说明 Hermes 通过内部 server 代理 Codex 调用
- **事件格式（CLI）**：stdout JSON，含 `reasoning`、`tool_call`、`output` 等字段，但字段名与 RunEvent 不一致（如 `output_text` vs `message`）
- **事件格式（API）**：OpenAI Responses API streaming，delta 形式
- **停止方式**：CLI 子进程 SIGTERM；API 无法中断已发出的请求（需要 timeout）
- **diff 来源**：与 Claude Code 相同，无内置 diff；需 adapter 主动 `git diff`
- **失败状态**：exit code 或 API error response
- **接口适配评估**：
  - ⚠️ 两种调用方式应封装在同一个 `CodexAdapter` 内，通过 `ExecutorConfig.extra.mode` 选择
  - ⚠️ diff 同样需要 adapter 在 `start` 前后 snapshot git state

### 2.4 DeepSeek TUI

- **调用方式**：TUI 进程（通常是 `deepseek-r1` 或兼容 CLI），非 JSON 输出，输出为 ANSI 终端文本
- **事件格式**：非结构化 stdout，需要启发式解析（无法完全归一化为 tool_call）
- **停止方式**：子进程 SIGTERM
- **diff 来源**：无；需 adapter 主动 `git diff`
- **失败状态**：exit code != 0 或 stderr 含 error pattern
- **接口适配评估**：
  - ⚠️ 无法从 stdout 可靠提取结构化 tool_call；只能生成 `log` type events
  - ⚠️ `reasoning` 和 `message` 无法区分，只能整体作为 `message` event
  - ℹ️ **DeepSeek TUI 的实际定位应是 low-cost worker，不应作为 UI 可感知的结构化执行器**；适合做后台 batch 任务，timeline 只显示 log 流

---

## 三、接口充分性评估

### 3.1 是否过度绑定 Claude Code

当前接口本身（4 个方法）**不绑定** Claude Code。但 `agent-adapter-layer.md` 的事件归一化表只列了 Hermes SSE 和 `claude-code stdout JSON line`，暗示其他执行器的归一化规则尚未定义。接口设计是中立的，文档描述有偏向。

### 3.2 start / stop / streamEvents / getStatus 是否足够通用

| 方法 | 充分性 | 缺口 |
|---|---|---|
| `start` | ✅ 足够 | 需要 `AdapterStartResult.git_snapshot` 字段供 diff 使用 |
| `stop` | ✅ 足够 | 子进程 adapter 需内部维护 pid 映射，接口签名不变 |
| `streamEvents` | ⚠️ 基本足够 | 非结构化 executor（DeepSeek TUI）只能产出 `log` events，调用方需知晓 |
| `getStatus` | ⚠️ 需补充 | 子进程 adapter 的 status 来自进程存活检测，而非 HTTP；实现路径不同但接口可复用 |

**结论**：4 个方法的签名**足够**，无需新增方法。但需要补充两处约定：
1. `AdapterStartResult` 增加 `git_snapshot?: string`（当前 HEAD commit sha）
2. `streamEvents` 文档说明：adapter 可以在 run 结束后追加合成的 `diff` event

### 3.3 diff 收集的统一方案

各 executor 的 diff 来源不同，需要在 adapter 层统一：

```
Hermes Local  → SSE 中含 diff event（直接使用）
Claude Code   → adapter 在 start 前记录 git HEAD，run 结束后执行 git diff 并作为 diff event 追加
Codex         → 同 Claude Code
DeepSeek TUI  → 同 Claude Code，但 diff 是 run 结束后唯一可信的结构化产出
```

建议在 `agent-adapter-layer.md` 补充一条约定：

> 若 executor 不原生产出 diff event，adapter 必须在 `start` 时记录 `git rev-parse HEAD`，在 `streamEvents` 迭代结束时追加通过 `git diff <snapshot>` 生成的 `diff` event。Orchestrator 不感知 diff 来源差异。

### 3.4 失败状态统一

| Executor | 原生失败信号 | 归一化方式 |
|---|---|---|
| Hermes Local | SSE `{"type":"error"}` + HTTP status | `failed` RunEvent + RunStatus.failed |
| Claude Code CLI | exit code != 0 或 `subtype:error` JSON | adapter 捕获后发出 `failed` event，`payload.error` 携带 stderr 摘要 |
| Codex | exit code / API error | 同上 |
| DeepSeek TUI | exit code / stderr pattern | adapter 发出 `failed` event；`error_summary` 取 stderr 最后 N 行 |

**统一规则**：所有 adapter 必须保证 `streamEvents` 在执行失败时以 `{type: "failed", payload: {error_summary: string}}` event 结束迭代，**不能让 AsyncIterable 静默结束**（即不 throw，也不 yield failed event）。

### 3.5 是否需要 executor health check

**需要，但不作为 AgentExecutorAdapter 接口方法。**

理由：`getStatus(runId)` 是运行时状态查询，不是执行器可用性检查。混在一起会导致：在没有 runId 的情况下无法检查执行器是否可用。

**建议**：在 `AdapterRegistry` 层增加可选的 health check：

```typescript
interface AgentExecutorAdapter {
  // 现有 4 个方法不变
  checkHealth?(): Promise<ExecutorHealthResult>  // 可选
}

interface ExecutorHealthResult {
  available: boolean
  version?: string
  error?: string
}
```

- `HermesLocalAdapter.checkHealth` → `GET /health`
- `ClaudeCodeAdapter.checkHealth` → `which claude-code && claude-code --version`
- `CodexAdapter.checkHealth` → `which codex && codex --version`
- `DeepSeekTuiAdapter.checkHealth` → 检查本地 binary 存在性

`checkHealth` 在 AdapterRegistry 初始化时调用，结果存入 executor manifest，供 UI status bar 展示；不影响主链路。

### 3.6 是否需要 executor capability 描述

**需要，以防止 UI 展示无法支持的操作。**

各 executor 的能力不对称：

| Capability | Hermes Local | Claude Code | Codex | DeepSeek TUI |
|---|---|---|---|---|
| 结构化 tool_call | ✅ | ✅ | ✅ | ❌ |
| 原生 diff event | ✅ | ❌（adapter 生成） | ❌（adapter 生成） | ❌（adapter 生成） |
| reasoning / thinking | ✅ | ✅ | ⚠️ 部分 | ❌ |
| 实时 streaming | ✅ | ✅ | ✅ | ⚠️ line-buffered |
| review gate | ✅ | ❌ v0.1 | ❌ v0.1 | ❌ |
| worktree 支持（v1.0） | ✅ | ✅ | ✅ | ✅ |

**建议**：在 executor manifest（JSON/YAML 配置文件，不在接口层）中声明 capabilities，Orchestrator 读取后决定是否展示 ReviewBar、ToolCallCard 等 UI 组件：

```typescript
interface ExecutorManifest {
  id: ExecutorType
  label: string
  capabilities: {
    structured_tool_calls: boolean
    native_diff_events: boolean
    reasoning_blocks: boolean
    review_gate: boolean
    streaming: 'realtime' | 'line-buffered' | 'batch'
  }
}
```

UI 根据 `capabilities.structured_tool_calls` 决定是否渲染 ToolCallCard（否则只渲染 log stream）；根据 `capabilities.review_gate` 决定是否渲染 ReviewBar。

---

## 四、必须修订的点

### P0 必须修

**P0-1：`streamEvents` 必须保证以 `failed` event 结束，不能静默结束**

当前接口文档未约定此行为。若 adapter 因子进程崩溃而让 `AsyncIterable` 自然结束，UI 的 timeline 会停止更新但不显示失败，用户无法判断 run 是完成了还是卡死了。

修订：在 `agent-adapter-layer.md` 的接口契约中明确：
> 若 run 以非正常方式结束，`streamEvents` 必须在结束前 yield 一个 `{type: "failed"}` event，然后才结束迭代。不允许静默结束。

**P0-2：`AdapterStartResult` 增加 `git_snapshot` 字段**

Claude Code、Codex、DeepSeek TUI 均无原生 diff event，adapter 必须在 `start` 时记录 git HEAD，否则 run 结束后无法生成可信的 diff。若 `start` 不记录 snapshot，diff 就永远缺失。

修订：
```typescript
interface AdapterStartResult {
  external_run_id?: string
  base_path?: string
  git_snapshot?: string  // git rev-parse HEAD，供 adapter 在 run 结束后生成 diff
}
```

---

### P1 应该修

**P1-1：增加可选 `checkHealth()` 方法**

不加则 status bar 无法区分"执行器未安装"和"执行器已安装但 run 未启动"。用户选择 `claude-code` 但未安装 CLI 时，会在 `start` 时才报错，而不是在执行器选择时就给出提示。

**P1-2：增加 `ExecutorManifest.capabilities` 定义**

不加则 UI 在所有 executor 下都渲染 ReviewBar 和 ToolCallCard，但 Claude Code 在 v0.1 不支持 review gate，会造成 ReviewBar 出现但永远不会触发的空状态。

**P1-3：在 `agent-adapter-layer.md` 补充 Claude Code / Codex / DeepSeek 的事件归一化表**

当前只有 Hermes SSE 的归一化规则。不补充，未来实现这三个 adapter 时每人理解不同，导致 RunEvent schema 漂移。

---

### P2 后续修

**P2-1：DeepSeek TUI adapter 的定位应在 manifest 中标注为 `low-fidelity`**

DeepSeek TUI 无法产出结构化 tool_call，timeline 只有 log stream。v0.1-v0.5 阶段不建议在 UI 中将其作为平等的执行器选项展示，避免用户产生"选了 DeepSeek 但看不到 tool call / diff"的困惑。在 manifest 中加 `ui_fidelity: 'low'`，UI 据此给出提示或降级展示。

**P2-2：Codex API vs CLI 双模式应在 manifest 中区分，而不是用 `extra.mode`**

`ExecutorConfig.extra` 是非类型化字段，双模式切换逻辑隐藏在 adapter 内部，外部无法感知。v1.0 引入 router 时，router 需要知道两种模式的延迟/成本差异，才能做路由决策。应在 manifest 中将 `codex-api` 和 `codex-cli` 注册为两个不同的 ExecutorType，而不是一个执行器的内部分支。

**P2-3：子进程 adapter 的 pid 映射需要持久化**

若 desktop 进程重启（Electron crash），`runId → pid` 映射丢失，`stop(runId)` 将无法找到子进程。v0.5 引入 Claude Code adapter 时需要考虑将 pid 写入本地 DB，重启后可尝试 SIGTERM。

---

## 五、接口修订后的最终形态

```typescript
interface AgentExecutorAdapter {
  start(run: AgentRun, config: ExecutorConfig): Promise<AdapterStartResult>
  stop(runId: string): Promise<void>
  // 约定：必须以 failed event 结束（若非正常完成），不得静默结束
  streamEvents(runId: string): AsyncIterable<RunEvent>
  getStatus(runId: string): Promise<RunStatus>
  checkHealth?(): Promise<ExecutorHealthResult>  // P1，可选
}

interface AdapterStartResult {
  external_run_id?: string
  base_path?: string
  git_snapshot?: string  // P0，新增
}

interface ExecutorHealthResult {
  available: boolean
  version?: string
  error?: string
}
```

manifest 层（不在接口，在配置文件中）：

```typescript
interface ExecutorManifest {
  id: ExecutorType
  label: string
  ui_fidelity: 'full' | 'low'  // P2
  capabilities: {
    structured_tool_calls: boolean
    native_diff_events: boolean
    reasoning_blocks: boolean
    review_gate: boolean
    streaming: 'realtime' | 'line-buffered' | 'batch'
  }
}
```

---

## 六、结论

当前 `AgentExecutorAdapter` 接口的 **4 个方法签名足够通用**，不绑定 Claude Code，不需要为每个执行器新增专属方法。

需要修订的是：
1. `AdapterStartResult` 加 `git_snapshot`（P0，所有非 Hermes 执行器都需要）
2. `streamEvents` 的终止契约（P0，防止静默失败）
3. 可选 `checkHealth`（P1，status bar 用）
4. `ExecutorManifest.capabilities`（P1，UI 按能力降级展示）

接口修订量小，不影响 HermesLocalAdapter 已有的设计，不需要修改 Orchestrator 或 UI。
