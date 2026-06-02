# Task Package 模板 v3.0

> 内斯塔（B 技术专员）使用的标准任务包模板。
> 此模板已整合 autoresearch 三个设计模式：**二值化审核** · **NEVER_STOP** · **ALLOWED_FILES**
>
> 用法：每问题一个任务包，发给 Claude Code / deepseek-tui 等执行 Agent。

---

## 1. 元数据

```yaml
task_id: <UUID 或项目缩写-序号>
agent_id: claude                  # 执行 Agent（claude / deepseek-tui）
NEVER_STOP: true                  # 🤖 模式二：子 Agent 不得停下问"我该继续吗"
priority: P0/P1/P2
estimated_complexity: S/M/L/XL
```

### 状态机

任务状态必须使用以下枚举：

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

> **NEVER_STOP 说明（模式二）**：当此字段为 `true` 时，执行 Agent **不得在遇到不确定性时停下来问"我该继续吗"**。
> - 遇到模糊点 → 基于已有信息自己做合理判断，继续执行
> - 遇到可选路径 → 选最符合任务目标的那条，继续执行
> - 遇到错误 → 尝试自动修复或降级方案，继续执行
> - **只有一种情况可以停**：遇到无法自动恢复的阻塞（API KEY 缺失、文件系统不可写等硬性障碍）
>
> **何时加 NEVER_STOP**：
> - ✅ 批处理任务（批量改文件、批量数据处理）
> - ✅ 情报收集 / 定时执行任务
> - ✅ 无人在线时执行的任务
> - ❌ 交互式任务（需要人类确认方向的）
> - ❌ 新代码库的首次探索（方向未定）

---

## 2. Goal

```
一句话描述本次任务要达成什么目标。
```

---

## 3. 修改范围（模式三）

```
ALLOWED_FILES:
- <相对路径或绝对路径>
- <路径支持 glob 通配：src/**/*.py>

禁止修改不在列表中的任何文件。
```

> **ALLOWED_FILES 说明（模式三）**：
> - 执行 Agent **只允许修改此列表中的文件**
> - 发现需要改列表外文件时 → 先停下来，在 outbox 的 notes 中注明需求，**不要擅自修改**
> - 调研/情报类任务（不涉及文件修改）填 `N/A`
> - 部分调研可能需要保存输出到新文件 → 明确写出允许创建的文件路径

---

## 4. 具体步骤

```
Step 1: [做什么]
  - 操作细节
  - 验证方式

Step 2: [做什么]
  - 操作细节
  - 验证方式

...
```

---

## 5. 关键上下文

```
- 项目结构要点（如有）
- 相关文件链接（read_file 的输出片段）
- 需要特别注意的约束或依赖关系
- 之前尝试过的方案及结果（如适用）
```

---

## 6. 执行结论（模式一）

```
## 执行结论
- [ ] ✅ KEEP — 符合验收标准，可以合并
- [ ] ❌ DISCARD — 不满足，需要重做
- 理由：具体说明为什么 KEEP 或 DISCARD
```

> **KEEP / DISCARD 二值审核说明（模式一）**：
> - 执行 Agent 完成任务后，**必须**填写此区块
> - 只允许两个结论：✅ KEEP 或 ❌ DISCARD
> - 没有"还行"、"部分通过"、"建议修改后再看"——**二值**
> - DISCARD 时需明确列出哪些验收项不满足、具体差距是什么
> - 验收标准（下节）的每条都需要在理由中被覆盖

---

## 7. 验收标准

逐条列出本次任务必须满足的条件，所有标准都要能被 `KEEP/DISCARD` 二值结论覆盖：

```markdown
### 功能验收
- [ ] 条件 1
- [ ] 条件 2

### 质量验收
- [ ] 条件 3
- [ ] 条件 4
```

### 证据要求

执行 Agent 必须在 outbox 或执行结论中提供以下证据；缺失任一项时，质量门默认进入 `NEEDS HUMAN REVIEW`：

```yaml
evidence_required:
  - changed_files
  - verification_commands
  - verification_output_summary
  - known_risks
```

### 标准 outbox

执行 Agent 的 outbox 必须优先使用 `templates/outbox_v2_8.json` 结构。错误必须进入 `error_taxonomy`：

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

### 默认派发入口

主 Hermes 使用 Task Card `output_contract.dispatch.command` 派发任务。该命令会读取 inbox，
选择 `execution_plan.primary_agent`，并通过 Hermes runtime `delegate_task(agent_id=...)`
交给对应子 Agent 执行。派发时会注入 `templates/outbox_v2_8.json` 的必填字段和最小 JSON 示例，
降低 malformed outbox 概率：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/dispatch-task.py --inbox <inbox_path>
```

### Post-Outbox Gate（v2.8 默认）

子 Agent 写完 outbox 后，主 Hermes 必须使用 Task Card `output_contract.post_outbox_gate.command`
中的 **单一命令** 执行自动验收分流，并将 gate record 写入
`output_contract.post_outbox_gate.record_path`：

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

`run-task-gate.py` 内部依次执行两步：
1. **verify（结构校验）** — 检查 outbox schema、必需字段、changed_files 完整性（由 `verify-task.py` 完成）
2. **review（语义审核）** — 检查任务目标覆盖、证据充分性、风险合理性（由 `review-task.py` 完成）
3. **policy（分流策略）** — 将 gate decision 与 failed checks 映射为 `complete / auto_revision / manual_review / reject / switch_agent / blocked`

输出三种结果之一：

| result | 含义 | 后续动作 |
|--------|------|----------|
| `approved` | 全部通过（结构 + 语义） | 可直接合并 / 交付 |
| `revision_needed` | 存在可自动修复的问题 | 自动生成下一轮 revision inbox，子 Agent 按返工 brief 修改 |
| `rejected` | 硬失败（缺失证据、schema 违反等） | 返工重做，或标记 blocked / failed |

> 底层仍然保留 `verify-task.py` 和 `review-task.py` 供手动分步调试，但日常交付必须使用
> Task Card 自带的 `post_outbox_gate.command`，不得绕过 gate 直接交付子 Agent outbox。
> 默认最多自动生成 2 轮 revision inbox；超过上限后转人工处理，避免无限返工。
> 如需让 gate 在生成 revision inbox 后立刻派发，可显式追加 `--auto-dispatch-revision`。
> 自动返工与自动派发必须同时通过 `gate-policy.py`；`allowed_files_check`、`must_avoid_respected` 等硬失败不会自动返工。

### 状态查询

任务状态由 `events.jsonl` 同步写入 `tasks/index.jsonl`。日常查询使用：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/task-status.py --project <project>
```

默认会折叠自动返工链路，显示类似 `approved via <task_id>_rev1` 的最终状态。
调试原始父子任务事件时使用：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/task-status.py --project <project> --no-rollup
```

事件时间线：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/event-summary.py --project <project>
```

### Agent Execution Watchdog / Run Ledger

外部 Agent 执行会写入：

```text
~/.claude/teams/<project>/runs/ledger.jsonl
```

查询最近执行：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/run-ledger.py --project <project>
```

查询 run 时间线：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/event-summary.py --project <project> --runs
```

Run ledger 会记录 `run_id`、`agent_id`、`duration_seconds`、`exit_code`、`classification`
和 stdout/stderr tail。`task-status.py` 的 `RUN` 列会显示最近一次 run 分类，便于定位
Claude / DeepSeek 卡死、超时、鉴权或权限问题。

### 真实链路 Smoke

修改 delegation、gate、policy 或外部 Agent 配置后，优先跑 `/tmp` 临时真实链路：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent claude
```

可选 DeepSeek TUI：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent deepseek-tui
```

先只检查任务包和派发命令：

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/smoke-real-chain.py --agent claude --dry-run
```

Gate approved 后会生成 `commit_suggestion`（diff 摘要 + 建议 commit message），但不会自动提交。

---

## 8. 执行顺序建议

```
- 步骤之间的依赖关系
- 并行执行的可能性
- ⚠️ 风险提醒（如有）
```

---

*模板结束。以下是一个虚拟任务演示示例。*

---

## 示例：更新用户配置文件解析逻辑

### 1. 元数据

```yaml
task_id: UC-001
agent_id: claude
NEVER_STOP: true
priority: P1
estimated_complexity: M
```

### 2. Goal

将 `config.py` 中的 YAML 配置文件解析逻辑从 `pyyaml` 迁移到 `ruamel.yaml`，保持所有已有配置键的读取行为不变。

### 3. 修改范围

```
ALLOWED_FILES:
- src/config.py
- src/tests/test_config.py
- pyproject.toml
```

### 4. 具体步骤

```
Step 1: 在 pyproject.toml 中添加 ruamel.yaml 依赖
  - 将 `PyYAML` 替换为 `ruamel.yaml>=0.18`
  - 验证：pip install -e . 安装成功

Step 2: 修改 src/config.py 中的解析逻辑
  - 将 `yaml.load()` / `yaml.safe_load()` 替换为 `ruamel.yaml.YAML().load()`
  - 保持所有返回的数据结构格式不变（dict/list 结构一致）
  - 验证：python -c "from config import load_config; print(load_config('test.yml'))"

Step 3: 更新测试用例
  - 确保 test_config.py 中的所有测试继续通过
  - 验证：pytest src/tests/test_config.py -v
```

### 5. 关键上下文

```
- 现有 config.py 中约 80 行配置解析逻辑
- 主要函数：load_config(path: str) → dict
- 已有测试覆盖了 5 种配置文件格式（空文件、嵌套、含注释、含变量引用、无效格式）
- ruamel.yaml 特性：保留注释、保留 YAML 格式（目前不需要，但为后续功能铺路）
```

### 6. 执行结论

```
## 执行结论
- [ ] ✅ KEEP — 符合验收标准，可以合并
- [ ] ❌ DISCARD — 不满足，需要重做
- 理由：
```

### 7. 验收标准

```markdown
### 功能验收
- [ ] load_config('test.yml') 对所有已有测试用例返回一致结果
- [ ] 嵌套结构、列表、字典等复杂 YAML 结构解析正确

### 质量验收
- [ ] ruamel.yaml 已正确添加为项目依赖
- [ ] PyYAML 引用已全部移除
- [ ] 所有已有测试通过
- [ ] 没有修改 ALLOWED_FILES 之外的任何文件

### 兼容性验收
- [ ] 与现有调用方代码兼容（API 签名不变）
```

### 证据要求

```yaml
evidence_required:
  - changed_files
  - verification_commands
  - verification_output_summary
  - known_risks
```

### 8. 执行顺序建议

```
- Step 1 → Step 2 → Step 3（顺序依赖）
- 无并行执行
- ⚠️ 注意：ruamel.yaml 加载后的返回类型是 ruamel.yaml.comments.CommentedSeq/CommentedMap 而非原生 list/dict，可能需要递归转换为标准类型
```

---

*模板与示例结束。*
