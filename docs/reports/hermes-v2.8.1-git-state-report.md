# Hermes v2.8.1 Phase 6 — Git State Report

> 执行时间：2026-06-01T22:35 CST

## 1. 变更统计

```
Modified (tracked):  17 files
Untracked (new):     13 items
Total:               30 entries (快照说的 27 是旧的)
```

## 2. 分类清单

### 2.1 本次 v2.8.1 修复相关（必须 commit）

| 文件 | 类型 | Phase |
|------|------|-------|
| `config/managed-agents.yaml` | M | Phase 1 — mirror drift fix |
| `config/agent-registry.json` | M | Phase 5 — TARS soul 更新 |
| `scripts/review-task.py` | ?? | Phase 2 — error taxonomy |
| `scripts/gate-policy.py` | ?? | Phase 2 — error taxonomy |
| `scripts/verify-task.py` | ?? | Phase 3 — outbox 校验 |
| `scripts/compile-task.py` | ?? | Phase 4 — budget 字段 |
| `docs/reports/` | ?? | Phase 0/1 — 审计和修复报告 |
| `docs/hermes-architecture-snapshot-2026-06-01.md` | ?? | 架构快照 |

> 注：`scripts/` 标记为 `??` 因为整个目录都是 untracked，Phase 2-4 的改动也在其中。

### 2.2 历史遗留（非本次修改，建议单独 commit）

| 文件 | 说明 |
|------|------|
| `skills/` 下 10+ 个 SKILL.md | 历史 skill 更新 |
| `templates/acceptance_criteria_cheatsheet.md` | 历史模板 |
| `templates/task_package_template.md` | 历史模板 |
| `templates/gate_policy_v2_8.json` | 历史模板（新文件） |
| `templates/inbox_v2_8.json` | 历史模板（新文件） |
| `templates/outbox_v2_8.json` | 历史模板（新文件） |
| `templates/review_v2_8.json` | 历史模板（新文件） |
| `skills/` 下 5 个新 skill 目录 | 历史新增 |
| `tests/` | 历史测试 |
| `bin/hermes-system-doctor.py` | 历史改动 |
| `bin/setup.sh` | 历史改动 |
| `config.yaml` | 历史配置变更 |
| `.gitignore` | 历史改动 |

### 2.3 日志/缓存（不应提交）

| 文件 | 说明 |
|------|------|
| — （当前无） | |

### 2.4 需要人工确认

| 文件 | 问题 |
|------|------|
| `config.yaml` | 包含 API key / secret，diff 需人工审查 |
| `.gitignore` | staged 变更，需确认是新增忽略项还是误改 |

## 3. 建议 .gitignore 更新

无需新增。当前 `.gitignore` staged change 需审查后再决定。

## 4. 最小提交方案

```bash
# Commit 1：v2.8.1 修复
git add config/managed-agents.yaml config/agent-registry.json
git add scripts/ docs/reports/ docs/hermes-architecture-snapshot-2026-06-01.md
git commit -m "fix: v2.8.1 agent sync, gate-policy taxonomy, outbox validation, budget, TARS boundary"

# Commit 2：历史遗留（可选，由 Gu 决定）
git add skills/ templates/ bin/ tests/ .gitignore config.yaml
git commit -m "chore: accumulated skill/template/config updates"
```

## 5. 建议

- **不要自动 commit**，由 Gu 审查 diff 后再提交
- `config.yaml` 的变更尤其需要人工确认（含密钥相关信息）
- `.gitignore` 变更需单独审查
