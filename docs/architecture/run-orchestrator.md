# Run Orchestrator 设计

## 1. 目的

Orchestrator 是 AgentRun 和 TaskThread **状态机的唯一拥有者**。UI 和 Adapter 层均不互相直接通信，所有状态变更必须经过 Orchestrator。

- UI → Orchestrator（发指令、订阅事件）
- Orchestrator → AdapterRegistry（委托执行）
- Orchestrator → Store（委托持久化）
- Adapter → Orchestrator（推送归一化事件）

---

## 2. RunStatus 状态机

```
           enqueue()
created ──────────► queued ──────────► starting
                        │
                        │ 执行器就绪
                        ▼
                     running ───────────────────────┐
                        │                           │
                        │ approval_needed            │ (approval 后 continue)
                        ▼                           │
                 waiting_review ────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
          completed             failed

  任意活跃状态 (starting | running | waiting_review)
       │
       │ stop() / 外部中断
       ▼
   cancelled

  completed / failed
       │
       │ retryRun() / continueThread()
       ▼
    created  (新 Run)
```

**终态**：`completed`、`failed`、`cancelled`（不可再转换）。`Retry` 和 `Continue` 不改变旧 run，而是创建新 run。

---

## 3. TaskStatus 状态机

```
draft ──► queued ──► running ──► needs_review ──► done
                  │
                  ├──► failed
                  ├──► blocked
                  └──► cancelled
```

| 触发条件 | 转换 |
|---|---|
| 用户提交任务 | `draft → queued` |
| Orchestrator 开始 Run | `queued → running` |
| Run 收到 `approval_needed` 事件 | `running → needs_review` |
| ReviewDecision: continue | `needs_review → running` |
| ReviewDecision: accept | `needs_review → running` 或保持当前 run 完成后再归纳 |
| ReviewDecision: done | `needs_review → done` |
| Run status = failed | `running → failed` |
| 外部依赖未满足 | `running → blocked` |
| 用户取消 | 任意活跃状态 → `cancelled` |

---

## 4. Orchestrator 公开接口

```typescript
interface RunOrchestrator {
  /** 创建新 Run（不启动），关联到指定 thread */
  createRun(
    threadId: string,
    prompt: string,
    executorId: ExecutorId
  ): Promise<AgentRun>;

  /** 启动已创建的 Run */
  startRun(runId: string): Promise<void>;

  /** 向执行器发送停止信号，Run 转为 cancelled */
  stopRun(runId: string): Promise<void>;

  /** 提交审核决定，驱动 TaskThread 状态流转 */
  resolveReview(runId: string, decision: ReviewDecision): Promise<void>;

  /** 基于同一 thread+prompt 创建并返回新 Run（用于 Retry） */
  retryRun(runId: string): Promise<AgentRun>;

  /** 在已完成的 thread 上追加新 prompt，创建并返回新 Run（用于 Continue） */
  continueThread(threadId: string, prompt: string): Promise<AgentRun>;

  /** 返回当前 thread 的 run history 摘要，供 v0.1 列表和 header 使用 */
  listThreadRuns(threadId: string): Promise<AgentRun[]>;

  /** 订阅 Run 事件流，返回取消订阅函数 */
  subscribeRunEvents(runId: string, callback: (event: RunEvent) => void): Unsubscribe;
}

type Unsubscribe = () => void;
```

---

## 5. Orchestrator 不做的事

- **不渲染 UI**：所有展示逻辑在 UI 层
- **不直接调用执行器**：通过 `AdapterRegistry.get(executorId)` 委托
- **不持久化数据**：通过 Store 层（`RunStore`、`ThreadStore`）读写
- **不吞噬错误**：所有 Adapter 抛出的错误必须转为 `RunStatus.failed` + `error_summary`，并通过事件通知订阅者
- **不实现 executor 私有状态机**：具体执行器的 step/progress 只能归一化为 `RunEvent`，不能泄漏到 UI 状态模型

---

## 6. 完整 Run 生命周期时序图

```
UI            Orchestrator       AdapterRegistry    HermesLocalAdapter    后端
│                  │                   │                   │               │
│ createRun()      │                   │                   │               │
│─────────────────►│                   │                   │               │
│◄─ AgentRun       │                   │                   │               │
│                  │                   │                   │               │
│ startRun(id)     │                   │                   │               │
│─────────────────►│                   │                   │               │
│                  │ get('hermes-local')│                   │               │
│                  │──────────────────►│                   │               │
│                  │◄─ adapter         │                   │               │
│                  │                   │                   │               │
│                  │ adapter.start()   │                   │               │
│                  │──────────────────────────────────────►│               │
│                  │                   │                   │ POST /v1/runs │
│                  │                   │                   │──────────────►│
│                  │                   │                   │◄─ 200 OK      │
│                  │ external_run_id/base_path persisted   │               │
│                  │                   │                   │               │
│                  │ adapter.streamEvents()                │               │
│                  │──────────────────────────────────────►│               │
│                  │                   │  SSE stream ◄──────────────────── │
│◄─ RunEvent×N ────│                   │                   │               │
│  (subscribeRunEvents callback)       │                   │               │
│                  │                   │                   │               │
│  [approval_needed 事件]              │                   │               │
│◄─ RunEvent(approval_needed) ─────────│                   │               │
│ resolveReview()  │                   │                   │               │
│─────────────────►│                   │                   │               │
│                  │──────────────────────────────────────►│               │
│                  │                   │                   │ POST /approval│
│                  │                   │                   │──────────────►│
│                  │                   │                   │               │
│  [completed 事件]│                   │                   │               │
│◄─ RunEvent(completed) ───────────────│                   │               │
│                  │ → TaskThread.status = done            │               │
```

---

## 7. 错误处理规则

| 场景 | Orchestrator 行为 |
|---|---|
| Adapter `start()` 抛出 | Run → `failed`，`error_summary` = error.message，推送 `failed` RunEvent |
| SSE 流中断 / 超时 | Run → `failed`，`error_summary` = "stream interrupted" |
| `stop()` 调用后 Adapter 异常 | 仍将 Run 标为 `cancelled`，记录警告日志 |
| Store 写入失败 | 抛出，不静默吞噬，由上层调用方处理 |
| 重复事件 / stream reconnect | 根据 executor event id 或 payload hash 去重，再由 Orchestrator 分配 `seq` |
| diff 事件缺失 | Run 可完成，但 Changed Files 显示“未检测到文件变更”；不伪造 diff |

**原则**：Orchestrator 不静默吞噬任何错误；所有运行时错误最终反映在 `RunStatus` 和 `error_summary` 中，并通过事件流通知 UI。

---

## 8. 版本扩展钩子

以下钩子在 v0.1 中**不实现**，仅在接口注释中预留：

| 钩子位置 | 版本 | 行为 |
|---|---|
| `createRun` 入口 | v0.3 | 评估 `TaskThread.router_policy`，自动选择 `executor_id` |
| `startRun` 执行前 | v0.4 | 分配/准备隔离 git worktree，并写入 `base_path` |
| 事件持久化前 | v0.4 | 支持多个 run 并行流入，按 run_id 分桶排序 |
| Run 进入 `completed` 后 | v0.5+ | 若配置了 QA Agent，自动创建新 Run 并写入 `qa_run_id` |

## 9. Logs / Diff / Review 支撑规则

- Logs：所有 adapter 原生日志都必须归一化为 `RunEvent(type='log')`，可选绑定 `tool_call_id`。
- Diff：`diff` event 是 Changed Files 的首选来源；如果 executor 只输出 tool result，Orchestrator 可以从 `tool_result` 中提取 unified diff 并生成 `ChangedFile`。
- Review：`approval_needed` event 使 `AgentRun.status` 进入 `waiting_review`，`resolveReview` 只写 `ReviewDecision` 并调用 adapter/后端 approval，不直接把 task 标成 done，除非 decision 为 `done`。
- Open in Editor：Orchestrator/Store 提供 `ChangedFile.absolute_path`，UI 只调用 desktop shell 打开文件，不根据 executor 类型拼路径。
