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

