# v2.8 验收标准速查卡

> 规则：子 Agent 输出事实和证据，`verify-task.py` 负责结构化检查；Ambrosini 或人工负责最终质量判断。

---

## v2.8 状态机

```text
created
dispatched
running
waiting_for_verification
needs_human_review
completed
discarded
failed
blocked
```

默认流程：`created -> dispatched -> running -> waiting_for_verification -> completed`。

证据不足时进入 `needs_human_review`；任务失败但可恢复时进入 `blocked`；不可恢复失败进入 `failed`。

## v2.8 标准 evidence

所有执行类任务默认要求：

```json
{
  "evidence_required": [
    "changed_files",
    "verification_commands",
    "verification_output_summary",
    "known_risks"
  ]
}
```

`known_risks: []` 是合法值，表示执行 Agent 明确声明无已知风险。

## v2.8 错误分类

`errors` 非空时必须填写 `error_taxonomy`：

```text
model_error
tool_permission_error
missing_api_key
timeout
invalid_output_schema
verification_failed
allowed_files_violation
human_input_required
runtime_error
unknown_error
```

## 结构化验收字段说明

```json
{
  "item": "验收项描述",
  "check_type": "检查类型",
  "auto_checkable": false,
  "review_hints": ["人工核对时的提示语"]
}
```

| check_type | 含义 | 自动检查方式 |
|-----------|------|-------------|
| `required_fields` | outbox 必填字段是否齐全 | verify-task.py 检查 JSON 键 |
| `changed_files_subset` | 修改范围是否越界 | verify-task.py 对比 inbox.files |
| `files_exist_and_modified` | 声称修改的文件是否真实存在且时间戳更新 | verify-task.py 查文件系统 |
| `human_review` | 需人工判断内容质量 | 输出到 review checklist，由人逐项勾选 |

---

## 通用默认（所有任务）

```json
{
  "acceptance_criteria": {
    "auto_checkable": [
      "changed files must be within allowed_files",
      "outbox must contain all required fields"
    ],
    "human_review": [
      "任务目标已完成",
      "输出内容符合指定用途和受众",
      "没有删除原有关键业务信息",
      "没有新增明显无关内容",
      "没有虚构明确数据、报价、结论或事实"
    ],
    "evidence_required": [
      "changed_files",
      "verification_commands",
      "verification_output_summary",
      "known_risks"
    ]
  }
}
```

---

## 文档修改类 (document_edit)

```json
{
  "acceptance_criteria": [
    {
      "item": "目标文档已按要求修改",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["逐条对照 goal 确认修改点是否落实"]
    },
    {
      "item": "原有关键业务信息未被删除",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查原文件关键段落、数据是否在修改后保留"]
    },
    {
      "item": "结构、标题、段落层级清晰",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查大纲结构是否合理，无断层或重复"]
    },
    {
      "item": "没有新增与任务无关的内容",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认新增段落均与 goal 直接相关"]
    },
    {
      "item": "只修改 files 中列出的文件",
      "check_type": "changed_files_subset",
      "auto_checkable": true
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 方案生成类 (proposal_generation)

```json
{
  "acceptance_criteria": [
    {
      "item": "已生成指定方案或补充指定章节",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认 goal 中要求的模块/章节均已覆盖"]
    },
    {
      "item": "内容包含任务要求的核心模块",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查方案结构是否完整，无遗漏核心环节"]
    },
    {
      "item": "逻辑结构清晰，适合实际业务沟通",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断方案是否可直接用于内部讨论或对外汇报"]
    },
    {
      "item": "没有把推测写成确定事实",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["标记文中缺乏数据支撑的确信表述"]
    },
    {
      "item": "没有虚构明确数据、报价或外部案例",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["核对所有数字、案例、引用是否真实可查"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 调研整理类 (research_summary)

```json
{
  "acceptance_criteria": [
    {
      "item": "资料已按主题或问题结构化整理",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查 findings 是否围绕 goal 中的问题组织"]
    },
    {
      "item": "重要结论有来源、上下文或不确定性说明",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["对照 sources 检查关键结论是否有出处"]
    },
    {
      "item": "不确定信息已列入 unknowns",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查 unknowns 是否诚实反映了信息缺口"]
    },
    {
      "item": "没有把推测写成确定结论",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["区分 findings 中的事实陈述和推测性判断"]
    },
    {
      "item": "输出适合后续由 Hermes 继续分析或转成方案",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断 findings 的结构是否可直接用于下一步任务"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、findings、sources、unknowns、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    }
  ]
}
```

> 调研类任务通常不修改文件，因此无 `changed_files_subset` 和 `files_exist_and_modified` 检查。

---

## 复盘总结类 (review_summary)

```json
{
  "acceptance_criteria": [
    {
      "item": "已总结目标项目或活动的背景、动作、结果和问题",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认背景-动作-结果-问题的逻辑链完整"]
    },
    {
      "item": "区分事实、判断和建议",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查是否有客观事实被包装成主观判断"]
    },
    {
      "item": "没有虚构未提供的数据或结论",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["核对复盘中的关键数字是否与输入资料一致"]
    },
    {
      "item": "问题和建议具有可执行性",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断建议是否具体到可落地执行"]
    },
    {
      "item": "输出结构适合内部复盘或汇报使用",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查格式是否可直接转发或开会使用"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 数据/表格处理类 (data_processing)

```json
{
  "acceptance_criteria": [
    {
      "item": "目标数据文件已按要求处理",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["抽样检查数据行，确认处理逻辑正确执行"]
    },
    {
      "item": "原始字段含义未被误改",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["对照原表检查字段名、类型是否被意外修改"]
    },
    {
      "item": "新增字段或计算结果有说明",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查 summary 是否说明了新增字段的计算逻辑"]
    },
    {
      "item": "输出格式可正常打开",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    },
    {
      "item": "如涉及计算，需说明计算逻辑",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认 summary 或 notes 中记录了计算公式/规则"]
    },
    {
      "item": "只修改 files 中列出的文件",
      "check_type": "changed_files_subset",
      "auto_checkable": true
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 项目管理类 (project_management)

```json
{
  "acceptance_criteria": [
    {
      "item": "任务已拆解为可执行步骤",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查每个步骤是否具体到可分配给某个人执行"]
    },
    {
      "item": "每个步骤有负责人、输入、输出或完成标准",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认关键步骤含 WHO / WHAT IN / WHAT OUT"]
    },
    {
      "item": "优先级和依赖关系清晰",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查是否有步骤顺序或阻塞关系说明"]
    },
    {
      "item": "没有过度复杂化流程",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断步骤数量是否与项目规模匹配"]
    },
    {
      "item": "输出适合直接用于推进或同步",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查格式是否可直接发群或开会使用"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 内容策划类 (content_planning)

```json
{
  "acceptance_criteria": [
    {
      "item": "内容方向符合指定平台、受众和业务目标",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["对照 goal 中的平台/受众要求检查调性是否匹配"]
    },
    {
      "item": "选题、文案或节奏清晰可用",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断内容是否可直接进入制作或发布流程"]
    },
    {
      "item": "没有虚构未经确认的事实或数据",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["核对文案中的数字、引用、案例是否真实"]
    },
    {
      "item": "表达风格符合任务要求",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查语气、用词是否匹配品牌或场景要求"]
    },
    {
      "item": "保留需要人工确认的不确定项",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认 notes 或 errors 中标注了需要人拍板的地方"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

---

## 小范围文件执行类 (file_execution)

```json
{
  "acceptance_criteria": [
    {
      "item": "目标文件已生成或修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    },
    {
      "item": "文件格式可正常打开或解析",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    },
    {
      "item": "没有创建额外无关文件",
      "check_type": "changed_files_subset",
      "auto_checkable": true
    },
    {
      "item": "没有修改范围外文件",
      "check_type": "changed_files_subset",
      "auto_checkable": true
    },
    {
      "item": "如果运行命令，需在 summary 或 notes 中说明",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查 summary/notes 是否记录了关键命令及其作用"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    }
  ]
}
```

---

## 混合任务 (mixed)

```json
{
  "acceptance_criteria": [
    {
      "item": "混合任务需拆分子任务，每个子任务分别验收",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["确认是否已拆分为多个独立 inbox/outbox，分别运行 verify-task.py"]
    },
    {
      "item": "无拆分时，按主要任务类型选择对应验收标准",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["判断当前 mixed 任务以哪种类型为主，套用对应标准"]
    },
    {
      "item": "outbox 包含 task_id、status、summary、changed_files、errors",
      "check_type": "required_fields",
      "auto_checkable": true
    },
    {
      "item": "changed_files 中的文件真实存在且已被修改",
      "check_type": "files_exist_and_modified",
      "auto_checkable": true
    }
  ]
}
```

> mixed 任务本质上是多个子任务的组合。推荐做法：拆分为独立 inbox/outbox 对，分别验收。如果必须合并为一个 outbox，则按主导任务类型选择验收标准，并额外人工检查各子目标是否都被覆盖。

---

## task_type 参考列表

| 类型 | 是否需要 changed_files 检查 | 特殊 outbox 字段 |
|------|---------------------------|-----------------|
| `document_edit` | ✅ | — |
| `proposal_generation` | ✅ | — |
| `research_summary` | ❌ | findings, sources, unknowns |
| `review_summary` | ✅ | — |
| `data_processing` | ✅ | — |
| `project_management` | ✅ | — |
| `content_planning` | ✅ | — |
| `file_execution` | ✅ | — |
| `mixed` | ✅ | 按主导类型决定 |

---

## v2.8 Outbox 字段说明

> 模板路径：`templates/outbox_v2_8.json`。所有子 Agent 执行完成后，必须按此模板输出 outbox JSON。

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定为 `"2.8"` |
| `task_id` | string | 与 inbox 一一对应的任务 ID |
| `agent_id` | string | 执行 Agent 标识 |
| `status` | string | v2.8 状态机状态，默认 `waiting_for_verification` |
| `summary` | string | 一句话说明实际完成内容 |
| `changed_files` | string[] | 本次任务实际修改的文件列表 |
| `changed_files_source` | string | **必须为 `"git_diff"`**，表示 changed_files 由系统级 `git diff` 检测，而非 Agent 自述 |
| `needs_human_review` | boolean | `true` 表示证据不足，需人工介入；`false` 表示证据完整 |
| `errors` | string[] | 错误列表；非空时必须填写 `error_taxonomy` |
| `error_taxonomy` | object[] | 错误分类对象数组；每项必须包含 `code` 和 `message`，可选 `recoverable` boolean |
| `verification` | object | 包含 `status`、`commands`、`output_summary` 的验证信息块 |
| `evidence` | object | 结构化证据块，含 `changed_files`、`verification_commands`、`verification_output_summary`、`known_risks`、`tool_trace` |
| `known_risks` | string[] | 已知风险；空数组 `[]` 表示 Agent 明确声明无已知风险 |
| `notes` | string[] | 补充说明 |

### 关键约束

```text
1. changed_files 必须由 git diff 检测，禁止 Agent 自述改动。changed_files_source 始终为 "git_diff"。
2. needs_human_review = true 时，status 自动进入 needs_human_review，等待人工/Ambrosini 介入。
3. errors 非空时 error_taxonomy 必填；每个 `code` 必须来自预定义类目。
4. verification.commands 中应填写实际运行的验证命令，verification.output_summary 填写实际输出摘要。
```

### error_taxonomy 示例

```json
[
  {
    "code": "verification_failed",
    "message": "pytest failed",
    "recoverable": true
  }
]
```

---

## Review Gate v2.8

> 规则：`verify-task.py` 先做结构化验证（pass / needs_human_review / fail），Review Gate 再做语义审查（approved / revision_needed / rejected）。只有结构通过的 outbox 才进入语义审查。

### 三项 Gate Decision

| decision | 含义 | 触发条件 | 后续动作 |
|----------|------|---------|---------|
| `approved` | 通过，交付用户 | 结构无问题 + 语义全部通过 | 标记 `completed`，内容交付用户 |
| `revision_needed` | 退回修改 | 结构通过但有小问题（summary 不准、遗漏 must_keep、格式偏差等） | 退回原 Agent，附具体 revision_notes，修正后重走 verify→review |
| `rejected` | 拒绝，升级人工 | 结构性违规（verify 返回 fail）、严重虚构、多次 revision 仍不达标 | 标记 `failed` 或 `needs_human_review`，通知人工/Ambrosini 介入 |

### verify-task.py 结果 → Gate Decision 映射

```
verify-task.py exit 0 (pass)
  → gate: approved 或 revision_needed
  → 不可 rejected（结构已通过）

verify-task.py exit 2 (needs_human_review)
  → gate: approved / revision_needed / rejected 均可
  → 需逐项检查 human_review 类 criteria

verify-task.py exit 1 (fail)
  → gate: rejected
  → 结构违规的 outbox 不进入语义审查，直接拒绝
```

### 语义检查清单 (SC-01 ~ SC-08)

| ID | 检查项 | 类别 |
|----|--------|------|
| SC-01 | summary 是否准确反映 changed_files 实际改动 | accuracy |
| SC-02 | must_keep 约束是否全部满足 | compliance |
| SC-03 | must_avoid 约束是否全部遵守 | compliance |
| SC-04 | success_criteria 完成标准是否全部达到 | completeness |
| SC-05 | 输出质量是否适合交付给用户 | quality |
| SC-06 | 是否有虚构事实、数据或未经支持的断言 | integrity |
| SC-07 | Agent 是否诚实声明了 known_risks | integrity |
| SC-08 | evidence 块是否提供了足够的验证证据 | completeness |

### 何时退回 Agent vs 升级人工

| 场景 | 路由 |
|------|------|
| summary 措辞不准、缺少关键说明 | → revision_needed，退回 Agent |
| 漏改了 must_keep 中要求的某项 | → revision_needed，退回 Agent |
| 输出格式有小偏差（如缺少换行、字段命名不规范） | → revision_needed，退回 Agent |
| 改动了 must_avoid 禁止的文件 | → rejected，升级人工 |
| 虚构了不存在的数据或事实 | → rejected，升级人工 |
| 完全偏离任务目标，产出了无关内容 | → rejected，升级人工 |
| 同一任务经历 3+ 次 revision 仍不达标 | → rejected，升级人工 |
| verify-task.py 返回 fail | → rejected，升级人工 |

### 流水线位置

```
子 Agent 输出 outbox → verify-task.py (结构化) → Review Gate (语义) → 交付/退回/升级
```

详细 schema 见 `templates/review_v2_8.json`。
