# Agent Fleet Status Contract — Phase 5A 审计与设计

> 状态：**Phase 5A — 审计与设计（修订版，本阶段不实现代码）**
> 日期：2026-06-11
> 基于：Phase 1-4 已推送

---

## 1. 审计：权威来源矩阵

### 1.1 managed-agents.yaml（config/managed-agents.yaml, 657 lines）

10 个注册 Agent。每个有 `agent_id`, `name`, `role`, `runtime`, `model_ref`, `model_strategy`, `can_delegate`, `risk_allowed`, `skills`, `permission`。

**权威性：配置身份是 ground truth。运行时状态不能覆盖配置字段。** `agent_id` 是稳定的 fleet_agent_id。

agent-registry.json 是从 YAML 生成的 JSON 快照（927 lines），含 `routing_rules`。不是独立事实源。YAML 与 JSON 冲突时以 YAML 为准。

### 1.2 Gateway 运行时状态（gateway/status.py → gateway_state.json + gateway.pid）

**持久化文件，独立 CLI 可读：**

```
~/.hermes/gateway_state.json  —  Gateway 运行时健康信息
~/.hermes/gateway.pid         —  Gateway 进程 PID（可验证进程存活）
```

`gateway_state.json` 结构（真实样例，源审 verified）：

```json
{
  "pid": 45768,
  "kind": "hermes-gateway",
  "gateway_state": "running",
  "active_agents": 0,
  "platforms": {
    "feishu": {"state": "connected", "updated_at": "..."},
    "api_server": {"state": "connected", "updated_at": "..."}
  },
  "updated_at": "2026-06-11T01:37:17Z"
}
```

`write_runtime_status()` 由 Gateway 在启动、平台连接/断开、shutdown 时调用。

**权威性：**
- `gateway_state`: Gateway 自身状态（running / stopped / startup_failed）
- `active_agents`: Gateway 管理的活跃 Agent session 数量
- `updated_at`: 最后更新时间戳
- `pid`: 可验证进程存活（`os.kill(pid, 0)`）

**限制：** `active_agents` 是计数，不是 agent_id 列表。无法区分哪些 Managed Agent 在线。

### 1.3 Delegate 活跃注册表（delegate_tool.py:157）

- `_active_subagents`: 进程内 `{subagent_id → {subagent_id, parent_id, depth, goal, model, started_at, status, tool_count}}`
- `list_active_subagents()` 返回快照

**权威性：** 仅进程存活期。Gateway 重启后丢失。Delegate 子 Agent 不进入 Fleet。

### 1.4 Unified Task/Run 投影（Phase 1-3）

| 来源 | 记录 | agent_id 来源 |
|------|------|--------------|
| Pipeline | 747 | `agent_id` 字段（ledger） |
| Delegate | 18 | `model` 字段 + `subagent_session_id` → 不可靠归属，标记 `unassigned_delegate` |
| Kanban | 115 | `assignee`（profile name）→ fleet_agent_id 映射 |

**agent_id 归属规则：**
- Pipeline `agent_id` 字段直接可用（ledger.jsonl 中的 `agent_id`）
- Delegate Run 的 `model` 字段无法可靠反查 fleet_agent_id——多个 managed agents 共用相同 `model_ref`（源审 verified：`opencode_go_deepseek_flash` → deepseek-tui + opencode；`opencode_go_kimi26` → intelligence + pirlo + designer）。Delegate Run/cost **不归属**到任何 fleet_agent_id，全部标记 `unassigned_delegate`
- Kanban `assignee` 是 Kanban profile name，可能与 fleet_agent_id 相同也可能不同。Phase 5B 做 best-effort 字符串匹配；无匹配 → FleetDiagnostic `unknown_kanban_assignee:{name}`
- 无法归属 → FleetDiagnostic，不猜测、不归零、不归第一个匹配项

### 1.5 健康/诊断

- `~/.hermes/gateway_state.json` 平台的 `error_code` / `error_message`
- `~/.hermes/logs/` delegate_timeout 诊断文件
- Kanban `consecutive_failures` > 0

---

## 2. 身份合同

### 2.1 fleet_agent_id

```
fleet_agent_id = managed-agents.yaml 中的 agent_id
```

10 个 fleet agents（稳定、持久化）。

### 2.2 Managed Agent vs Delegate

| 维度 | Managed Agent | Delegate 子 Agent |
|------|:--:|:--:|
| 进入 Fleet | ✅ | ❌ |
| 身份来源 | `managed-agents.yaml` | 无配置 |
| Run/cost 归属 | 直接归属 fleet_agent_id | 不可归属（多 Agent 共用 model_ref），标记 `unassigned_delegate` |

**无法归属的 Delegate Run/cost → FleetDiagnostic `unknown_cost_source`，不猜测、不归零。**

### 2.3 多实例与冲突

- 同一 fleet_agent_id 多个 Gateway session（如 cron worker 多实例）→ 状态聚合（至少一个 online = online）
- 配置重命名 → 旧 agent_id 的 Run 仍归属旧 ID，新 ID 只归属新的
- 配置禁用 → Fleet 仍展示，标记 `disabled`，不要求在线

---

## 3. 五状态模型（修订版）

### 3.1 状态定义

| 状态 | 判定 |
|------|------|
| `online` | `gateway_state.json` 存在 + `gateway_state="running"` + `pid` 进程存活 + `updated_at` 在 5 分钟内 |
| `idle` | `gateway_state.json` 存在 + `gateway_state="running"` + `pid` 存活 + `updated_at` 超过 5 分钟 |
| `offline` | `gateway_state.json` 缺失 或 `gateway_state != "running"` 或 `pid` 不存在 |
| `working` | Unified 投影中该 Agent 存在非终态 Run（`status=running`），与 online/idle/offline 正交 |
| `error` | 最近 1 小时内有 delegate_timeout 诊断、Kanban `consecutive_failures > 0` 或 `gateway_state="startup_failed"`，与 online/working 正交 |

### 3.2 正交性（修订）

`working` 和 `error` 是**正交标志**，不是互斥状态：

```
FleetAgentStatus {
  status: "online" | "idle" | "offline"
  working: boolean
  error: boolean
}
```

| status | working | error | 语义 |
|--------|:--:|:--:|------|
| online | false | false | Gateway 运行中，空闲 |
| online | true | false | 正在执行任务 |
| online | true | true | 正在执行但存在错误 |
| online | false | true | Gateway 运行但异常 |
| idle | false | false | Gateway 静默 |
| offline | false | false | Gateway 未运行 |

**修订原因：** `working > error` 优先级会掩盖错误。Agent 工作中同时有健康错误时必须两者都可见。

### 3.3 故障判定

- **`gateway_state.json` 存在但进程不存在**（PID 不存在）→ `offline` + FleetDiagnostic `stale_pid`
- **`gateway_state.json` 超过 24 小时未更新** → `offline` + FleetDiagnostic `orphaned_state_file`
- **`gateway_state.json` 不存在但 journal 有最近 Run** → `offline` + FleetDiagnostic `gateway_state_missing`
- **仅凭"最后一次任务完成"不得判定 online**

### 3.4 快照时间语义

- `observed_at`：快照生成时的 UTC 时间戳。参与心跳过期判定。
- 确定性 core（managed-agents.yaml、projection）→ byte-identical rebuild
- 观察性字段（`gateway_state.json` 的 `updated_at`、进程存活）→ 仅在 `observed_at` 相同时 byte-identical
- 不同时间的快照可能不同，这是预期行为

---

## 4. 当前工作与统计

### 4.1 当前 Task/Run

来自 Unified 投影中 `status=running` 的 Run，按 fleet_agent_id 分组。

**非终态 Run 不一定表示 Agent 仍在工作。** 只有结合 `gateway_state.json` 的 `active_agents > 0` 或进程存活才提升置信度。否则标记 `stale_run` 诊断。

### 4.2 今日统计

- **时区：Asia/Shanghai（UTC+8）日历日**
- **任务数：** Delegate journal + Kanban Run + Pipeline Run，按 fleet_agent_id 去重
- **成本：** Delegate journal `cost_usd` + Kanban metadata cost。未知 → `null`，不估算
- **跨来源：** 不同命名空间自然隔离，不复计数

### 4.3 Kanban assignee → fleet_agent_id 映射

```
Kanban assignee (profile name) → managed-agents.yaml agent_id
  "claude"    → fleet_agent_id="claude"
  "codex"     → fleet_agent_id="codex"
  "deepseek"  → fleet_agent_id="deepseek-tui"
  无匹配     → FleetDiagnostic "unknown_assignee: {name}"
```

### 4.4 Delegate Run 归属（不可归属）

Delegate journal 的 `model` 字段无法可靠映射到 fleet_agent_id：

源审 verified — 多个 managed agents 共用相同 `model_ref`：
- `opencode_go_deepseek_flash` → deepseek-tui AND opencode
- `opencode_go_kimi26` → intelligence AND pirlo AND designer
- `opencode_go_glm51` → hermes-internal AND ambrosini

只有 `claude` (claude_sonnet)、`codex` (codex_cli)、`agent-tars` (opencode_go_mimo25_pro) 有唯一 model_ref。

**Phase 5B 处理：** 所有 Delegate Run/cost 标记为 `unassigned_delegate`，在 FleetSnapshot 的 summary.diagnostics 中汇总计数。未来如果 delegate journal 记录了 parent_agent_id 或 fleet_agent_id，才可归属。

---

## 5. FleetSnapshot Schema

### 5.1 FleetAgentStatus

```
FleetAgentStatus {
  fleet_agent_id:    string        // managed-agents.yaml agent_id
  display_name:      string        // managed-agents.yaml name
  role:              string        // lead_implementer | fast_worker | ...
  runtime:           string?       // claude_code_cli | codex_cli | ...
  status:            "online" | "idle" | "offline"
  working:           boolean
  error:             boolean
  current_task_id:   string?       // 非终态 Run 的 Task ID
  current_run_id:    string?       // 非终态 Run 的 Run ID
  last_active_at:    timestamp?    // gateway_state updated_at 或最近事件时间
  today_task_count:  int
  today_cost_usd:    float?
  session_count:     int           // gateway_state active_agents
  diagnostics:       [FleetDiagnostic]
}
```

### 5.2 FleetSnapshot

```
FleetSnapshot {
  schema_version:    "fleet_v1"
  observed_at:       timestamp     // 快照生成时的 UTC
  source_watermark: {
    gateway_state_updated_at: timestamp?
    projection_sha:           string?
  }
  agents:            [FleetAgentStatus]
  summary: {
    total:           int
    online:          int
    idle:            int
    offline:         int
    working:         int
    error:           int
  }
  diagnostics:       [FleetDiagnostic]
}
```

### 5.3 存储

```
~/.hermes/projections/fleet/snapshot.json
```

- 原子写入（temp file + os.replace）
- 可删除、可重建的派生视图，不是权威事实源
- 构建失败不修改已有快照

---

## 6. Phase 5B 实现范围

### 6.1 实现内容

| 文件 | 修改量 | 内容 |
|------|--------|------|
| `scripts/fleet-status-build.py` | ~250 行 | 读取 managed-agents.yaml、gateway_state.json + gateway.pid、查询 Unified 投影、聚合 FleetSnapshot |

### 6.2 关键澄清

- **Gateway `_agent_cache` 不可从独立 CLI 读取。** Phase 5B 使用持久化文件 `gateway_state.json` + `gateway.pid`。
- **`active_agents` 是计数不是列表。** 无法区分具体哪个 Agent 在线。Phase 5B 只能判定 Gateway 整体存活，所有 managed agent 的状态基于 gateway_state + projection 推断。
- **Delegate 子 Agent 不进入 Fleet。** 其 Run/cost 归属到 Managed Agent。

### 6.3 测试

| 场景 | 覆盖 |
|------|------|
| managed-agents.yaml 完整解析 | 10 agents |
| gateway_state.json 存在 + pid 存活 → online | ✅ |
| gateway_state.json 缺失 → offline | ✅ |
| gateway_state.json 存在但 pid 不存在 → offline + stale_pid | ✅ |
| 非终态 Run → working=true | ✅ |
| delegate_timeout 诊断 → error=true | ✅ |
| 今日统计跨来源去重 | ✅ |
| 空输入不崩溃 | ✅ |
| rebuild 同 observed_at → byte-identical | ✅ |
| Phase 1-4 417 tests 无回归 | ✅ |

### 6.4 不实现

- ❌ Desktop UI
- ❌ daemon / 自动刷新 / Event Bus
- ❌ 控制命令
- ❌ Postgres / agent-state 文件

---

## 7. 验收标准

1. FleetSnapshot 包含全部 10 个 managed agents
2. `gateway_state.json` 存在 → online/idle；缺失 → offline
3. `working` 和 `error` 正交展示
4. Kanban assignee ↔ fleet_agent_id 映射正确
5. 空数据不崩溃
6. Phase 1-4 417 tests 无回归

---

## 8. 风险和开放问题

| 风险 | 缓解 |
|------|------|
| `active_agents` 是计数，不区分 Agent | 所有 managed agents 共享 online 状态 |
| Delegate model → fleet_agent_id 反查不精确 | 标记 unknown，不猜测 |
| gateway_state.json 未实时更新 | 用 `updated_at` 判定 freshness |
| CLI 模式下无 gateway_state.json | 全部 offline（正常）|
