# DeepSeek TUI Adapter 可行性评估

> 检查 `deepseek` CLI 是否能作为 Hermes Desktop 的 executor。

评估日期：2026-06-03
DeepSeek TUI 版本：v0.8.39（npm wrapper）
评估方式：实际命令行测试

---

## 测试结果汇总

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 1. 非交互式调用 | ✅ 支持 | `deepseek exec` 子命令 |
| 2. 命令行传入 prompt | ✅ 支持 | `exec --auto --json "prompt"` |
| 3. 稳定输出 stdout | ✅ 支持 | `stream-json` 或 `--json` |
| 4. 需要 PTY | ❌ 不需要 | piped stdin 工作正常 |
| 5. 会卡在交互输入 | ⚠️ 有条件 | 有 `--yolo` 可绕过审批 |
| 6. 在 project path 下执行 | ✅ 自动 | CWD 即为工作目录 |
| 7. 通过 git diff 收集结果 | ❌ 不支持原生 | 需 adapter 主动执行 git diff |
| 8. 作为 executor 的可行性 | ⚠️ 部分可行 | 见下方详细分析 |

---

## 1. 非交互式调用 ✅

`deepseek exec` 子命令是专为非交互式调用设计的。

```bash
# 完整的一次性调用，输出汇总 JSON
deepseek exec --auto --json "write a test" --no-project-config

# 流式输出
deepseek exec --auto --output-format stream-json "write a test"
```

**关键输出格式**：

`--json`（非流式，一次性返回 JSON）：

```json
{
  "mode": "agent",
  "model": "deepseek-v4-pro",
  "prompt": "...",
  "output": "...",
  "tools": [
    { "name": "...", "success": true, "output": "..." }
  ],
  "status": "completed",
  "error": null
}
```

`--output-format stream-json`（流式，逐行输出）：

```json
{"type":"content","content":"..."}
{"type":"tool_use","name":"write_file","id":"...","input":{...}}
{"type":"tool_result","id":"...","output":"...","status":"success"}
{"type":"metadata","meta":{"model":"...","status":"completed"}}
{"type":"done"}
```

**结论**：非交互式调用能力完整。`stream-json` 的输出事件与新模型的 `RunEvent` 类型对齐度很高。

---

## 2. Prompt 传入 ✅

```bash
# 直接参数
deepseek exec --auto --json "write hello world"

# 通过管道（实测通过）
echo "" | deepseek exec --auto --json "just say OK"
```

实测 prompt 被正确传递和执行。管道输入也正常工作，没有 hang。

---

## 3. stdout / stderr 输出 ✅

两种模式均输出到 stdout。stderr 有少量诊断日志（Gemini 注册失败等），不影响 stdout 协议解析。

注意事项：
- `--json` 和 `--output-format stream-json` **互斥**
- `--json` 输出 `tools` 数组（已完成的工具调用摘要）
- `stream-json` 逐个输出事件，最后有 `{"type":"done"}`

---

## 4. PTY 需求 ❌

`deepseek exec` 不会尝试启用 raw mode，不需要 PTY。

实测 piped stdin 场景可以工作。之前 `deepseek --help` 报的 "Failed to enable raw mode" 只是警告，不影响 exec 的执行。

---

## 5. 交互输入阻塞风险 ⚠️

**不需要 PTY，但有审批阻塞风险**：

| Flag | 作用 | 建议 |
|------|------|------|
| `--auto` | 启用 agentic 模式，带 tool access | 必须 |
| `--yolo` | 自动批准所有工具调用（跳过审批） | 看安全策略 |
| 无 flags | 纯对话模式，无 tool access | 不适合 executor |

不加 `--yolo` 时，write_file 等写操作会被审批阻塞，非 TTY 环境自动拒绝。

加 `--yolo` 则所有工具调用自动通过，存在安全风险。

当前没有 `--approval-policy auto` 之类的细粒度控制。

---

## 6. Project Path 执行 ✅

`deepseek exec` 以其 CWD 为工作目录：

```bash
cd /tmp && deepseek exec --auto --json "pwd"
# 输出：`/private/tmp`
```

`--workspace` 是顶层 flag，主要用于 TUI 模式读取 AGENTS.md 等配置。exec 模式下 CWD 就是工作目录。注意 npm wrapper 参数解析有偏移——`--workspace` 无法正确传递到 exec 子命令。

---

## 7. Git Diff 收集 ❌

`deepseek exec` 的 `--json` 输出中，`tools` 数组包含了工具调用摘要，但**没有 git diff 信息**。

测试中 `write_file` 的 `tool_result` 输出包含 diff 字符串，但这只在 `stream-json` 模式的 `tool_result` 事件中出现，`--json` 模式的 `tools` 数组只输出描述性摘要。

**方案**：Adapter 在 start 时记录 `git rev-parse HEAD`，run 结束后执行 `git diff <before>` 并作为 `diff` event 追加。这与其他非原生 executor 的方案一致。

---

## 8. 核心能力差距

| 能力 | DeepSeek TUI | Hermes Local | 影响 |
|------|-------------|-------------|------|
| reasoning events | ❌ 无 | ✅ 有 | Desktop 无法显示 thinking 块 |
| tool_call events | ✅ 有 | ✅ 有 | 可用于 ToolCallCard |
| tool_result events | ✅ 有 | ✅ 有 | 差异不大 |
| diff events | ❌ 需 adapter 生成 | ✅ 原生 | adapter 额外负担 |
| approval_needed | ❌ 无 | ✅ 有 | 无 review 流程 |
| review_decision | ❌ 无 | ✅ 有 | 无 review 流程 |
| getStatus(runId) | ❌ 无 | ✅ HTTP GET | 无法查询中间状态 |
| stop(runId) | ❌ 仅 kill | ✅ HTTP POST | 只能强制杀进程 |
| safety/approval | `--yolo` 全过/全不过 | 细粒度 Guard | 安全控制粗糙 |

**结论**：DeepSeek TUI 不能替代 Hermes Local Adapter。

---

## 9. v0.1 实现建议

### 建议：实现为 Stub，不硬接

理由：

1. `deepseek exec` 虽然支持非交互式，但缺少 `reasoning` 事件、`status` 查询、`approval` 等 executor 需要的关键能力
2. 审批跳过完全依赖 `--yolo`，缺乏细粒度安全控制
3. npm wrapper 的参数解析缺陷（`--workspace` flag 无法正常传递）增加了集成不确定性
4. v0.1 已有 Hermes Local Adapter 提供完整的执行能力，不需要第二个执行器
5. `stream-json` 的 `tool_use` 事件虽然结构化，但信息量远少于 Hermes SSE 流

### Stub 接口

```typescript
class DeepSeekTuiAdapter implements AgentExecutorAdapter {
  async start(run: AgentRun, config: ExecutorConfig): Promise<AdapterStartResult> {
    throw new ExecutorNotAvailableError(
      'DeepSeek TUI not available as automated executor. ' +
      'Run manually: cd <project> && deepseek exec --auto --yolo "<prompt>"'
    );
  }

  async stop(runId: string): Promise<void> {
    throw new ExecutorNotAvailableError('Not available in stub mode');
  }

  async *streamEvents(runId: string): AsyncIterable<RunEvent> {
    throw new ExecutorNotAvailableError('Not available in stub mode');
  }

  async getStatus(runId: string): Promise<RunStatus> {
    throw new ExecutorNotAvailableError('Not available in stub mode');
  }

  async checkHealth(): Promise<ExecutorHealthResult> {
    try {
      const { stdout } = await exec('deepseek --version');
      return { available: false, version: stdout.trim(),
        error: 'DeepSeek TUI is manual-only. Install Hermes Agent for automated execution.' };
    } catch {
      return { available: false, error: 'deepseek CLI not found' };
    }
  }
}
```

UI 显示：

```
Executor: DeepSeek TUI
Status: ⚠️ Manual Only
Hint: Run manually via terminal:
  cd <project> && deepseek exec --auto --yolo "<prompt>"
```

### 未来扩展点（v0.3+）

如果后续需要低成本 worker executor，DeepSeek TUI 的 `stream-json` 输出是最有希望的切入点：

1. 直接使用 DeepSeek HTTP API（base URL 模式）而非 CLI 子进程——API 模式比 CLI 更可控
2. 等待 DeepSeek TUI 支持 MCP server 作为完整的 executor（已有 `mcp-server` 命令但尚需评估）
3. 等待 npm wrapper 的参数解析修复

### 手动辅助工具入口

即使不做 executor，Adapter 的 `checkHealth` 仍然有价值——UI 可以在「手动执行」功能区显示：

```
Available Executors (manual):
  🔧 DeepSeek TUI v0.8.39
  Command: cd <project> && deepseek exec --auto --yolo "<prompt>"
```
