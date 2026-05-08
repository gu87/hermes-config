# v2.5 验收标准速查卡

> 规则：子 Agent 只输出事实（summary + changed_files + errors），`verification` 由验收方（verify-task.py / 人工）根据本标准自动生成。

---

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
  "acceptance_criteria": [
    {
      "item": "任务目标已完成",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["对照 inbox.goal 检查 summary 是否覆盖所有要求"]
    },
    {
      "item": "输出内容符合指定用途和受众",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查表达风格、术语使用是否匹配受众"]
    },
    {
      "item": "没有删除原有关键业务信息",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["对照原文件检查关键数据、结论是否保留"]
    },
    {
      "item": "没有新增明显无关内容",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["检查新增段落是否与 goal 相关"]
    },
    {
      "item": "没有虚构明确数据、报价、结论或事实",
      "check_type": "human_review",
      "auto_checkable": false,
      "review_hints": ["核对 summary 中的数字、结论是否有来源支撑"]
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
