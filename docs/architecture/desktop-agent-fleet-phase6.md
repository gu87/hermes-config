# Desktop Agent Fleet UI — Phase 6A 审计与设计

> 状态：**Phase 6A — 审计与设计（修订版）**
> 日期：2026-06-11
> 基于：Phase 1-5 已推送，FleetSnapshot 已稳定

---

## 1. Desktop 架构审计（源审 verified）

### 1.1 关键边界

```
main (Node.js)              preload (contextBridge)       renderer (React)
─────────────────          ─────────────────────────     ──────────────────
src/main/index.ts           src/preload/index.ts           src/renderer/src/
ipcMain.handle("ch")   →   ipcRenderer.invoke("ch")   →   Layout/Agents/...
                            contextBridge.exposeInMainWorld("hermesAPI", {...})
```

- **源审 verified：** `ipcMain.handle("channel", handler)` 模式（main/index.ts:415+）
- **源审 verified：** `contextBridge.exposeInMainWorld("hermesAPI", {...})`（preload/index.ts:1033-1034）
- **源审 verified：** `readFile` from `fs/promises` 用于读取文件（main/index.ts:13），但仅用于已知固定路径（media attachments）
- **安全约束：** renderer 无法直接访问 Node fs。所有 I/O 必须通过 `hermesAPI` → `ipcRenderer.invoke`

### 1.2 AgentsView（screens/Agents/Agents.tsx）

- **源审 verified：** Agents 是 Layout 中渲染的**直接组件**，不是路由页面（Layout.tsx:333）
- Props：`{ activeProfile, onSelectProfile, onChatWith }`
- 当前展示 profile 列表 + create/delete，无 Fleet 概念
- 使用 React `useState` + `useCallback` 模式

### 1.3 Layout（screens/Layout/Layout.tsx）

- **源审 verified：** Layout 直接导入并渲染 Agents 组件（Layout.tsx:8）
- `sidebar-footer` div（Layout.tsx:248）目前仅含更新按钮
- 无 Status Bar 组件 — 可在此区域增加 Fleet 摘要
- 视图切换通过内部 state 控制（非 React Router）

---

## 2. FleetSnapshot 消费合同

### 2.1 TypeScript 类型（逐字段对齐真实 snapshot.json）

```typescript
interface FleetDiagnostic {
  code: string;
  message: string;
}

interface FleetAgentStatus {
  fleet_agent_id: string;           // 必填，来自 managed-agents.yaml
  display_name: string;             // 必填
  role: string;                     // 必填
  runtime: string | null;           // 可空
  status: "online" | "idle" | "offline";  // 必填
  working: boolean;                 // 必填
  error: boolean;                   // 必填
  current_task_id: string | null;   // 可空
  current_run_id: string | null;    // 可空
  last_active_at: string | null;    // 可空
  today_task_count: number;         // 必填，≥0
  today_cost_usd: number | null;    // 可空（null=unknown, 0=zero_cost）
  session_count: number;            // 必填，≥0
  diagnostics: FleetDiagnostic[];   // 必填，可为空数组
}

interface FleetSnapshot {
  schema_version: string;           // 必填，"fleet_v1"
  observed_at: string;              // 必填，ISO-8601
  source_watermark: {
    gateway_state_updated_at: string | null;
    gateway_pid_alive: boolean;
  };
  agents: FleetAgentStatus[];       // 必填，可为空数组
  unassigned: {
    unassigned_delegate_runs: number;
    unassigned_kanban_assignees: string[];
  };
  summary: {
    total: number;
    online: number;
    idle: number;
    offline: number;
    working: number;
    error: number;
  };
  diagnostics: FleetDiagnostic[];   // 全局诊断（配置错误等）
}
```

### 2.2 消费规则

- **Desktop 不重新计算** online/idle/offline、working/error、24h recency、身份归属
- `schema_version !== "fleet_v1"` → 降级显示 "Fleet data format changed"，不 crash
- `diagnostics.length > 0` → 显示 warning 图标 + tooltip
- `unassigned` → Fleet 表格底部显示 "Unassigned" 汇总行
- `observed_at` → 显示 "Updated: {relative time}"
- `gateway_state_updated_at` 超过 10 分钟无变化 → 显示 "stale" 标签
- 文件不存在 → 降级显示 "Fleet data unavailable"，不影响 Current Run

---

## 3. IPC 设计（修正版）

### 3.1 新增 IPC 通道

**Main handler（src/main/index.ts）：**

```typescript
import { getHermesHome } from "./config";  // 源审 verified: config.ts:873

ipcMain.handle("read-fleet-snapshot", async () => {
  const snapshotPath = path.join(getHermesHome(), "projections", "fleet", "snapshot.json");
  try {
    const stat = await stat(snapshotPath);
    if (stat.size > MAX_FLEET_SNAPSHOT_BYTES) {  // 1 MB
      return { ok: false, error: "snapshot file too large" };
    }
    const raw = await readFile(snapshotPath, "utf-8");
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || data.schema_version !== "fleet_v1") {
      return { ok: false, error: "unsupported schema_version" };
    }
    return { ok: true, snapshot: data as FleetSnapshot };
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return { ok: false, error: "snapshot not found" };
    }
    return { ok: false, error: "snapshot read failed" };
  }
});
```

**Preload bridge（src/preload/index.ts → hermesAPI）：**

```typescript
readFleetSnapshot: (): Promise<FleetSnapshotResult> =>
  ipcRenderer.invoke("read-fleet-snapshot"),
```

**共享类型（src/shared/types/fleet.ts）：**

```typescript
type FleetSnapshotResult =
  | { ok: true; snapshot: FleetSnapshot }
  | { ok: false; error: string };
```

- **严格约束：**
  - 使用 `getHermesHome()`（源审 verified）构造路径，不硬编码 `~/.hermes`
  - **不接受任何 renderer 参数**，防止任意文件读取
  - 文件大小上限 1 MB（`MAX_FLEET_SNAPSHOT_BYTES`）
  - 错误净化：不向 renderer 暴露文件系统绝对路径、堆栈或敏感内容
  - `schema_version !== "fleet_v1"` → `{ ok: false }` 降级，不渲染部分错误数据
  - handler 重复注册：使用 `ipcMain.handle`（幂等，后注册覆盖前）— 在开发热重载下安全
- **discriminated union** `{ ok: true } | { ok: false }` — TypeScript narrows after `if (result.ok)`

### 3.2 单例 Store 与轮询

**设计：** 单一 `useFleetSnapshot()` hook 被 AgentsView 和 sidebar-footer 共享。

```
useFleetSnapshot():
  - 内部维护 { data, error, stale, lastFetchAt } state
  - 订阅计数 refCount：首次订阅 → start poller；最后一次取消 → stop
  - 30s 轮询（仅在 Fleet tab active 或 sidebar-footer visible）
  - 防重叠：pending 为 true 时跳过新请求
  - 超时保护：invoke 超过 10s → 视为失败，允许下次请求
  - Last-known-good：新请求失败时保留旧 data，标记 stale=true
  - 手动刷新：与轮询共享同一 pending gate

订阅生命周期：
  AgentsView mount (Fleet tab) → refCount++
  Layout mount (sidebar-footer) → refCount++
  AgentsView unmount → refCount--
  Layout unmount → refCount--
  refCount 0→1：启动轮询
  refCount 1→0：停止 + 清除 timer
  window hidden → 暂停轮询（保留 data）
  window shown → 立即 fetch + 恢复轮询

---

## 4. UI/UX 设计（修正版）

### 4.1 Agents 组件双 Tab

Agents 组件内部使用本地 state 切换两个视图：

```tsx
function Agents({ activeProfile, onSelectProfile, onChatWith }: AgentsProps) {
  const [activeTab, setActiveTab] = useState<"current" | "fleet">("current");
  ...
  return (
    <div className="agents-view">
      <div className="agents-tabs">
        <button onClick={() => setActiveTab("current")}>Current Run</button>
        <button onClick={() => setActiveTab("fleet")}>All Agents ({fleetSummary?.total ?? "—"})</button>
      </div>
      {activeTab === "current" ? <CurrentRunView ... /> : <FleetTab ... />}
    </div>
  );
}
```

### 4.2 Fleet 表格

| Status | Agent | Role | Tasks Today | Cost | Diagnostics |
|--------|-------|------|-------------|------|-------------|
| ● idle | Claude 主程执行官 | lead_implementer | 2 | $— | — |
| ● idle | DeepSeek 低成本快工 | fast_worker | 6 | $— | — |

- 默认排序：status（online > idle > offline）→ fleet_agent_id alphabetical
- Cost `null` → "$—"；`0` → "$0.00"
- Diagnostics > 0 → ⚠ icon + tooltip

### 4.3 StatusDot 设计

```
status dot (position: left) + badge overlays (right of dot)
  online = ● green
  idle   = ◉ gray
  offline = ○ outline

  working = ⚡ yellow badge (independent)
  error   = ✕ red badge (independent)

组合示例：
  ● idle + ⚡ working → gray dot + yellow "working" badge
  ○ offline + ✕ error → outline dot + red "error" badge
  ● online → green dot only
  ○ offline + ⚡ working → outline dot + yellow badge + ⚠ tooltip "Run without gateway"
  ● idle + ✕ error + ⚡ working → gray dot + both badges
```

**冲突组合处理：**
- `working=true + status=offline` → 数据显示不变，但该行增加 ⚠ icon + tooltip "Agent has active runs but gateway is offline — data may be stale"
- `error=true + working=true` → 两者都显示，不互斥
- `diagnostics.length > 0` → 该行最右侧增加 ⓘ icon，hover 显示 diagnostic 列表

### 4.4 Current Run 行为保留

- **Current Run Tab 默认显示**（`activeTab` 初始值为 `"current"`）
- 现有 profile 列表、create、delete、select、chat with 逻辑**完全不变**
- 新增 Fleet tab 通过 `setActiveTab("fleet")` 切换，不影响 Current Run 的任何 state 或流式更新
- 快捷键和现有交互保持不变

### 4.5 Unassigned 与 Diagnostics 可见性

- Fleet 表格底部固定行 "Unassigned"（当 `unassigned` 非零时显示）
- 每行 diagnostics > 0 → ⓘ icon + tooltip
- Fleet 表格顶部全局 diagnostics → banner（可关闭）

### 4.4 Status Bar 摘要（Layout sidebar-footer）

```
┌──────────────────────────────────────────────┐
│ ● 0 online  ◉ 10 idle  10 agents total      │
│ ⚡ 0 working  ✕ 0 error                      │
│ Updated: 2 min ago                      [↻]  │
└──────────────────────────────────────────────┘
```

- **online count：** 仅 `summary.online`，不包含 idle
- **idle count：** `summary.idle`（gateway 存活但 stale）
- **working count：** `summary.working`，无 working 时隐藏此行
- **error count：** `summary.error`，无 error 时隐藏此行
- **不将 idle 算入 online** — 避免误导
- 点击摘要 → 切换 Agents 到 Fleet tab
- `snapshot` 缺失时整个摘要隐藏（不显示占位符）

### 4.5 状态处理

| 状态 | 展示 |
|------|------|
| loading | Fleet 表格区域显示 skeleton |
| empty (0 agents) | "No managed agents configured" |
| stale (>10 min since observed_at) | yellow banner "Data may be stale" |
| snapshot 缺失 | "Fleet data unavailable" |
| schema mismatch | "Fleet data format changed — update Desktop" |
| partial (部分 agents 有 diagnostic) | ⚠ icon + tooltip per row |

---

## 5. Phase 6B 实现范围（修正版）

### 5.1 修改文件

| 文件 | 修改量 | 内容 |
|------|--------|------|
| `src/main/index.ts` | +20 lines | `ipcMain.handle("read-fleet-snapshot")` |
| `src/preload/index.ts` | +8 lines | `hermesAPI.readFleetSnapshot()` |
| `src/shared/types/fleet.ts` | +60 lines | 共享 FleetSnapshot 类型（新增文件） |
| `src/renderer/src/screens/Agents/Agents.tsx` | +50 lines | 双 Tab + Fleet snapshot fetch |
| `src/renderer/src/screens/Agents/FleetTab.tsx` | +150 lines | 新组件：Fleet 表格 + StatusDot |
| `src/renderer/src/screens/Layout/Layout.tsx` | +30 lines | sidebar-footer Fleet 摘要 |
| `src/renderer/src/components/StatusDot.tsx` | +40 lines | 正交状态 dot 组件 |

### 5.2 测试

- `FleetTab.test.tsx`：正常渲染、loading、empty、stale、schema mismatch、error
- `StatusDot.test.tsx`：全部组合（3 status × 2 working × 2 error = 12 combos）
- `Layout.test.tsx`：Fleet 摘要显示/隐藏
- IPC smoke test：`read-fleet-snapshot` 返回 mock snapshot
- 现有 Agents.test.tsx 保持通过

### 5.3 不实现

- ❌ 控制 CLI 集成、费用图表、详情面板、告警
- ❌ OpenClaw 后端/Mission Control
- ❌ Fleet builder daemon/自动刷新
- ❌ 通用文件读取 API

### 5.4 验收标准

1. Agents 双 Tab：Current Run 行为不变；All Agents 显示 Fleet 表格
2. StatusDot 正确展示 12 种组合
3. Layout sidebar-footer 显示 Fleet 摘要
4. Snapshot 缺失时安全降级
5. 439 backend tests 无回归
6. Desktop build + type check 通过

---

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `docs/architecture/desktop-agent-fleet-phase6.md` | 本设计文档（修订版） |

Phase 6B 预计 7 files, ~358 lines。
