# Phase 6 — Desktop Agent Fleet UI Closeout

> 日期：2026-06-11
> 状态：**Phase 6C complete**

---

## 1. Commits

| 仓库 | Commit | 说明 |
|------|--------|------|
| .hermes | `361718d46` | Phase 6A: Fleet UI design |
| hermes-desktop | `c27dae4` | Phase 6B: Fleet UI implementation |

---

## 2. 实现

| 层 | 组件 | 说明 |
|----|------|------|
| IPC | `ipcMain.handle("read-fleet-snapshot")` | 无参数、`getHermesHome()`、`realpath` symlink 防护、1MB limit、discriminated union |
| Store | `useFleetSnapshot` singleton hook | refCount + listeners set + pending gate + 30s poller |
| UI | AgentsView dual tab | Current Run (default, preserved) + All Agents (FleetTab) |
| UI | StatusDot | 3 status × 2 working × 2 error = 12 combos + diagnostics icon |
| UI | FleetSummary | sidebar-footer: 四计数分离 (idle≠online), click→Agents |

---

## 3. FleetSnapshot 验证

```
Snapshot: 5082 bytes (<< 1MB limit)
Schema: fleet_v1 ✅
10 agents: 0 online, 10 idle, 0 working, 0 error
Diagnostics: 0, Unassigned: 0
```

---

## 4. 测试

```
Desktop: 844 tests (73 files), 3 skipped ✅
Backend: 439 tests ✅
Phase 1: SHA 508b3c70..., 747 records, 14/14 ✅
```

---

## 5. 已知限制与后续

- GUI smoke 需要真实 Desktop 启动环境验证
- Fleet builder 未集成 daemon（手动运行）
- StatusDot 样式需 CSS 配套
- Desktop 预存 15 个无关改动未提交
