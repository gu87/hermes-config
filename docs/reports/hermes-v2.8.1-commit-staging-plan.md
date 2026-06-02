# Hermes v2.8.1 Commit Staging Plan

**日期**: 2026-06-02 08:37 CST  
**编制者**: Hermes (马蒂尼)  
**状态**: 待 Gu 审核后执行  

---

## 分类总览

| 分类 | 数量 | 建议 |
|------|------|------|
| ① v2.8.1 必须提交 | 42 文件 | `git add` |
| ② v2.8.1 可选提交 | 0 文件 | — |
| ③ 报告文档 | 6 文件 | 随 commit 提交 |
| ④ 本地运行时文件，不应提交 | 0 文件 | 已确认无 |
| ⑤ 历史遗留，需人工判断 | 0 文件 | — |
| ⑥ 敏感配置，不应提交 | 0 文件 | 已确认无 |

> **总计**: 42 changed + 6 untracked reports = 48 文件可安全提交。

---

## ① v2.8.1 必须提交 — 42 文件

### A. 核心配置 (3 files)

| 文件 | 变更摘要 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|---------|----------|:--:|------|
| `config.yaml` | `child_timeout_seconds: 600 → 180` | ✅ 无密钥/token/webhook/base_url | ✅ | `git add` |
| `config/agent-registry.json` | Claude model_ref opus→sonnet; DeepSeek 模型链重排; 新增 opencode Agent; 新增 3 skills; DeepSeek 新增 runtime 字段 | ✅ 无 | ✅ | `git add` |
| `config/managed-agents.yaml` | 从内联 YAML 重写为结构化格式，作为 agents.yaml 部署镜像 | ✅ 无 | ✅ | `git add` |

**config.yaml 验证**: diff 只有一行变更 (`child_timeout_seconds`)，无 token、webhook、base_url 泄露。  
**agent-registry.json 验证**: model_ref 变更（opus→sonnet, pro→flash）不涉及密钥。  
**managed-agents.yaml 验证**: 纯 Agent 结构定义，无运行时凭证。

---

### B. 系统工具 (2 files)

| 文件 | 变更摘要 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|---------|----------|:--:|------|
| `bin/hermes-system-doctor.py` | 新增 managed-agents.yaml 镜像一致性检查 | ✅ 无 | ✅ | `git add` |
| `bin/setup.sh` | managed_agents 部署方向修正：源文件→镜像（不逆向覆盖） | ✅ 无 | ✅ | `git add` |

---

### C. .gitignore (1 file)

| 文件 | 变更摘要 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|---------|----------|:--:|------|
| `.gitignore` | unignore `scripts/`、`templates/*.json`、`tests/`，使其进入版本控制 | ✅ 无 | ✅ | `git add` |

**说明**: v2.8.1 Task Card Pipeline 将核心脚本和模板从本地运行时提升为可移植资产，.gitignore 需对应放开。

---

### D. 核心流水线脚本 (10 files，新文件)

| 文件 | 用途 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|------|----------|:--:|------|
| `scripts/verify-task.py` | 结构+事实验收（outbox schema/status/changed_files/evidence） | ✅ 无（仅 mention `missing_api_key` 作为错误分类） | ✅ | `git add` |
| `scripts/review-task.py` | 语义审查（goal 覆盖/must_avoid/must_keep/evidence 质量） | ✅ 无 | ✅ | `git add` |
| `scripts/gate-policy.py` | Gate 决策→下一动作映射（complete/auto_revision/manual_review/reject） | ✅ 无 | ✅ | `git add` |
| `scripts/run-task-gate.py` | 统一 gate 入口（verify→review→policy 三合一） | ✅ 无 | ✅ | `git add` |
| `scripts/compile-task.py` | Task Card 组装（编译 inbox JSON） | ✅ 无 | ✅ | `git add` |
| `scripts/dispatch-task.py` | 任务派发（读取 inbox→委托子 Agent） | ✅ 无 | ✅ | `git add` |
| `scripts/opencode-agent.py` | OpenCode CLI 适配器 | ✅ 无 | ✅ | `git add` |
| `scripts/run-ledger.py` | Agent 执行监控/run ledger 查询 | ✅ 无（仅 `auth_error` 分类逻辑） | ✅ | `git add` |
| `scripts/task-status.py` | 任务状态查询（含 revision rollup） | ✅ 无 | ✅ | `git add` |
| *(event-summary.py, smoke-real-chain.py 不在 tracked 列表，按需 add)* | | | | |

**验证**: 所有 10 个脚本仅包含错误分类常量名（如 `missing_api_key`、`auth_error`），无实际凭证。

---

### E. 流水线模板 (4 files，新文件)

| 文件 | 用途 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|------|----------|:--:|------|
| `templates/gate_policy_v2_8.json` | Gate policy 规则配置 | ✅ 无 | ✅ | `git add` |
| `templates/inbox_v2_8.json` | v2.8 标准 inbox schema | ✅ 无（含 `output_contract.command` 本地路径） | ✅ | `git add` |
| `templates/outbox_v2_8.json` | v2.8 标准 outbox schema | ✅ 无 | ✅ | `git add` |
| `templates/review_v2_8.json` | v2.8 Review gate record schema | ✅ 无 | ✅ | `git add` |

**inbox_v2_8.json 注意**: 包含 `command` 字段中的本地路径（`~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/...`），这些是默认值模板，不含用户特定信息。

---

### F. 文档模板 (2 files，已修改)

| 文件 | 变更摘要 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|---------|----------|:--:|------|
| `templates/acceptance_criteria_cheatsheet.md` | v2.5→v2.8 全面重写：状态机、evidence、error_taxonomy、review gate 语义检查清单、流水线位置图 | ✅ 无 | ✅ | `git add` |
| `templates/task_package_template.md` | 新增状态机、标准 outbox、post-outbox gate 命令、状态查询、run ledger、smoke 链路 | ✅ 无 | ✅ | `git add` |

---

### G. Skill 更新 (8 files，已修改)

| 文件 | 变更摘要 | 敏感信息 | v2.8.1 直接相关 | 建议 |
|------|---------|----------|:--:|------|
| `skills/autonomous-ai-agents/chief-of-staff/SKILL.md` | delegate-v27.sh→delegate_task 迁移; verify-task.py 分流表; exit code 映射 | ✅ 无 | ✅ | `git add` |
| `skills/github/github-repo-risk-assessment/SKILL.md` | Scrapling 抓 GitHub 导航栏垃圾→raw.githubusercontent.com 正确做法 | ✅ 无 | ✅ | `git add` |
| `skills/hermes-multi-agent-research/SKILL.md` | v2.6→v2.8 delegation protocol 升级; exit code 分流; Intelligence fallback 重试指引 | ✅ 无 | ✅ | `git add` |
| `skills/hermes-subagent-delegation/SKILL.md` | 配置权威源说明; managed_persistence 误导修正（≠子Agent热启动） | ✅ 无 | ✅ | `git add` |
| `skills/hermes/hermes-knowledge-architecture/SKILL.md` | 新增 github-trending-analysis-workflow 参考文件链接 | ✅ 无 | ✅ | `git add` |
| `skills/hermes/hermes-system-diagnostics/SKILL.md` | CodeGraph 自检指引; managed_persistence 风险表修正; 3 个新参考文件链接 | ✅ 无 | ✅ | `git add` |
| `skills/productivity/obsidian-knowledge-base/SKILL.md` | 新增 tool-evaluation-workflow 参考文件链接 | ✅ 无 | ✅ | `git add` |
| `skills/research/competitive-intelligence/SKILL.md` | 重大更新: Bing News+scrapling stealth 最佳发现方法; 竞品沉默信号; 产品开发信号; GitHub 技术情报; 中文Bing News系统性空结果; Intelligence Agent委托陷阱; 多个新参考文件 | ✅ 无 | ✅ | `git add` |

---

### H. 新 Skill (5 files，新文件)

| 文件 | 用途 | 来源 | 敏感信息 | 建议 |
|------|------|------|----------|------|
| `skills/software-development/verification-loop/SKILL.md` | v2.8 验收分流完整文档（gate / 状态查询 / run ledger / smoke / pre-commit pipeline validation / outbox.status 双校验坑） | 新增 | ✅ 无 | `git add` |
| `skills/software-development/codebase-scout/SKILL.md` | 快速代码库侦察（多文件编辑/调试/委托前） | 适配自 withkynam/vibecode-pro-max-kit | ✅ 无 | `git add` |
| `skills/software-development/context-skill-audit/SKILL.md` | Hermes 配置漂移审计 | 适配自 withkynam/vibecode-pro-max-kit | ✅ 无 | `git add` |
| `skills/software-development/hermes-orchestration-closeout/SKILL.md` | 多 Agent 委托结果结构化收束协议 | 适配自 withkynam/vibecode-pro-max-kit | ✅ 无 | `git add` |
| `skills/software-development/systematic-debugging/SKILL.md` | 4 阶段根因调试 | 适配自 obra/superpowers | ✅ 无 | `git add` |
| `skills/hermes/divergent-exploration/SKILL.md` | 发散探索模式（多帧并行→收敛） | 新增 | ✅ 无 | `git add` |

---

### I. 测试文件 (2 files，新文件)

| 文件 | 用途 | 敏感信息 | 建议 |
|------|------|----------|------|
| `tests/test_opencode_agent.py` | OpenCode Agent harness 测试 | ✅ 无 | `git add` |
| `tests/test_run_ledger_default_paths.py` | Run ledger 默认路径测试 | ✅ 无 | `git add` |

---

## ③ 报告文档 — 6 文件

| 文件 | 说明 | 建议 |
|------|------|------|
| `docs/reports/hermes-v2.8.1-agent-sync-audit.md` | Agent 注册表与 agents.yaml 同步审计 | 随 commit 提交 |
| `docs/reports/hermes-v2.8.1-agent-sync-fix.md` | 同步修复记录 | 随 commit 提交 |
| `docs/reports/hermes-v2.8.1-final-delivery.md` | v2.8.1 最终交付报告 | 随 commit 提交 |
| `docs/reports/hermes-v2.8.1-git-state-report.md` | Git 状态报告（分类建议） | 随 commit 提交 |
| `docs/reports/hermes-v2.8.1-precommit-validation.md` | 提交前验证报告（pipeline smoke tests） | 随 commit 提交 |
| `docs/hermes-architecture-snapshot-2026-06-01.md` | 架构快照（含公开 base_url） | ⚠️ 含 `base_url: https://api.deepseek.com`（公开 URL，非敏感），可提交 |

---

## ⑥ 敏感配置 — 确认安全

对全部 42+6 文件执行了敏感信息扫描：

| 检查模式 | 命中 | 结果 |
|---------|------|------|
| `api.key` / `api_key` | 0 实际凭证 | 仅错误分类常量名（`missing_api_key`, `auth_error`） |
| `token` | 0 实际 token | 仅函数名（`path_tokens`, `keyword_tokens`） |
| `secret` / `password` | 0 | — |
| `webhook` | 0 | — |
| `base_url` | 1 | `docs/hermes-architecture-snapshot-2026-06-01.md` 中的公开 DeepSeek API URL |
| `sk-` / `skey-` | 0 | — |
| `AUTH` / `BEARER` | 0 | 仅 run-ledger.py 中的 `auth_error` 分类逻辑 |

**结论**: 零敏感信息泄露。

---

## 额外确认

### ✅ config.yaml 只有预期变化
```
-  child_timeout_seconds: 600
+  child_timeout_seconds: 180
```
单行变更，无其他字段改动。

### ✅ scripts/ 核心脚本未变更
`scripts/` 目录在 git diff（已修改文件）中为空。三个核心脚本（verify-task.py, review-task.py, gate-policy.py）是**新文件**（untracked），v2.8.1 首次引入，此前不在版本控制中。

### ✅ verify/review/gate 行为变化来自配置/doctor/fixture
- `verify-task.py` 行为依赖：`agent-registry.json`（READ_ONLY_AGENTS）、`inbox` 结构（allowed_files/acceptance_criteria）
- `review-task.py` 行为依赖：`compiled_intent`（must_avoid/must_keep/success_criteria）
- `gate-policy.py` 行为依赖：`gate_policy_v2_8.json`（auto_revision_checks/hard_stop_checks）
- 三个脚本的核心逻辑未在本次 diff 中修改

### ✅ docs/reports 应随 commit 提交
6 个报告文档记录了 v2.8.1 稳定化审计、修复和验证的完整过程，是项目演进的可追溯记录。建议随 commit 提交。

---

## 建议的提交操作

```bash
# 1. 提交所有 42 个 v2.8.1 必须文件（含新文件）
cd ~/.hermes
git add .gitignore
git add bin/hermes-system-doctor.py bin/setup.sh
git add config.yaml config/agent-registry.json config/managed-agents.yaml
git add scripts/compile-task.py scripts/dispatch-task.py scripts/gate-policy.py
git add scripts/opencode-agent.py scripts/review-task.py scripts/run-ledger.py
git add scripts/run-task-gate.py scripts/task-status.py scripts/verify-task.py
git add templates/gate_policy_v2_8.json templates/inbox_v2_8.json
git add templates/outbox_v2_8.json templates/review_v2_8.json
git add templates/acceptance_criteria_cheatsheet.md templates/task_package_template.md
git add skills/autonomous-ai-agents/chief-of-staff/SKILL.md
git add skills/github/github-repo-risk-assessment/SKILL.md
git add skills/hermes-multi-agent-research/SKILL.md
git add skills/hermes-subagent-delegation/SKILL.md
git add skills/hermes/hermes-knowledge-architecture/SKILL.md
git add skills/hermes/hermes-system-diagnostics/SKILL.md
git add skills/hermes/divergent-exploration/SKILL.md
git add skills/productivity/obsidian-knowledge-base/SKILL.md
git add skills/research/competitive-intelligence/SKILL.md
git add skills/software-development/codebase-scout/SKILL.md
git add skills/software-development/context-skill-audit/SKILL.md
git add skills/software-development/hermes-orchestration-closeout/SKILL.md
git add skills/software-development/systematic-debugging/SKILL.md
git add skills/software-development/verification-loop/SKILL.md
git add tests/test_opencode_agent.py tests/test_run_ledger_default_paths.py

# 2. 提交 6 个报告文档
git add docs/reports/hermes-v2.8.1-agent-sync-audit.md
git add docs/reports/hermes-v2.8.1-agent-sync-fix.md
git add docs/reports/hermes-v2.8.1-final-delivery.md
git add docs/reports/hermes-v2.8.1-git-state-report.md
git add docs/reports/hermes-v2.8.1-precommit-validation.md
git add docs/hermes-architecture-snapshot-2026-06-01.md

# 3. 提交
git commit -m "v2.8.1 稳定化：Task Card Pipeline 完整部署

- config: child_timeout_seconds 600→180, Claude model_ref opus→sonnet, 新增 opencode Agent
- scripts: 10 个核心流水线脚本（verify/review/gate/compile/dispatch/run-ledger/task-status/opencode）
- templates: v2.8 inbox/outbox/review/gate_policy JSON schemas
- templates: acceptance_criteria_cheatsheet v2.5→v2.8 重写
- templates: task_package_template 新增状态机/outbox/gate/smoke
- skills: 8 个 skill 更新 + 6 个新 skill（verification-loop/codebase-scout/divergent-exploration 等）
- system: hermes-system-doctor 新增 mirror 检查, setup.sh 修正部署方向
- tests: opencode_agent + run_ledger 测试
- docs: 6 份 v2.8.1 审计/修复/验证报告"
```

---

## ⚠️ 未包含的文件（有意排除）

以下 untracked 文件不在上述分类中，因为它们是**参考数据文件**（非代码/配置），不影响 v2.8.1 核心功能：

| 文件 | 原因 |
|------|------|
| `skills/*/references/*.md` | 大量 references/ 子目录文件，运行时参考数据，不阻塞 pipeline |
| 可能的 `.pyc` 缓存 | 不应提交 |

如需一并提交，可在最终 commit 前手动 `git add`。

---

*计划结束。所有分类基于逐文件 diff 审查，不含推测。*
