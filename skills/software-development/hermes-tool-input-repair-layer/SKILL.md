---
name: hermes-tool-input-repair-layer
description: Hermes Agent 工具输入修复层（Tool Input Repair Layer）— 解决开源模型工具调用中的重复错误
tags:
- tool-calling
- repair
- harness-engineering
- deepseek
agents:
- deepseek-tui
- claude
- codex
- hermes-internal
---

# Tool Input Repair Layer

## 背景

开源模型（DeepSeek、Qwen、GLM 等）在工具调用中的失败往往不是模型能力问题，而是 Harness 设计问题。模型反复犯 4 类重复错误：
- optional 字段传 `null` 而不是省略
- 把数组写成 JSON 字符串 `'["a","b"]'`
- schema 要数组但传了 `{}`（空占位符）
- schema 要数组但传了裸字符串 `"foo"`

## 核心设计原则

1. **validate-then-repair** — 先原样校验，通过就绝不修改；失败时才定点修复
2. **先 repair 后 coerce** — 修复结构后再做类型转换，repair 看到的永远是原始输入
3. **不引入新依赖** — 全部手工规则匹配，不用 `jsonschema`
4. **最小改动** — 核心逻辑内联在 `model_tools.py`，不建新模块
5. **反馈循环** — repair_log 注入 tool result，让模型知道被修复了

## 实施步骤

### Phase 0：Repair Core Pipeline

在 `model_tools.py` 中新建：

```python
_REPAIR_RULES = [
    ("stripNull", _repair_strip_null),
    ("parseJsonArray", _repair_parse_json_array),
    ("unwrapEmptyObject", _repair_unwrap_empty_object),
    ("wrapBareString", _repair_wrap_bare_string),
]
```

注意：`parseJsonArray` **必须在** `wrapBareString` 之前，否则 `'["a","b"]'` 会被错误修成 `['["a","b"]']`。

在 `handle_function_call()` 中先 repair 后 coerce：

```python
function_args, repair_log = _repair_tool_args(function_name, function_args)
function_args = coerce_tool_args(function_name, function_args)
```

### Phase 1：Agent Loop 集成

在 `run_agent.py:_invoke_tool()` 中，对 ALL 工具（包括 `delegate_task`/`todo`/`memory`/`session_search`/`clarify`）执行 repair。MCP 工具（`mcp_` 前缀）跳过。

### Phase 1.5：语义类型 + 安全检查

使用 `(tool_name, param_name)` 元组做 key 的 dict 注册表：

```python
_SEMANTIC_REPAIR_MAP = {
    ("read_file", "path"): [("strip_markdown_link", fn), ("expand_tilde", fn)],
    ("terminal", "command"): [("fix_double_escape", fn)],
}
```

安全检查：path traversal、shell injection 检查内置，不推迟。

### Phase 2：事件日志 + 反馈循环

- 注册 `tool_input_repaired` 事件到 `events.db`
- repair_log 注入 tool result 的 `_repair` 字段
- 让模型看到自己被修复了

### Phase 3：错误格式 + 测试

- raw Python error → 结构化模型可读错误
- 24 个集成测试覆盖所有错误模式

## 文件清单

```
修改:
  ├── model_tools.py                    # 核心，~+290 行
  ├── run_agent.py                      # _invoke_tool 集成，~+60 行
  ├── agent/session_event_log.py        # 事件类型注册，~+20 行
  ├── tools/file_tools.py               # x-semantic-type，+4 行
  ├── tools/terminal_tool.py            # x-semantic-type，+2 行
  └── tests/test_tool_repair.py         # 24 个测试
```

## 已知 Bug 修复历史

| # | 问题 | 修复 |
|---|------|------|
| 1 | 语义修复日志仅记录最后一条规则 | 改为记录每次转换，列表存储所有应用的规则 |
| 2 | 并发执行路径中存在双重修复 | `_invoke_tool` 中注册表工具跳过 repair，由 `handle_function_call` 处理 |
| 3 | `log_tool_input_repaired` 未被生产代码调用 | 在修复路径中加调用 |
| 4 | `_repair_check_path_traversal` 是空操作 | 改为 `logger.warning()` 记录遍历路径 |
| 5 | `_repair_fix_double_escape` 4→2 但名称为"双重转义" | 改为 2→1，更新 docstring |
| 6 | docstring 反引号格式错误 | 修正引号位置 |
| 7 | `_repair_strip_shell_prompt` 定义未用 | 注册到 `_SEMANTIC_REPAIR_MAP` |
| 8 | 测试文件死代码 | 移除空的 `patch.dict` 和未使用的 `MagicMock` |
| 9 | 测试断言模棱两可 | 改为精确期望行为 |
| 10 | 异常被 `except: pass` 静默吞掉 | 加 `logger.warning` |
| 11 | 事件类型不在 `REQUIRED_PAYLOAD_KEYS` | 补充 |
| 12 | 测试缺口 | 补充 7 个 edge case 测试 |

## OpenClaw / 桌面工具适配 (GLM-5-Turbo)

桌面工具的语义修复规则（已实现在 `_SEMANTIC_REPAIR_MAP`）：

| 工具 | 参数 | 修复 | 场景 |
|------|------|------|------|
| `desktop_click` | x, y | `fix_coord_type` 浮点数/字符串→int | GLM 坐标传成 100.0 或 "500" |
| `desktop_move` | x, y | `fix_coord_type` 同上 | 同上 |
| `desktop_press` | keys | wrapBareString（基础修复）| 传 "enter" 而不是 ["enter"] |
| `desktop_clipboard` | action | null→"read" | required 枚举传 null |
| `desktop_clipboard` | text | int→str | 传 123 而不是 "123" |
| `desktop_scroll` | amount | float→int | 传 5.0 而不是 5 |
| `desktop_type` | text | **🚫 绝不做任何修改** | 内容就是用户要打的字 |

关键规则：`desktop_type.text` 通过 identity function 保护，确保绝不会被任何 repair 修改。

## 关键陷阱

1. **parseJsonArray 必须在 wrapBareString 之前** — 否则 JSON 字符串会被误 wrapped
2. **先 repair 后 coerce** — 修复需要看原始输入，不能被 coerce 预处理污染
3. **MCP 工具跳过** — 动态 schema 不兼容手工规则
4. **不做全量 JSON Schema validate** — handler 用 `args.get()` 已容错
5. **`(tool, param)` 做 key，不是 `param` 单独** — write_file.path 和 patch.path 语义不同
