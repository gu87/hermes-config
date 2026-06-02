# Hermes v2.8.1 稳定化修复 — 最终交付物

> 执行时间：2026-06-01T22:40 CST
> 执行模型：马蒂尼总控 → 技术翻译官审查 → Claude 主程执行

---

## 1. 修复摘要

| Phase | 目标 | 结果 |
|-------|------|------|
| 0 | 三边 Agent 定义审计 | ✅ 审计报告已生成 |
| 1 | 修复 managed-agents mirror drift | ✅ mirror 10→10 agents，与 source/registry 一致 |
| 2 | Gate-Policy 错误分类扩展 | ✅ 11 种 taxonomy，向后兼容 |
| 3 | Agent outbox schema 标准化 | ✅ 只读 Agent changed_files 强校验 |
| 4 | Task Card budget 字段 | ✅ 三种默认策略 |
| 5 | TARS 硬约束 | ✅ soul 追加禁止项 |
| 6 | Git state 分类 | ✅ 30 项变更分类报告 |

---

## 2. 修改文件清单

| 文件 | Phase | 改动 |
|------|-------|------|
| `config/managed-agents.yaml` | 1 | +opencode, claude model_ref, deepseek-tui model_ref/chain/runtime |
| `scripts/review-task.py` | 2 | +_CHECK_TAXONOMY 映射, make_check() 增加 taxonomy 字段 |
| `scripts/gate-policy.py` | 2 | +_TAXONOMY_POLICY, +policy_for_v2_8_1() |
| `scripts/verify-task.py` | 3 | +validate_standard_outbox(), +READ_ONLY_AGENTS |
| `scripts/compile-task.py` | 4 | +budget 字段和默认策略 |
| `config/agent-registry.json` | 5 | agent-tars soul 追加禁止项 |

---

## 3. 新增文件清单

| 文件 | 说明 |
|------|------|
| `docs/reports/hermes-v2.8.1-agent-sync-audit.md` | Phase 0 审计报告 |
| `docs/reports/hermes-v2.8.1-agent-sync-fix.md` | Phase 1 修复报告 |
| `docs/reports/hermes-v2.8.1-git-state-report.md` | Phase 6 Git 状态报告 |

---

## 4. 风险说明

| 风险 | 等级 | 说明 |
|------|------|------|
| config.yaml 未审查 | 🟡 | 含 API key 相关变更，需人工确认 |
| scripts/ 全目录 untracked | 🟡 | 需确认 git add 范围 |
| Phase 2 gate-policy 新增 security_risk → reject | 🟢 | 比旧行为更严格，合理 |
| opencode Agent mirror 已补 | 🟢 | 不影响运行（运行时用 registry） |

---

## 5. 验证结果

| 检查 | 结果 |
|------|------|
| hermes-system-doctor.py | ✅ WARN（仅有 git state 告警，无 FAIL） |
| Managed agents mirror | ✅ OK（10 agents） |
| Agent registry coverage | ✅ OK（10 agents） |
| Agent registry consistency | ✅ OK |
| compile-task.py 加载 | ✅ OK |
| verify-task.py 加载 | ✅ OK |
| gate-policy.py 加载 | ✅ OK |
| review-task.py 加载 | ✅ OK |

---

## 6. 逐项验收对照

| 验收标准 | 状态 |
|---------|------|
| managed agents mirror drift 修复 | ✅ |
| opencode 状态明确 | ✅ |
| source / registry / mirror Agent 一致 | ✅ |
| gate-policy 支持更细错误类型 | ✅ 11 种 |
| Agent outbox schema 统一 | ✅ |
| Task Card 有 budget | ✅ |
| TARS 边界更硬 | ✅ soul 追加 |
| git state 已分类 | ✅ 报告已生成 |
| 不引入新的 Agent | ✅ |
| 不开启 orchestrator_enabled | ✅ 未改 |
| 不提高 max_spawn_depth | ✅ 未改 |
| 不开启 subagent_auto_approve | ✅ 未改 |

---

## 7. 需要人工确认

1. `config.yaml` 的 27 行历史变更 — diff 审查
2. `.gitignore` 的 staged 变更 — 确认意图
3. `scripts/` 全目录是否整体 add — 确认 Phase 2-4 改动无误后再 commit

---

## 8. 下一步建议

1. Gu 审查 `config.yaml` 和 `.gitignore` 的 diff
2. `git add scripts/ docs/ config/managed-agents.yaml config/agent-registry.json` 提交 v2.8.1 修复
3. 残留的 skill/template 更新单独 commit
4. 考虑 `hermes update` 合入 Tool Search feature（已评估，可选）
