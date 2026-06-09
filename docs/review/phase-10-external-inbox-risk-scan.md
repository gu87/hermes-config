# Phase 10 External Inbox 风险扫描

> 检查 v0.8 `InboxManager` + 外部入口的安全风险。

扫描日期：2026-06-04
扫描范围：
- `hermes-agent/executors/inbox.py` — InboxManager 核心
- `hermes-agent/executors/inbox_cli.py` — CLI 子命令
- `hermes-agent/executors/types.py` — InboxItem / InboxSource / InboxStatus 类型

---

## 风险总览

| # | 风险 | 严重度 | 结论 |
|---|------|--------|------|
| 1 | 外部 item 是否会自动执行 | ✅ 不会 | 纯 CRUD，无自动触发 |
| 2 | 是否绕过 task review | ✅ 不会 | 转换后走正常 task 创建 |
| 3 | 是否绕过 permission gate | ✅ 不会 | 不含任何执行逻辑 |
| 4 | raw_payload 是否可能污染 | 🟡 中危 | 明文存储，建议加大小限制 |
| 5 | source 字段是否可信 | 🟡 中危 | 自报 source，当前仅用于显示 |
| 6 | convert 是否允许用户编辑 | ✅ 允许 | `update_draft()` + `user_edited` 标记 |
| 7 | result 回写是否绑定 | ✅ 绑定 | `inbox_item_id` + `run_id` 双字段 |
| 8 | stub 是否清楚显示 | ✅ 清楚 | "unavailable — stub" 显示 |
| 9 | 是否有隐藏自动化入口 | ✅ 没有 | 纯 CLI CRUD，无 scheduler/poller |

---

## 1. 外部 Item 不会自动执行 ✅

`add()` 只创建 PENDING 状态 item，不触发任何执行。`convert_to_task()` 只标记状态为 CONFIRMED + 关联 task_id，不启动 task。没有任何自动消费/执行的代码路径。所有状态转换都需要用户通过 CLI 显式调用。

**风险等级**：🟢 无风险。

---

## 2. 不绕过 Task Review ✅

`convert_to_task()` 不创建 `TaskThread` 或 `AgentRun`，不调用任何 executor，不跳过 review gate。inbox 不参与任务执行生命周期。

**风险等级**：🟢 无风险。

---

## 3. 不绕过 Permission Gate ✅

`inbox.py` 不含任何权限检查或执行逻辑——无 `PermissionGuard`、无 `PolicyEngine`、无 `ReviewGate` 调用。纯存储层。

**风险等级**：🟢 无风险。

---

## 4. raw_payload 污染风险 🟡 中危

**位置**：`types.py` 第 467 行 / `inbox.py` 第 111 行

```python
class InboxItem:
    raw_payload: Dict[str, Any] = field(default_factory=dict)
```

`raw_payload` 是自由格式 dict，不做大小或内容校验直接存储到 `inbox.json`。

**当前风险可控**：`raw_payload` 不自动注入到 prompt——prompt 从 `draft.suggested_prompt` 生成。Python 的 `json.loads` 反序列化安全。

**建议**：在 `add()` 中增加 payload 大小限制：

```python
MAX_PAYLOAD_BYTES = 65536
if raw_payload and len(json.dumps(raw_payload)) > MAX_PAYLOAD_BYTES:
    raise ValueError(f"raw_payload exceeds {MAX_PAYLOAD_BYTES} bytes")
```

---

## 5. Source 字段自报，无验证 🟡 中危

**位置**：`inbox.py` 第 87 行

```python
def add(self, source: InboxSource, ...):
```

`source` 由调用者传入，任何代码路径都可以用任何来源值调用。CLI 也可以传入 `FEISHU`。

**当前无风险**：source 仅用于 UI 显示和 writeback 可用性判断，不用于权限决策。

**建议**：如果未来增加 source-based 自动执行，必须通过签名验证或 API 密钥验证来源真实性。

---

## 6. 用户可编辑 Draft ✅

`update_draft()` 允许编辑 title、prompt、executor、project、priority。编辑后 `user_edited = True`。编辑是用户显式触发，不存在静默改写。

**风险等级**：🟢 低风险。

---

## 7. Result 回写绑定具体 Task/Run ✅

```python
class InboxResultCallback:
    inbox_item_id: str   # 绑定 inbox item
    run_id: str           # 绑定 run
```

双字段绑定。`writeback_available` 表明是否真的可以回写（当前仅 CLI source 支持）。

**风险等级**：🟢 无风险。

---

## 8. Stub 状态清晰 ✅

```python
_WRITEBACK_AVAILABLE = {
    FEISHU: False,    DISCORD: False,    SCHEDULER: False,
}
writeback_destination():  "Feishu thread (unavailable — stub)"
```

3 个 stub source 的 writeback 明确标记为 False，destination 显示 `"(unavailable — stub)"`。

**风险等级**：🟢 无风险。

---

## 9. 无隐藏自动化入口 ✅

- `inbox.py` 纯 CRUD，无 scheduler/poller/webhook
- `inbox_cli.py` 纯 CLI 子命令，无自动触发
- 全局搜索 `InboxManager` 引用——只有 `inbox_cli.py` 使用

所有操作都是用户主动触发：`inbox add` / `convert` / `reject` / `edit`。

**风险等级**：🟢 无风险。

---

## 总结

| 检查项 | 风险 | 建议 |
|--------|------|------|
| 自动执行 | ✅ 无 | — |
| 绕过 review | ✅ 无 | — |
| 绕过 permission | ✅ 无 | — |
| raw_payload 污染 | ⚠️ 建议加限制 | 64KB cap + 类型验证 |
| source 可信度 | ⚠️ 建议加备注 | 当前仅显示，未来需签名 |
| 用户可编辑 | ✅ 设计正确 | — |
| result 绑定 | ✅ 设计正确 | — |
| stub 清晰 | ✅ 设计正确 | — |
| 隐藏自动化 | ✅ 无 | — |

**唯一 P0 建议**：在 `add()` 中增加 `raw_payload` 大小限制（64KB）和类型验证。
