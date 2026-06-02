---
name: verification-loop
description: Hermes 交付前验证循环。用于代码、配置、文档任务完成前识别项目类型、选择最小真实验证命令、汇总证据，并明确残余风险。
tags:
- verification
- testing
- quality-gate
- hermes
category: software-development
agents:
- claude
- codex
- ambrosini
- hermes-internal
---

# Verification Loop — Hermes 交付前验证

## 触发条件

当任务涉及以下任一情况时加载此技能：
- 代码、配置、脚本、部署或文档结构发生修改
- 子 Agent 在 outbox 中声明任务完成
- Ambrosini 需要做最终质量门验收
- 用户要求“验证”“质量门”“跑测试”“确认生效”

## 核心原则

1. **真实验证优先**：优先运行项目已有命令，而不是发明新命令。
2. **最小有效验证**：根据改动范围选择能证明结果的最小命令集合。
3. **失败即证据**：失败输出也要记录，不能改写成“基本完成”。
4. **无法验证要明说**：写清楚未验证原因、缺失依赖和下一步。
5. **不强制固定覆盖率**：覆盖率阈值遵循项目自身配置；没有配置时不硬塞 80%。

## 验证流程

### Step 1: 识别项目类型

先读取当前目录和改动文件，查找：

```bash
git diff --name-only
find . -maxdepth 3 \( -name package.json -o -name pyproject.toml -o -name Cargo.toml -o -name go.mod -o -name Makefile \) -print
```

根据项目文件选择命令：
- Node.js：`npm run lint`、`npm test`、`npm run build`、`npm run typecheck`
- Python：`pytest`、`mypy .`、`ruff check .`
- Rust：`cargo test`、`cargo clippy`
- Go：`go test ./...`、`go vet ./...`
- Makefile：优先查看并复用 `make test`、`make lint`、`make build`

### Step 2: 回读关键文件

配置类修改必须回读目标文件，确认写入位置和内容正确。

```bash
git diff -- <changed-file>
```

### Step 3: 执行最小真实调用

选择和任务直接相关的验证命令。示例：

```bash
npm test -- --runInBand
pytest path/to/test_file.py -q
python -m compileall path/to/package
go test ./pkg/...
```

### Step 4: 检查改动范围

确认没有越过任务包的 `ALLOWED_FILES`：

```bash
git diff --name-only
git diff --stat
```

### Step 5: 输出验证报告

必须使用以下格式：

```text
VERIFICATION REPORT
Build:    PASS/FAIL/SKIPPED - 命令与结果摘要
Types:    PASS/FAIL/SKIPPED - 命令与结果摘要
Lint:     PASS/FAIL/SKIPPED - 命令与结果摘要
Tests:    PASS/FAIL/SKIPPED - 命令与结果摘要
Security: PASS/FAIL/SKIPPED - 是否检查 secrets/权限/输入边界
Diff:     PASS/FAIL - 改动文件是否符合 ALLOWED_FILES

Overall: READY / NOT READY / NEEDS HUMAN REVIEW

Evidence:
- changed_files: ...
- verification_commands: ...
- verification_output_summary: ...
- known_risks: ...
```

## 判定规则

- 任一关键验证失败：`Overall = NOT READY`
- 验证命令无法运行但原因合理：`Overall = NEEDS HUMAN REVIEW`
- 无测试但任务低风险且已做最小真实调用：可 `READY`，但必须列出残余风险
- 配置类修改没有回读文件或真实调用：不得 `READY`

## v2.8 Outbox 验收分流

主 Hermes 使用 Task Card `output_contract.dispatch.command` 派发任务。该命令会读取 inbox，
选择 `execution_plan.primary_agent`，并通过 Hermes runtime `delegate_task(agent_id=...)`
交给对应子 Agent 执行。派发时会注入 `templates/outbox_v2_8.json` 的必填字段和最小 JSON 示例，
降低 malformed outbox 概率：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/dispatch-task.py --inbox <inbox_path>
```

子 Agent 写入 outbox 后，主 Hermes 必须使用 Task Card
`output_contract.post_outbox_gate.command` 中的 **单一命令** 执行自动验收分流（v2.8 默认 gate），
并将 gate record 写入 `output_contract.post_outbox_gate.record_path`：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/run-task-gate.py \
  --inbox <inbox_path> \
  --outbox <outbox_path> \
  --output <review_record_path> \
  --event-log <team_events_jsonl> \
  --task-index <team_tasks_index_jsonl> \
  --summary \
  --create-revision-inbox
```

`run-task-gate.py` 内部依次运行两步：
1. **verify（结构校验）** — 对应底层 `verify-task.py`，检查 outbox schema、必需字段、changed_files 完整性
2. **review（语义审核）** — 对应底层 `review-task.py`，检查任务目标覆盖、证据充分性、风险合理性
3. **policy（分流策略）** — 对应 `gate-policy.py`，将 gate decision 与 failed checks 映射为 `complete / auto_revision / manual_review / reject / switch_agent / blocked`

输出三种结果之一：

| result | 含义 | 后续动作 |
|--------|------|----------|
| `approved` | 全部通过（结构 + 语义） | 可直接合并 / 交付 |
| `revision_needed` | 存在可自动修复的问题 | 自动生成下一轮 revision inbox，子 Agent 按返工 brief 修改 |
| `rejected` | 硬失败（缺失证据、schema 违反等） | 返工重做，或标记 blocked / failed |

默认最多自动生成 2 轮 revision inbox；超过上限后转人工处理，避免无限返工。
如需让 gate 在生成 revision inbox 后立刻派发，可显式追加 `--auto-dispatch-revision`。
自动返工与自动派发必须同时通过 `gate-policy.py`；`allowed_files_check`、`must_avoid_respected` 等硬失败不会自动返工。

### 状态查询

任务状态由 `events.jsonl` 同步写入 `tasks/index.jsonl`。日常查询使用：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/task-status.py --project <project>
```

默认状态视图会把自动返工链路折叠成一条记录，例如
`original_task -> approved via original_task_rev1`。如需调试原始父子事件，可追加 `--no-rollup`。

事件时间线查询：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/event-summary.py --project <project>
```

### Agent Execution Watchdog / Run Ledger

外部执行（dispatch、自动 revision dispatch）会写入 run ledger：

```text
~/.claude/teams/<project>/runs/ledger.jsonl
```

每条 run 会记录 `run_id`、`task_id`、`agent_id`、`run_type`、开始/结束时间、耗时、
`exit_code`、`classification`（如 `ok`、`timeout`、`permission_error`、`auth_error`、
`rate_limited`、`process_error`）。

查询最近 run：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/run-ledger.py --project <project>
```

查看 run 时间线：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/event-summary.py --project <project> --runs
```

`task-status.py` 默认会把最新 run 分类显示在 `RUN` 列；当 Claude / DeepSeek 卡住或超时时，
先查 run ledger，再看对应 `run_id` 的 stdout/stderr tail。

### 真实协作链路 Smoke

当修改了 delegation、gate、policy、outbox contract 或外部执行器配置后，运行真实链路 smoke。
该脚本只在 `/tmp` 下创建临时文件：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent claude
```

如需验证 DeepSeek TUI 执行链路：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent deepseek-tui
```

如只想检查任务包和派发命令，不调用外部 Agent：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent claude --dry-run
```

当 gate 最终 `approved` 时，gate record 会附带 `commit_suggestion`：
- `commit_message`
- `diff_stat`
- `diff_name_only`

这只是提交建议；脚本不会自动 `git add` 或 `git commit`。

### 底层分步命令（调试用）

日常交付用 Task Card 自带的 `post_outbox_gate.command` 一条命令即可。如需手动分步调试，可单独运行底层脚本：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/verify-task.py --inbox <inbox_path> --outbox <outbox_path> --summary
```

`verify-task.py` exit code 映射（保留参考）：

| exit code | result | 含义 |
|-----------|--------|------|
| 0 | `pass` | 结构校验通过 |
| 2 | `needs_human_review` | 无硬失败，但有人工判定项 |
| 1 | `fail` | 结构硬失败 |

### 提交前 Smoke 验证（Pre-Commit Pipeline Validation）

修改 delegation、gate、policy、outbox contract 或核心配置后，在提交前运行只读 pipeline smoke 验证，
确保变更未破坏 Task Card Pipeline。所有测试数据写入 `/tmp`，不接触生产文件。

**流程**：`git diff 概览 → config 敏感信息审查 → scripts/ 变更检查 → system-doctor → 5 项 pipeline smoke`

**Smoke 测试矩阵**（用合成 JSON 覆盖 4 条异常路径）：

| # | 场景 | 工具 | 预期 | 关键验证点 |
|---|------|------|------|-----------|
| 1 | 只读 Agent + 空 changed_files | verify-task.py | PASS | 正常路径畅通 |
| 2 | 只读 Agent + 非空 changed_files | verify-task.py | FAIL + SCOPE_VIOLATION | 越权拦截 |
| 3 | 缺少 evidence（verification_commands / git_diff） | review-task.py → gate-policy.py | artifact_missing → auto_revision | 证据缺失自动返工 |
| 4 | changed_files 超出 allowed_files | review-task.py → gate-policy.py | scope_violation → reject | 越界拒绝 |
| 5 | revision 超过 max_revisions | gate-policy.py | manual_review | 超限转人工 |

**合成测试数据模板**：见 `references/precommit-smoke-test-pattern.md`

**完整提交前验证流程示例**：`docs/reports/hermes-v2.8.1-precommit-validation.md`（5 项 pipeline smoke 的完整执行结果、发现的问题、最终结论）

**Commit Staging Plan 模板**：`docs/reports/hermes-v2.8.1-commit-staging-plan.md`（变更文件 6 分类法：必须提交/可选/报告/本地运行时/历史遗留/敏感配置）

### ⚠️ Pitfall: outbox.status 双校验冲突

`verify-task.py` 对 outbox.status 执行两次校验，使用不同枚举集：

| 校验函数 | 枚举集 | 有效值示例 |
|---------|--------|-----------|
| `validate_status()` | `TASK_STATUSES` | `created`, `completed`, `waiting_for_verification`, ... |
| `validate_standard_outbox()` | `VALID_OUTBOX_STATUSES` | `success`, `failed`, `blocked` |

**影响**：标准格式 outbox（含 `agent_id` + `next_action`）的 status 必须同时满足两个集合。
`"success"` 不在 TASK_STATUSES 中，`"completed"` 不在 VALID_OUTBOX_STATUSES 中。
这是故意的语义分层——任务层状态机 vs 交付层结果——非 Bug。
非标准格式 outbox（无 agent_id+next_action）不受此影响。

**构造测试 outbox 时**：用非标准格式（不加 agent_id+next_action）搭配 TASK_STATUSES 值如 `completed`，
可绕过双校验，专注测试其他维度。

> 完整设计分析和未来拆分方案见 **ADR**: `docs/adr/ADR-verify-task-dual-status-validation.md`。
> 包含：代码路径图、枚举对照表、`task_status` / `delivery_status` 拆分方案、v2.8.2/v2.9 迁移建议。
