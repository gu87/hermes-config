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

### 8. 执行顺序建议

```
- Step 1 → Step 2 → Step 3（顺序依赖）
- 无并行执行
- ⚠️ 注意：ruamel.yaml 加载后的返回类型是 ruamel.yaml.comments.CommentedSeq/CommentedMap 而非原生 list/dict，可能需要递归转换为标准类型
```

---

*模板与示例结束。*
