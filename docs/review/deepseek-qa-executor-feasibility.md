# DeepSeek TUI QA Executor 可行性评估

> 检查 `deepseek exec` 是否能作为 QA / Code Review / Quick Scan 的自动化执行器。

评估日期：2026-06-04
实际测试版本：deepseek v0.8.39（npm wrapper）

---

## 结论先行

**不适合作为自动 QA executor，但适合作为人工辅助工具。** 核心障碍是缺乏 `--readonly` 模式——`--auto --yolo` 会放行所有工具（含写操作），不加 `--yolo` 则连 `exec_shell` 读操作也会被阻塞。

---

## 适合 QA 的能力 ✅

### 1. Diff 审查能力（强）

实测 `deepseek exec --auto --json "review this diff: ..."` 能够：

- 理解 unified diff 格式
- 输出结构化的审查表格（语义、字符串值、标识符、测试维度）
- 给出明确的变更风险评估

实际测试输出：

```json
{
  "mode": "agent",
  "output": "| 维度 | 评估 |\n|------|------|\n| **语义** | ... |\n| **标识符** | ... |\n| **测试** | ... |",
  "status": "completed"
}
```

### 2. 结构化风险列表输出（强）

One-shot 模式（不加 `--auto`）可以直接输出结构化列表：

```bash
deepseek exec --json "list 3 risk categories for code changes"
```

输出格式良好的文本列表。

### 3. 静默执行（无需 PTY）

- `exec` 模式不需要 TTY，piped stdin 也可以
- 无障碍非交互式调用

---

## 不适合 QA 的能力 ❌

### 1. 没有 `--readonly` 模式（核心缺失）

当前工具控制只有二选一：

| 模式 | 工具可用性 | 写防护 |
|------|-----------|--------|
| `--auto`（不加 `--yolo`） | 非 TTY 下工具调用被阻塞 | 写操作被防 ✅ 但读也被防 ❌ |
| `--auto --yolo` | 所有工具自动批准 | 无防护 ❌ |
| 不加 `--auto` | 无工具 | 无法执行命令 ❌ |

QA executor 需要**只读 git diff + 文件读取 + 测试执行**，但无法配置白名单。不 `--yolo` 则连 `read_file` / `exec_shell ls` 也会被阻塞。

### 2. 没有原生结构化 diff 输入

`deepseek review` 命令只接受当前工作目录的 git diff，无法传入任意 diff 字符串。改用 `exec --auto --json "review this diff: ..."` 时，diff 作为 prompt 的一部分，长度受限。

### 3. 测试命令执行不可控

- `exec_shell` 在 `--auto` 模式下可用
- 但无法限制只执行测试——执行器也可以运行 `rm -rf /`
- 测试运行时长不确定，exec 模式一直等待

### 4. 输出格式不稳定

```json
{
  "output": "自然语言分析文本",
  "status": "completed"
}
```

无法保证返回 JSON schema 一致的输出，无法可靠解析为结构化 risk items。

---

## 适合的 QA 场景

### ✅ 人工辅助：Pre-submit Checklist

```bash
cd <project>
deepseek review
```

用户自行审查输出。

### ✅ 单文件快速扫描（人工介入）

```bash
deepseek exec --auto --json "Scan src/auth.py for security issues"
```

用户读取审查意见后自行修改。

### ❌ 自动化 Pipeline：CI/CD Gate

`--yolo` 放行写操作 → CI 不可接受。不 `--yolo` 则被阻塞。

---

## 安全矩阵

| 场景 | `--auto` | `--yolo` | 可行性 | 风险 |
|------|---------|---------|--------|------|
| 纯文本问答审查 | 不用 | 不用 | ✅ | 无工具，纯文本分析 |
| diff 分析（文本传入） | 不用 | 不用 | ✅ | 受 prompt 长度限制 |
| 代码审查（手动） | 使用 | 不用 | ⚠️ | 读工具可能被阻塞 |
| 快速 grep/搜索 | 使用 | 不用 | ⚠️ | exec_shell 可能被拒 |
| 运行测试并报告 | 使用 | 不用 | ⚠️ | 测试命令被拒 |
| CI/CD 自动 review | 使用 | 需要 | ❌ | 写操作自动放行 |

---

## 建议：保持 Manual Only

1. **保留为 Manual Only（stub 状态）**，与 Phase 5 结论一致
2. **未来需要 DeepSeek TUI 支持以下功能之一才能作为 QA executor**：
   - `--readonly` flag：仅放行读工具 + 测试命令
   - `--allow-tools read_file,exec_shell,grep`：白名单机制
   - `--timeout 60`：执行超时控制
3. **当前 v0.8.39 不支持以上任何功能**

### 最关键的缺失功能优先级（供 DeepSeek TUI 开发团队参考）

| 优先级 | 功能 | 理由 |
|--------|------|------|
| P0 | `--readonly` | 只允许读操作+测试执行 |
| P1 | `--allow-tools` | 白名单替代黑名单 |
| P2 | `--timeout` | exec 超时控制 |
| P3 | `--output-schema` | 强制结构化输出 |
