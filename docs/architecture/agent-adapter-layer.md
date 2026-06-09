# Agent Adapter 层设计

## 1. 目的

将 UI / Orchestrator 与具体执行器实现**解耦**。Orchestrator 只依赖统一接口，不感知底层是 HTTP 调用、子进程还是 IPC。新增执行器只需实现接口并注册，无需修改 Orchestrator 或 UI。

---

## 2. AgentExecutorAdapter 接口

```typescript
interface AgentExecutorAdapter {
  /** 启动一次运行。返回后执行器应已在后台运行。 */
  start(run: AgentRun, config: ExecutorConfig): Promise<AdapterStartResult>;

  /** 向执行器发送停止信号。幂等。 */
  stop(runId: string): Promise<void>;

  /** 返回该 run 的事件异步迭代器（归一化为 RunEvent）。 */
  streamEvents(runId: string): AsyncIterable<RunEvent>;

  /** 查询当前 RunStatus，不副作用。 */
  getStatus(runId: string): Promise<RunStatus>;
}

interface AdapterStartResult {
  external_run_id?: string;
  base_path?: string;
}
```

Adapter 返回的是 executor 私有运行 id 和实际执行目录；UI 只读 `AgentRun.id`、`AgentRun.status`、`ChangedFile`，不读取 executor 私有字段。

---

## 3. 具体适配器

### v0.1：HermesLocalAdapter

封装本地 Hermes 后端 REST/SSE API。

- `start` → `POST /v1/runs`（带 prompt、executor_id、env）
- `stop` → `POST /v1/runs/{id}/stop`
- `streamEvents` → `GET /v1/runs/{id}/events`（SSE），每条 SSE data 映射为 RunEvent
- `getStatus` → `GET /v1/runs/{id}`，取 `.status` 字段

### v0.5：多执行器（当前可用清单）

| ExecutorType | Adapter 类 | 调用方式 | 结构化事件 | 原生 diff |
|---|---|---|---|---|
| `hermes-local` | `HermesLocalAdapter` | HTTP REST + SSE | ✅ | ✅ |
| `claude-code` | `ClaudeCodeAdapter` | 子进程 stdout JSON lines | ✅ | ❌（adapter 生成） |
| `codex-cli` | `CodexCliAdapter` | 子进程 stdout JSON lines | ✅ | ❌（adapter 生成） |
| `opencode` | `OpenCodeAdapter` | 子进程 stdout，结构化程度中等 | ⚠️ 部分 | ❌（adapter 生成） |
| `deepseek-tui` | `DeepSeekTuiAdapter` | 子进程 stdout，非结构化 | ❌（仅 log） | ❌（adapter 生成） |

> ~~`codex-app`~~：暂不可用，不注册。

每个 adapter 必须满足同一 contract：向上只暴露 `RunEvent`、`RunStatus`、`ChangedFile`，不让 UI 感知 executor 原生事件。

非 `hermes-local` 的所有子进程 adapter 均需在 `start` 时记录 `git_snapshot`（见 `AdapterStartResult`），在 `streamEvents` 结束时追加通过 `git diff <snapshot>` 生成的 `diff` event。

## 4. 新增执行器流程

1. 实现 `AgentExecutorAdapter` 接口（含 `streamEvents` 事件归一化）
2. 在 `AdapterRegistry` 初始化处调用 `registry.register('new-executor', new NewAdapter())`
3. 在 executor manifest 中声明名称、能力、`ui_fidelity`、`checkHealth` 实现
4. Orchestrator 根据 `executor_id` 获取 adapter，无需修改 UI 或现有 adapter

---

## 5. AdapterRegistry

```typescript
class AdapterRegistry {
  private map = new Map<ExecutorId, AgentExecutorAdapter>();

  register(executorId: ExecutorId, adapter: AgentExecutorAdapter): void {
    this.map.set(executorId, adapter);
  }

  get(executorId: ExecutorId): AgentExecutorAdapter {
    const adapter = this.map.get(executorId);
    if (!adapter) throw new Error(`No adapter registered for: ${executorId}`);
    return adapter;
  }
}

// 初始化（应用启动时）
const registry = new AdapterRegistry();
registry.register('hermes-local', new HermesLocalAdapter());
```

---

## 6. Adapter 的职责边界

**Adapter 不负责：**

- 状态持久化（由 Store 层负责）
- 审核决定（由 Orchestrator 负责）
- UI 更新（UI 订阅 Orchestrator 提供的事件）
- 路由逻辑（由 Orchestrator 或 Router 负责）

**Adapter 负责：**

- 启动执行器（HTTP 请求、子进程、IPC 等）
- 转发运行参数（prompt、env、model 等）
- 收集原生日志/事件流
- 将原生事件**归一化**为 `RunEvent` schema
- 上报实际执行目录 `base_path`，供 Changed Files / Open in Editor 使用

---

## 7. 事件归一化

各适配器将各自原生格式映射到统一 `RunEvent` 类型：

| 原生事件 | 归一化 RunEvent.type |
|---|---|
| Hermes SSE `data: {"type":"text",...}` | `message` |
| Hermes SSE `data: {"type":"thinking",...}` | `reasoning` |
| Hermes SSE `data: {"type":"tool_use",...}` | `tool_call` |
| Hermes SSE `data: {"type":"tool_result",...}` | `tool_result` |
| Hermes SSE `data: {"type":"diff",...}` | `diff` |
| Hermes SSE `data: {"type":"approval_needed",...}` | `approval_needed` |
| Hermes SSE `data: {"type":"done",...}` | `completed` |
| Hermes SSE `data: {"type":"error",...}` | `failed` |
| claude-code stdout JSON line（v0.3）| 按字段映射，同上规则 |

归一化后，`seq` 字段由 Orchestrator 分配，而不是 Adapter 分配。原因是 v0.4 并行任务、stream reconnect、adapter 重试都会导致原生事件可能重复或乱序；Orchestrator 才能在持久化前做去重和顺序归并。

---

---

## 9. 架构示意图（v0.5）

```
  UI
   │  (仅通过 Orchestrator 接口交互)
   ▼
Router ──► RouterOutput (推荐 executor，用户确认)
   │
   ▼
Orchestrator
   │  get(executorType)
   ▼
AdapterRegistry
   ├──► HermesLocalAdapter  ──► POST/GET /v1/runs      (本地 Hermes 后端)
   ├──► ClaudeCodeAdapter   ──► claude-code CLI 子进程
   ├──► CodexCliAdapter     ──► codex CLI 子进程
   ├──► OpenCodeAdapter     ──► opencode CLI 子进程
   └──► DeepSeekTuiAdapter  ──► deepseek-tui 子进程
```

所有 Adapter 向上返回统一的 `AsyncIterable<RunEvent>`，Orchestrator 不感知下游差异。Router 只产生推荐数据，不创建 run。
