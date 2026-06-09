# Hermes Desktop Codex-like v1.0 发布前 Bug Scan

> 发布前问题排查。覆盖 15 个检查维度，聚合所有 Phase 扫描结果。

扫描日期：2026-06-04
范围：`hermes-agent/executors/` + `web/src/` + `ui-tui/src/`

---

## 优先级定义

- **P0**：必须修，否则不能发布（数据丢失、安全漏洞、功能不可用）
- **P1**：应该修，否则体验或安全有明显问题
- **P2**：可以后续修
- **Nits**：小问题

---

## P0：必须修复（3 项）

### P0-1：Worktree `discard()` 缺少路径安全校验

**文件**：`executors/worktree.py` 第 402-457 行
**详情**：`discard()` 执行 `git worktree remove --force` + `git branch -D` 前，不验证 `worktree_path` 是否在管理目录下。状态损坏时可能删除任意 git worktree。
**对比**：`delegate_tool.py` 有 `startswith(_get_worktree_base_dir())` 保护。
**修复**：约 5 行，增加路径校验。

### P0-2：Worktree `_short_id("")` 返回空字符串

**文件**：`executors/worktree.py` 第 109-112 行
**详情**：空 `thread_id` 产生空 `short_id`，分支名变为 `hermes//1`。
**修复**：1 行，`thread_id or "unknown"`。

### P0-3：Worktree `_check_clean_working_tree` 缩进错误

**文件**：`executors/worktree.py` 第 139-148 行
**详情**：过滤 `.hermes/` 变更的 4 行代码与 `if not r.ok` 同缩进，导致只在失败时执行。脏仓库可能误通过检查。
**修复**：调整 6 行缩进。

---

## P1：应该修复（9 项）

### P1-1：`codex_adapter.py` 健康检查提示 Codex.app 已过时

**文件**：`executors/codex_adapter.py` 第 91 行
**当前文本**：`install via Codex.app or set HERMES_CODEX_PATH`
**建议**：改为 `install via: npm install -g @openai/codex 或设置 HERMES_CODEX_PATH`

### P1-2：`codex_adapter.py` 使用 `-p` 参数传递 prompt——不支持结构化输出

**文件**：`executors/codex_adapter.py` 第 106 行
**详情**：`codex -p "<prompt>"` 输出纯文本。adapter 只收集原始 stdout 作为 log event，无法提供 tool_call / diff / reasoning 事件。
**建议**：v1.0 文档标注 codex adapter 为 "log-only"。

### P1-3：`claude_code_adapter.py` 缺少 `--output-format stream-json`

**文件**：`executors/claude_code_adapter.py` 第 116 行
**详情**：启动命令只传 prompt，没有结构化输出 flag。与 Phase 5 测试确认的 DeepSeek TUI `stream-json` 模式相比有差距。
**影响**：无法解析 tool_call 事件。

### P1-4：所有子进程 adapter env 传递完整 `os.environ`

**文件**：`codex_adapter.py:124`、`claude_code_adapter.py:122`、`opencode_adapter.py:102`
**细节**：
```python
env={**os.environ, **(run.env or {})},
```
子进程继承父进程完整环境。API key 等敏感变量被传递给子进程。
**建议**：构建白名单环境，只传递 `PATH`、`HOME`、`HERMES_*` 前缀的变量。

### P1-5：Prompt Builder token cap 超过只 warning 不截断

**文件**：`executors/prompt_builder.py` 第 260-265 行
**详情**：deepseek-tui cap 500、codex-cli cap 1500 不实际截断。`_TRUNCATION_PRIORITY` 列表已定义但未被使用。
**影响**：低成本 executor 收到远超预期的长 prompt。

### P1-6：`common_commands` 可能注入 secrets 到 prompt

**文件**：`executors/types.py` 第 277-281 行
**详情**：`CommandEntry.command` 自由文本，用户可能存储含明文 token 的命令。
**建议**：Save 时检测常见 secret pattern。

### P1-7：External Inbox `raw_payload` 无大小限制

**文件**：`executors/inbox.py` 第 111 行
**建议**：增加 64KB 大小限制。

### P1-8：SessionsPage / RunsPage 空状态未覆盖

**文件**：`web/src/pages/SessionsPage.tsx`、`RunsPage.tsx`
**建议**：确认首次使用时页面显示 "No sessions yet" / "No runs yet"。

### P1-9：Stub adapter `stream_events()` 应明确报错

**文件**：`executors/deepseek_tui_adapter.py`
**详情**：stub 模式不应允许调用 `stream_events()` 和 `get_status()`。如果被调用，应抛 `ExecutorNotAvailableError`。

---

## P2：后续修复（5 项）

### P2-1：Worktree 状态纯内存，崩溃后丢失

**文件**：`executors/worktree.py` 第 90 行
**建议**：增加 JSON 状态持久化。

### P2-2：Worktree merge 冲突后无法重试

**文件**：`executors/worktree.py` 第 372-379 行
**建议**：增加 FAILED → DIRTY 恢复路径。

### P2-3：插件 loading 超时 2000ms

**文件**：`web/src/plugins/usePlugins.ts` 第 99 行
**建议**：降到 1000ms。

### P2-4：`opencode_adapter.py` 无结构化输出支持

**文件**：`executors/opencode_adapter.py`

### P2-5：CJK token 估算偏差

**文件**：`executors/prompt_builder.py` 第 299-309 行
**建议**：CJK 估算从 2 chars/token 改为 1.25 chars/token。

---

## Nits（4 项）

### Nit-1：`codex_adapter.py` health check 返回 `"codex"` 而非 `"codex-cli"`

**文件**：`executors/codex_adapter.py` 第 89 行

### Nit-2：`hermes_local_adapter.py` git snapshot 使用过多 flag

**文件**：`executors/hermes_local_adapter.py` 第 342-343 行

### Nit-3：`_TRUNCATION_PRIORITY` 缺少 `workspace_conventions`

**文件**：`executors/prompt_builder.py` 第 127-137 行

---

## 按文件汇总

| 文件 | P0 | P1 | P2 | Nits |
|------|----|----|----|------|
| `executors/worktree.py` | 3 | 0 | 2 | 0 |
| `executors/prompt_builder.py` | 0 | 1 | 1 | 1 |
| `executors/codex_adapter.py` | 0 | 2 | 0 | 1 |
| `executors/claude_code_adapter.py` | 0 | 1 | 0 | 0 |
| `executors/opencode_adapter.py` | 0 | 1 | 1 | 0 |
| `executors/deepseek_tui_adapter.py` | 0 | 1 | 0 | 0 |
| `executors/inbox.py` | 0 | 1 | 0 | 0 |
| `executors/context.py` | 0 | 1 | 0 | 0 |
| `executors/types.py` | 0 | 1 | 0 | 0 |
| `web/src/pages/SessionsPage.tsx` | 0 | 1 | 0 | 0 |
| `web/src/plugins/usePlugins.ts` | 0 | 0 | 1 | 0 |
| **合计** | **3** | **9** | **5** | **3** |

---

## 发布决策建议

| 条件 | 建议 |
|------|------|
| 含 worktree 功能 | **P0-1、P0-2、P0-3 必须修**（共 ~12 行代码），否则有数据丢失风险 |
| 不含 worktree（标记 experimental） | P0 降级为 P1，可以发布 |
| 其他 | 修全部 9 个 P1 后发布，P2+Nits 留 v1.1 |
