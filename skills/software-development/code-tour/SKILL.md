---
name: code-tour
description: 创建可复用的代码导览 .tour 文件，用真实文件、目录、行号或 pattern 锚定架构、PR、RCA、安全边界和新人 onboarding 路径。
tags:
- code-tour
- onboarding
- architecture
- documentation
category: software-development
agents:
- codex
- hermes-internal
- claude
---

# Code Tour — 可导航代码导览

## 触发条件

当用户要求以下内容时加载此技能：
- “给我做一个代码导览”
- “解释这个系统怎么运转”
- “新成员 onboarding 路线”
- “这个 PR / bug / 安全边界怎么走”
- 需要把一次解释沉淀成可复用 artifact

## 输出约束

- 只创建或更新 `.tours/*.tour`
- 不修改业务代码
- 每个文件、目录、行号、selection 或 pattern 必须真实存在
- 不允许猜行号；写入前必须回读文件确认 anchor
- 第一条 step 必须锚定真实文件或目录，不能只是纯文字

## 推荐文件名

```text
.tours/<persona>-<focus>.tour
```

示例：

```text
.tours/new-joiner-hermes-routing.tour
.tours/pr-reviewer-gateway-change.tour
.tours/security-reviewer-auth-boundary.tour
```

## Step 类型

### Directory

```json
{ "directory": "skills/software-development", "title": "Software Skills", "description": "这里放软件工程相关技能。" }
```

### File + line

```json
{ "file": "config/agent-registry.json", "line": 1, "title": "Agent Registry", "description": "多 Agent 编制的主要入口。" }
```

### Selection

```json
{
  "file": "templates/task_package_template.md",
  "selection": {
    "start": { "line": 1, "character": 0 },
    "end": { "line": 20, "character": 0 }
  },
  "title": "Task Package Header",
  "description": "任务包的元数据和执行边界从这里开始。"
}
```

### Pattern

```json
{ "file": "skills/hermes-subagent-delegation/SKILL.md", "pattern": "## 排查流程", "title": "Delegation Debug Flow" }
```

## 导览结构

默认叙事顺序：

1. 系统入口
2. 角色或模块地图
3. 核心执行路径
4. 风险或容易误解的点
5. 下一步阅读建议

## 验证

完成前必须检查：

```bash
test -d .tours
python -m json.tool .tours/<file>.tour >/dev/null
```

并逐项确认：
- `file` 路径存在
- `directory` 路径存在
- `line` 不越界
- `pattern` 能在对应文件中搜到

