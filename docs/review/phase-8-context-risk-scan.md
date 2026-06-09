# Phase 8 Workspace Context / Prompt Builder 风险扫描

> 检查 v0.6 WorkspaceContextManager + PromptBuilder 的数据安全和格式风险。

扫描日期：2026-06-04
扫描范围：
- `hermes-agent/executors/context.py` — WorkspaceContextManager
- `hermes-agent/executors/prompt_builder.py` — PromptBuilder
- `hermes-agent/executors/context_cli.py` — CLI 子命令
- `hermes-agent/executors/types.py` — ProjectContext / PromptSnapshot 类型

---

## 风险总览

| # | 风险 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | CommandEntry.command 可能包含 secrets | 🔴 高危 | 敏感信息被注入到 LLM prompt |
| 2 | context.json 文件未加密 | 🟡 中危 | 明文存储可能泄露 |
| 3 | executor_id "codex-cli" 不匹配 registry | 🟡 中危 | codex 意外使用 hermes-local 的字段表 |
| 4 | Token caps 仅 warning 不截断 | 🟡 中危 | deepseek-tui 可能收到远超 500 token 的 prompt |
| 5 | CJK token 估算偏差可达 2x | 🟡 中危 | cap warning 可能不准确 |
| 6 | 无 prompt snapshot 持久化 | 🟢 低危 | 当前无风险，未来需注意 |
| 7 | 无 env var 泄露（命令文本展开） | 🟢 低危 | 变量名保留但值不会展开 |
| 8 | 注入控制清晰可关闭 | ✅ 良好 | `context_injection_enabled` + CLI on/off |
| 9 | 用户可预览注入内容 | ✅ 良好 | `cmd_preview` + `cmd_show` |
| 10 | deepseek-tui 只收到 minimal 字段 | ✅ 良好 | 500 token cap + 仅 4 个字段 |

---

## 1. CommandEntry.command 可能包含 Secrets 🔴 高危

### 位置

`types.py` 第 277-281 行 / `prompt_builder.py` 第 231-234 行

### 问题

`CommandEntry.command` 是自由文本字段，用户可能存储包含敏感信息的命令：

```json
{
  "common_commands": [
    {"label": "prod", "command": "psql postgresql://user:pass@host/db"},
    {"label": "deploy", "command": "DEPLOY_KEY=sk-xxx ./deploy.sh"}
  ]
}
```

这些命令被**原样注入**到 executor prompt 中，发送到 LLM。

### 缓解

- Shell 变量（如 `$DEPLOY_KEY`）以文本形式保留，不会展开为实际值
- 但明文 Token 直接暴露

### 建议

在 `context.py` 的 `save()` 中增加命令泄露检测：

```python
_SENSITIVE_PATTERNS = [
    r"(api[_-]?key|token|secret|password)\s*[=:]\s*\S{8,}",
    r"Authorization:\s*Bearer\s+\S+",
    r"postgresql://\w+:\w+@",
]
```

检测到 secrets 时记录 warning，不阻塞写入但让用户知晓。

---

## 2. context.json 文件未加密 🟡 中危

### 位置

`context.py` 第 42 行 — `~/.hermes/context.json`

### 问题

所有 context 数据以明文 JSON 存储在 `project_root/.hermes/context.json`：
- project_overview（项目内部详情）
- architecture_notes（架构细节）
- adr_summaries（决策记录）
- common_commands（可能含敏感命令）

如果 `.hermes/` 被误提交到 git，或备份时包含此目录，数据可能泄露。

### 建议

在 `save()` 保存时计算完整性哈希（非加密，但可检测篡改），同时在 `.gitignore` 模板中确认 `.hermes/` 被排除。

---

## 3. executor_id "codex-cli" 不匹配 Registry 🟡 中危

### 位置

`prompt_builder.py` 第 47、96、104、112、120 行 vs `registry.py` 第 166 行

### 问题

prompt_builder 的所有 `_*` 表使用 `"codex-cli"` 作为 key，但 registry 注册的是 `"codex"`。当 `executor_id="codex"` 时：

```python
# 第 189 行 — 所有 key miss 都回退到 hermes-local
field_table = dict(_FIELD_TABLE.get(executor_id, _FIELD_TABLE["hermes-local"]))
```

这导致 codex 使用 hermes-local 的字段表（无截断、无 cap），`_TOKEN_CAP["codex"]` 也是 fallback 到 2000。

### 建议

所有 `_FIELD_TABLE`、`_TOKEN_CAP`、`_ADR_LIMITS`、`_ARCH_TRUNCATION`、`_RECENT_TASK_LIMITS` 中的 `"codex-cli"` → `"codex"`。

---

## 4. Token Caps 仅 Warning 不截断 🟡 中危

### 位置

`prompt_builder.py` 第 260-265 行

```python
if estimated > cap:
    logger.warning("Prompt may exceed %d token cap (estimated %d) for %s", cap, estimated, executor_id)
```

### 问题

Token cap 超过时**只打印 warning，不做截断**。`_TRUNCATION_PRIORITY` 列表已定义但没有被使用。

对于 deepseek-tui（cap 500），如果用户 context 很长，实际注入 prompt 可能远超 500 tokens。

### 建议

对设置了明确 cap 的 executor 增加截断逻辑：

```python
if estimated > cap and cap < 99999:
    injected = _truncate_to_token_cap(injected, cap, _TRUNCATION_PRIORITY)
```

裁剪策略：按 `_TRUNCATION_PRIORITY` 顺序，从最低优先级的 section 开始移除，直到 token 计数降至 cap 以内。

---

## 5. CJK Token 估算偏差可达 2x 🟡 中危

### 位置

`prompt_builder.py` 第 299-309 行

```python
# 当前：CJK 每 2 chars 计 1 token
cjk_count / 2

# 实际多数模型：CJK 每 ~1 char 计 1 token
```

对中文项目，估算值可偏低到实际的一半。建议调整为：

```python
return max(1, int(ascii_count / 4 + cjk_count * 0.8))
```

---

## 6-10：其余评估 🟢

### 6. PromptSnapshot 无持久化（当前无风险）

`PromptSnapshot` 定义完整但只在内存中返回。如果未来增加持久化到 `events.db` 或 `state.db`，必须注意 `injected_prompt` 字段含完整上下文。

### 7. 命令 env 变量不会展开（正确行为）

```json
{"command": "deploy.sh $DEPLOY_KEY"}
```

注入为文本 `deploy.sh $DEPLOY_KEY`，变量名保留但值不会泄露。这是正确的——环境变量在 executor 子进程运行时才由 shell 展开。

### 8. 注入控制 ✅

- `context_injection_enabled: bool = True`（默认开启）
- CLI: `context injection on|off`
- 关闭后 prompt 直接等于 user_prompt

### 9. 预览机制 ✅

- `cmd_preview --executor codex --goal "refactor"` — 显示注入后的完整 prompt
- `cmd_show` — 显示所有 context 字段
- 用户可清楚看到什么信息会被发送

### 10. DeepSeek TUI minimal 字段 ✅

| 字段 | | cap |
|------|---------|------|
| project_overview | ✅ | 基本信息 |
| architecture_notes | ❌ | 跳过 |
| adr_summaries | ❌ | 跳过 |
| current_sprint | ✅ | |
| common_commands | ✅ | |
| test_commands | ❌ | 跳过 |
| forbidden_areas | ✅ | |
| coding_conventions | ❌ | 跳过 |
| recent_tasks | ❌ | 跳过 |
| **Token cap** | | **500** |

这是合理的 minimal 策略——不注入架构、ADR、代码约定这些对低成本 executor 无意义的长文本。

---

## 附录：修复优先级

| 优先级 | 修复项 | 文件 | 行数 |
|--------|--------|------|------|
| **P0** | CommandEntry secrets 检测 | `context.py` save() | ~20 行 |
| **P0** | `"codex-cli"` → `"codex"` | `prompt_builder.py` 6 处 | 6 行 |
| **P1** | Token cap 实际截断 | `prompt_builder.py` build() | ~20 行 |
| **P2** | CJK 估算公式 | `prompt_builder.py` `_estimate_tokens` | 1 行 |
| **P3** | context.json 完整性 | `context.py` save/load | ~10 行 |
