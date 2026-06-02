# Hermes v2.8.1 Phase 1 — Agent Sync Fix Report

> 执行时间：2026-06-01T22:30 CST

## 修复文件

| 文件 | 操作 |
|------|------|
| `config/managed-agents.yaml` | 修改（补 opencode + 修正 claude/deepseek-tui 字段） |

## 具体修改

| # | 位置 | 修改 | 原因 |
|---|------|------|------|
| 1 | claude model_ref + chain | `claude_opus` → `claude_sonnet`，补 sonnet fallback | 对齐 source |
| 2 | claude role_summary | 补齐 "标准实现默认 Sonnet..." | 对齐 source |
| 3 | deepseek-tui model_ref + chain | primary 从 Pro → Flash，chain 顺序修正 | 对齐 source |
| 4 | deepseek-tui runtime | 补 `deepseek_tui_cli` | source 有此字段 |
| 5 | deepseek-tui 后 | 插入 opencode 完整定义（34 行） | 解决 mirror drift |

## 验证结果

```
[OK] Managed agents mirror
[OK] Agent registry coverage
[OK] Agent registry consistency
Summary: WARN — current system is usable but has warnings
       (warnings are git state, not agent sync)
```

- Source: 10 agents ✅
- Mirror: 10 agents ✅  
- Registry: 10 agents ✅
- Agent ID 集合：完全一致 ✅
- opencode：已补充到 mirror ✅

## 未修改文件

- `hermes-agent/configs/managed_agents/agents.yaml` — source，未动
- `config/agent-registry.json` — registry，未动
- `bin/hermes-system-doctor.py` — 校验增强留到 Phase 6
