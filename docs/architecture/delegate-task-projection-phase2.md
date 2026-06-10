# Delegate Task — Phase 2A 审计与统一投影设计

> 状态：**Phase 2A — 审计与设计（第三轮修订，本阶段不实现代码）**
> 日期：2026-06-10
> 基于：Phase 1D commit `c8abf7bf0`

---

## 1. 审计范围

### 1.1 源码

| 文件 | 行数 | 角色 |
|------|------|------|
| `hermes-agent/tools/delegate_tool.py` | 2829 | delegate_task 工具定义、子 Agent 构造、执行、事件 relay；line 2815 registry handler |
| `hermes-agent/agent/agent_runtime_helpers.py` | ~2000 | `invoke_tool()` 并发路径：line 1752 调用 `_dispatch_delegate_task`，**未传播 tool_call_id** |
| `hermes-agent/agent/tool_executor.py` | ~1000 | 顺序路径：line 960 调用 `_dispatch_delegate_task`，**未传播 tool_call_id** |
| `hermes-agent/run_agent.py` | ~5000 | `_dispatch_delegate_task` line 4793：接收 `function_args`，**无 tool_call_id 参数** |
| `hermes-agent/agent/memory_manager.py` | ~700 | `on_delegation()` 将委派结果告知父 Agent 记忆层 |
| `hermes-agent/tools/file_state.py` | ~350 | 进程内文件读写注册表 |
| `hermes-agent/hermes_state.py` | — | Gateway SessionDB：持久化 session_id、parent_session_id、messages |

### 1.2 测试

```
hermes-agent/tests/tools/test_delegate.py — 135 passed
```

---

## 2. 当前真实调用链和数据流

### 2.1 入口 — 三条路径均丢失 tool_call_id

**路径 A — 顺序（tool_executor.py:960）：**
```
LLM tool_call (id="toolu_xxx") → tool_executor.py
  tool_call_id = tool_call.id   ← 存在，可用
  function_result = agent._dispatch_delegate_task(function_args)
                     ↑ tool_call_id 未传播 ❌
```

**路径 B — 并发（agent_runtime_helpers.py:1752）：**
```
invoke_tool(agent, ..., tool_call_id="toolu_xxx", ...)
  tool_call_id 作为参数存在 ← 存在，可用
  return _finish_agent_tool(agent._dispatch_delegate_task(function_args))
                             ↑ tool_call_id 未传播 ❌
```

**路径 C — registry handler（delegate_tool.py:2815）：**
```
registry.register(
    handler=lambda args, **kw: delegate_task(
        ..., parent_agent=kw.get("parent_agent"),
    ),
)
```
当前 `**kw` 可能包含 `tool_call_id`（取决于调度层是否传入），但 handler 未显式接收。此路径在顺序/并发内联处理中通常不被触发，但作为注册入口仍需覆盖。

### 2.2 delegate_task 执行流程

```
delegate_task(parent_agent)   ← 当前无 tool_call_id 参数
  │
  ├─ _build_child_agent(task_index, goal, ..., parent_agent)
  │   ├─ subagent_id = "sa-{task_index}-{uuid8}"      ← 随机 UUID
  │   ├─ parent_subagent_id = getattr(parent, "_subagent_id", None)
  │   ├─ child_depth = parent._delegate_depth + 1
  │   └─ child 继承 parent._session_db, parent.session_id
  │       子 Agent 的 session_id 是新生成的 UUID
  │       子 session 的 parent_session_id = 直接父 Agent 的 session_id
  │
  └─ _run_single_child(task_index, goal, child, parent)
       ├─ _register_subagent({...})  → _active_subagents 内存字典
       ├─ child.run_conversation(user_message=goal, task_id=child_task_id)
       │   SessionDB 持久化：子 session（session_id, parent_session_id, messages, tokens, cost）
       └─ 返回结果：status, summary, api_calls, duration, tokens, tool_trace, cost
```

### 2.3 嵌套委派的 session 结构（关键审计发现）

```
Top Agent (session=S0)
  │
  └─ delegate_task → orchestrator
       orchestrator 获得新 session S1
       S1.parent_session_id = S0
       │
       └─ orchestrator 内部 delegate_task → leaf worker
            leaf worker 获得新 session S2
            S2.parent_session_id = S1   ← 是直接父，不是 S0

parent_session_id 始终指向直接父 Agent，不是顶层 Agent。
不能用 parent_session_id 跨层级查找根 Task。
```

---

## 3. 权威事实源清单

### 3.1 已持久化的事实

| 事实 | 存储 | 格式 |
|------|------|------|
| 父 session_id | SessionDB | UUID |
| 子 session_id | SessionDB | UUID |
| parent_session_id → child_session_id | SessionDB（子 session 记录） | UUID |
| 子 Agent 对话 messages | SessionDB | JSON |
| 子 Agent token/cost/model | SessionDB（子 session） | int/float/str |
| delegate_timeout 诊断 | `~/.hermes/logs/` | 文本（仅 0-API-call 超时） |

### 3.2 仅内存中的事实

| 事实 | 说明 |
|------|------|
| subagent_id、parent_subagent_id、depth、role | 委派树拓扑 |
| goal、context、toolsets | 仅 prompt 文本 |
| task_index | 单次调用内稳定 |
| _active_subagents | TUI 运行时注册表 |
| file_state | 进程内 |

### 3.3 关键约束：phase killing 不可靠

`AIAgent.close()` (run_agent.py:2889) **不调用** `end_session()`。`end_session()` 仅由 Gateway (tui_gateway/server.py:384)、CLI (cli.py:15462)、compression (conversation_compression.py:507) 等外部调用者显式触发。子 Agent 的 session `ended_at` 可能永远为 NULL。

**结论：** Phase 2 无可用于子 Agent 的可靠进程终止事实。started-only 不能判定为 crashed，必须保守投射为 running/unknown。

### 3.4 结论

SessionDB 已有足够数据证明委派发生过，但无法确定性重建统一的 Task、Run、RunRelation 语义。进程终止状态在 Phase 2 范围内不可靠。

---

## 4. 双阶段持久化设计

### 4.1 阶段 1：子 Run started（执行前）

在 `_run_single_child` 中、子 Agent 开始执行前，追加：

```jsonl
{"schema_version":"delegate_v1","phase":"run_started","parent_session_id":"uuid-S0","delegate_call_id":"toolu_xxx","task_index":0,"subagent_session_id":"uuid-s1","parent_delegate_task_id":null,"parent_delegate_run_id":null,"root_task_id":null,"depth":1,"role":"leaf","goal":"...","toolsets":["read","write"],"model":"claude-sonnet-4-6","started_at":"2026-06-10T15:00:00.123456+00:00"}
```

### 4.2 阶段 2：子 Run terminal（执行后）

在 finally 块中追加：

```jsonl
{"schema_version":"delegate_v1","phase":"run_finished","parent_session_id":"uuid-S0","delegate_call_id":"toolu_xxx","task_index":0,"subagent_session_id":"uuid-s1","parent_delegate_task_id":null,"parent_delegate_run_id":null,"root_task_id":null,"depth":1,"status":"completed","summary":"...","exit_reason":"completed","api_calls":12,"duration_seconds":43.1,"tokens":{"input":5000,"output":1200},"cost_usd":0.042,"tool_trace":[...],"files_written":["path/to/file.py"],"files_read":["path/to/src.py"],"error":null,"ended_at":"2026-06-10T15:00:43.000000+00:00"}
```

### 4.3 started-only 的确定性判定（P0 修订）

Phase 2 无可靠持久化进程终止事实。started-only 判定规则：

| 条件 | 统一 RunStatus | 统一 outcome | 说明 |
|------|---------------|-------------|------|
| 有 started + terminal | terminal status 映射 | terminal outcome 映射 | 正常完成 |
| 只有 started | `running` | `null` | **保守默认**：Phase 2 无可靠终止证据 |

`crashed` 判定推迟到未来 Phase（引入显式 process/session finalize journal 记录后）。在此期间：

- 无 `AIAgent.close()` → `end_session()` 调用链保证
- 子 Agent session 的 `ended_at` 可能永久为 NULL
- 禁止依赖 SessionDB `ended_at` / `end_reason` 判定 crashed

**byte-identical rebuild 保证：** started-only → `running` 是无条件确定性规则，不依赖当前时间或任何外部状态。相同 journal 输入始终产生相同结果。

---

## 5. 确定性 ID 规则

### 5.1 delegate_call_id 来源

`delegate_call_id` 来自 LLM API 返回的 `tool_call.id`（如 `toolu_01ABC123...`），在同一 turn 内唯一标识每次 `delegate_task()` 调用。

**传播路径（Phase 2B 必须打通四条节点）：**

| # | 文件:行 | 当前状态 | Phase 2B 修改 |
|---|---------|----------|--------------|
| 1 | `delegate_tool.py:delegate_task()` | 无 `tool_call_id` 参数 | 增加 `tool_call_id: Optional[str] = None` |
| 2a | `tool_executor.py:960`（顺序路径） | `agent._dispatch_delegate_task(function_args)` | `agent._dispatch_delegate_task(function_args, tool_call_id=tool_call.id)` |
| 2b | `agent_runtime_helpers.py:1752`（并发路径） | `agent._dispatch_delegate_task(function_args)` | `agent._dispatch_delegate_task(function_args, tool_call_id=tool_call_id)` |
| 2c | `delegate_tool.py:2815`（registry handler） | `lambda args, **kw: delegate_task(...)` 未显式接收 | 增加 `tool_call_id=kw.get("tool_call_id")`；若 `tool_call_id` 为 None → MappingError |
| 3 | `run_agent.py:_dispatch_delegate_task` | 无 `tool_call_id` 参数 | 增加参数，透传到 `delegate_task()` |
| 4 | `delegate_tool.py:_run_single_child` | 通过 `delegate_task` 获取 | 写入 journal started/terminal 记录 |

**路径 2c 兼容策略：** registry handler 通过 `**kw` 接收调度层传入的参数。如果 `tool_call_id` 不在 `**kw` 中（旧调度层或测试桩），`delegate_task` 收到 `tool_call_id=None`。当 `tool_call_id` 为空且 `parent_session_id` 不为空时，无法生成确定性 journal 记录 → journal 写入跳过 + logger.warning。投影器在缺少 `delegate_call_id` 时返回 `MappingError`。

### 5.2 ID 公式

```
namespace = "delegate"

task_id = "delegate:{subagent_session_id}:task:{delegate_call_id}:{task_index}"
run_id  = "delegate:{subagent_session_id}:run:{delegate_call_id}:{task_index}"

# TaskRelation（仅当 journal 有显式 parent_delegate_task_id）
relation_id = "tr_{child_task_id}_delegation"

# RunRelation（仅当 journal 有显式 parent_delegate_run_id）
relation_id = "dr_{child_run_id}_{parent_delegate_run_id}"

# DomainEventEnvelope
event_id = SHA-256(
    "delegate:{subagent_session_id}:{delegate_call_id}:{task_index}:{phase}"
)[:32]
```

### 5.3 字段稳定性

| 字段 | 来源 | 跨重启稳定？ |
|------|------|-------------|
| `subagent_session_id` | 子 Agent 的 `session_id`（SessionDB UUID） | ✅ |
| `delegate_call_id` | LLM API `tool_call.id` | ✅ |
| `task_index` | 单次 delegate_task 调用内 0-based 索引 | ✅ |
| `phase` | `"run_started"` / `"run_finished"` | ✅ |

### 5.4 缺少稳定身份

| 缺失 | 行为 |
|------|------|
| `subagent_session_id` 为空 | `MappingError` |
| `delegate_call_id` 为空 | `MappingError` |

**禁止 timestamp、PID、随机 ID 回退。**

---

## 6. 统一实体映射

### 6.1 delegate_task 调用 → Task

```
每次 (delegate_call_id, task_index) → 一个统一 Task

Task:
  id:            "delegate:{subagent_session_id}:task:{delegate_call_id}:{task_index}"
  title:         journal started 中的 goal[:200]
  status:        running（只有 started）/ completed / failed
  created_at:    started_at
  root_task_id:  journal 中的 root_task_id 字段；null 时 = 自身
```

### 6.2 子 Agent 执行 → Run

```
每次 (delegate_call_id, task_index) → 一个统一 Run

Run:
  id:              "delegate:{subagent_session_id}:run:{delegate_call_id}:{task_index}"
  task_id:         "delegate:{subagent_session_id}:task:{delegate_call_id}:{task_index}"
  parent_run_id:   journal 中的 parent_delegate_run_id（可能为 null）
  run_type:        "delegated"
  executor_id:     "hermes-local"
  agent_id:        子 Agent 使用的 managed agent ID
  status:          running / completed / failed / cancelled
  outcome:         completed | failed | timeout | interrupted | error
  note:            Phase 2 不投射 outcome=crashed
```

### 6.3 状态映射

| journal terminal status | RunStatus | outcome |
|------------------------|-----------|---------|
| `completed` | `completed` | `completed` |
| `failed` | `failed` | `failed` |
| `timeout` | `failed` | `timeout` |
| `error` | `failed` | `error` |
| `interrupted` | `cancelled` | `interrupted` |
| (only started) | `running` | `null` |

### 6.4 嵌套委派 — 显式字段设计

**journal 必须持久化的三个显式字段：**

| 字段 | 含义 | 示例 |
|------|------|------|
| `parent_delegate_task_id` | 直接父委派的统一 Task ID | `"delegate:{s1}:task:tc1:0"` |
| `parent_delegate_run_id` | 直接父委派的统一 Run ID | `"delegate:{s1}:run:tc1:0"` |
| `root_task_id` | 委派树的根统一 Task ID | `"delegate:{s0}:task:tc0:0"` |

在 `_build_child_agent` 中，从 `parent_agent` 获取这些值（如果父是顶层 Agent 则为 null）。

**示例：三层委派树**

```
Top Agent (session=S0)
  │
  └─ delegate_task(tool_call_id="tc0")
       └─ orchestrator (session=S1)
            parent_delegate_task_id = null
            parent_delegate_run_id = null
            root_task_id = null  → 投影时设为自身
            │
            └─ delegate_task(tool_call_id="tc1")
                 └─ leaf worker (session=S2)
                      parent_delegate_task_id = "delegate:S1:task:tc0:0"
                      parent_delegate_run_id = "delegate:S1:run:tc0:0"
                      root_task_id = "delegate:S1:task:tc0:0"
                      │
                      └─ delegate_task(tool_call_id="tc2")
                           └─ leaf worker (session=S3)
                                parent_delegate_task_id = "delegate:S2:task:tc1:0"
                                parent_delegate_run_id = "delegate:S2:run:tc1:0"
                                root_task_id = "delegate:S1:task:tc0:0"
```

**journal 记录示例（tc2 的 leaf worker）：**

```jsonl
{"phase":"run_started","parent_session_id":"S0","delegate_call_id":"tc2","task_index":0,"subagent_session_id":"S3","parent_delegate_task_id":"delegate:S2:task:tc1:0","parent_delegate_run_id":"delegate:S2:run:tc1:0","root_task_id":"delegate:S1:task:tc0:0","depth":3,...}
```

**统一投影产出：**

```
TaskRelation(parent_child):
  parent="delegate:S2:task:tc1:0"
  child="delegate:S3:task:tc2:0"

RunRelation(delegated):
  parent_run_id="delegate:S2:run:tc1:0"
  child_run_id="delegate:S3:run:tc2:0"
```

### 6.5 Parent Run/RunRelation 缺失处理

- journal 中 `parent_delegate_run_id` 不为 null → 生成 `RunRelation(type=delegated)`
- journal 中 `parent_delegate_run_id` 为 null → 不生成 RunRelation
- **禁止**从 Task/时间排序推断 parent_run_id
- **禁止**用 `parent_subagent_id`（随机 UUID）跨 session 查找父 Task
- `parent_delegate_task_id` 和 `parent_delegate_run_id` 是统一投影的确定性 ID，在父委派完成时已确定

### 6.6 兄弟 Task 不共享 root

```
parent_delegate_task(parent=S0)
  ├─ batch[task_index=0]  root_task_id = "delegate:S0:task:tc:0"  ← 自身
  └─ batch[task_index=1]  root_task_id = "delegate:S0:task:tc:1"  ← 自身，非兄弟
```

批量调用中的每个子 Task 有独立的 root_task_id。**不因 task_index 顺序或 goal 文本相似推断共享 root。**

---

## 7. 事件映射（Phase 2 范围）

Phase 2B 仅支持已在 journal 中有确定性身份的事件：

| 事件 | event_type | event_scope | event_id 输入 |
|------|-----------|-------------|--------------|
| journal `run_started` | `delegate.run_started` | `run` | subagent_session_id + delegate_call_id + task_index + "started" |
| journal `run_finished` | `delegate.run_finished` | `run` | subagent_session_id + delegate_call_id + task_index + "finished" |

**不在 Phase 2 范围内的事件：**
- `subagent.spawn_requested` / `subagent.thinking` / `subagent.tool` / `subagent.progress` — 无稳定 source_event_id，不持久化，不进入 DomainEventEnvelope

---

## 8. Journal 协议

### 8.1 存储位置

```
~/.hermes/delegations/{parent_top_session_id}.jsonl
```

以顶层 session 为文件边界。每个父顶层 session 一个 JSONL 文件。

### 8.2 写入协议

```
1. open(path, "a", encoding="utf-8")         ← O_APPEND
2. fcntl.flock(fd, LOCK_EX)
3. line = json.dumps(record, ensure_ascii=False) + "\n"
4. os.write(fd, line.encode("utf-8"))         ← 单次 write
5. os.fsync(fd)
6. fcntl.flock(fd, LOCK_UN)
7. close(fd)
```

### 8.3 投影读取与配对规则

**配对键：** `(parent_session_id, delegate_call_id, task_index)`

投影器构建时：
1. 扫描全量 journal，按配对键分桶
2. 每个桶内匹配 started 和 terminal 记录
3. 应用异常边界规则（见 §8.4）

### 8.4 异常边界规则（P1 补全）

| 场景 | 行为 |
|------|------|
| 一条 started + 一条 terminal | ✅ 正常投影 |
| 只有 started（无 terminal） | 投影 Run: status=`running`, outcome=`null` |
| 只有 terminal（无 started） | `MappingError` — 无法构建完整 Task/Run |
| 两条 byte-identical started | 去重：仅保留一条 |
| 两条 byte-identical terminal | 去重：仅保留一条 |
| 两条 started，内容不同 | `MappingError` — journal 数据冲突 |
| 两条 terminal，内容不同 | `MappingError` — journal 数据冲突 |
| 单行 JSON 解析失败 | `MappingError(error="bad journal line", source_location="{path}:{line_number}")`，**继续处理后续行** |

### 8.5 部分写入恢复

- 普通文件 `write()` 不提供 POSIX 原子性保证。单次 `write()` 在本地文件系统上通常完整，但在 NFS、容器文件系统或 I/O 错误下可能产生部分行
- 投影器逐行 `json.loads()` → 解析失败按 §8.4 坏行规则处理
- **不使用** `os.replace()` 临时文件方案（对追加式 journal 架构不正确）

### 8.6 并发

- 同一顶层 session 的 delegate_task 调用串行（父 Agent 阻塞等待），同文件无并发写
- `flock(LOCK_EX)` 为防御性措施
- 不同 session → 不同文件，天然无冲突

### 8.7 Journal 与投影

```
~/.hermes/delegations/*.jsonl     ← 权威 journal，不可随意删除
                                        丢失 = 事实永久丢失
~/.hermes/projections/delegate-task/*/events.jsonl  ← 统一投影
                                        可安全删除、从 journal + SessionDB 完整重建
```

---

## 9. Phase 2B 实现范围

### 9.1 代码修改

| 文件 | 修改量 | 内容 |
|------|--------|------|
| `hermes-agent/tools/delegate_tool.py` | +~40 行 | `delegate_task()` 增加 `tool_call_id` 参数；`_run_single_child` 增加两处 journal 写入；`_build_child_agent` 增加关系字段设置；registry handler 增加 `tool_call_id` 提取 |
| `hermes-agent/run_agent.py` | +~5 行 | `_dispatch_delegate_task` 增加 `tool_call_id` + 显式关系字段参数 |
| `hermes-agent/agent/tool_executor.py` | +~3 行 | 路径 A：传入 `tool_call_id=tool_call.id` + 关系字段 |
| `hermes-agent/agent/agent_runtime_helpers.py` | +~3 行 | 路径 B：传入 `tool_call_id=tool_call_id` + 关系字段 |
| `scripts/task-run-projection.py` | +~300 行 | delegation 映射函数 + 异常边界规则 + 关系处理 |
| `scripts/task-run-projection-build.py` | +~50 行 | delegation journal 数据源 |

### 9.2 测试要求

| 测试场景 | 覆盖 |
|----------|------|
| 正常完成/超时/失败/中断 | journal started + terminal 正确写入 |
| 批量并行 | 每个 task_index 有独立 started/terminal |
| 嵌套委派 | parent_delegate_task_id/run_id/root_task_id 链正确 |
| tool_call_id 传播 — 路径 A | 顺序：`tool_call.id` 传入 |
| tool_call_id 传播 — 路径 B | 并发：`invoke_tool` 参数传入 |
| tool_call_id 传播 — 路径 C | registry handler：`**kw` 提取；缺失时 handle |
| started-only | status=`running`, outcome=`null` |
| 确定性 ID | 同 session + delegate_call_id + task_index → 同 ID |
| 缺失字段 | `subagent_session_id`/`delegate_call_id` → MappingError |
| 缺失 parent_run | `parent_delegate_run_id`=null → 不生成 RunRelation |
| 异常 journal | 重复行去重/冲突 MappingError/只有 terminal MappingError/坏行继续 |

### 9.3 不实现

- ❌ 流式事件（thinking、tool、progress）
- ❌ Gateway SessionDB schema 修改
- ❌ Kanban / Desktop / Orchestrator 接入
- ❌ 改变 delegate_task 工具限制/审批/隔离
- ❌ 从 prompt/goal/时间/顺序推断结构化关系
- ❌ 自动判定 crashed（Phase 2 无可靠终止证据）

---

## 10. 验收标准

1. delegate_task 135 tests 通过
2. journal 写入不改变 delegate_task 返回值
3. 确定性 ID：相同输入 → 相同 Task/Run/Event ID
4. started-only → status=`running`, outcome=`null`（无条件确定性规则）
5. 缺 `subagent_session_id` / `delegate_call_id` → MappingError
6. 缺 `parent_delegate_run_id` → 不生成 RunRelation
7. byte-identical rebuild：删除投影 → 从 journal 重建 → 逐字节一致
8. 三条 tool_call_id 传播路径全部覆盖
9. 异常 journal 场景全部有明确行为
10. journal 去重：byte-identical 行不产生重复投影记录

---

## 11. 风险和开放问题

| 风险 | 缓解 |
|------|------|
| CLI 模式无 SessionDB → `subagent_session_id` 可能不可用 | 需调研 CLI 子 Agent 是否产生 session_id；若无 → MappingError |
| `tool_call_id` 在非标准 provider 下可能为 None | 检测 → MappingError；journal 写入跳过 + logger.warning |
| 进程 SIGKILL 后 terminal 未写入 | started 已 fsync；started-only → `running`，不误判 crashed |
| started-only 记录随时间累积 | 投影始终映射为 `running`；未来 Phase 引入显式 finalize 后标记为 `crashed` |
| registry handler `**kw` 中 tool_call_id 缺失 | delegate_task 收到 None → journal 跳过 + log；投影器报 MappingError |
| 批量调用中部分子 Agent 完成前父进程崩溃 | 已完成的 terminal 已 fsync；未完成的只有 started → `running` |

---

## 12. 文件清单

### 本阶段

| 文件 | 说明 |
|------|------|
| `docs/architecture/delegate-task-projection-phase2.md` | 本设计文档（第三轮修订） |

### Phase 2B 预计

| 文件 | 修改量 |
|------|--------|
| `hermes-agent/tools/delegate_tool.py` | +~40 行 |
| `hermes-agent/run_agent.py` | +~5 行 |
| `hermes-agent/agent/tool_executor.py` | +~3 行 |
| `hermes-agent/agent/agent_runtime_helpers.py` | +~3 行 |
| `scripts/task-run-projection.py` | +~300 行 |
| `scripts/task-run-projection-build.py` | +~50 行 |
| `tests/test_task_run_projection.py` | +~250 行 |
| `tests/test_task_run_projection_build.py` | +~120 行 |
