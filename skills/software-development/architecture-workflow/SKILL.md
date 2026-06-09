---
name: architecture-workflow
description: Architecture review and ADR design workflow — phased delivery from problem analysis through implementation design to closeout, with explicit don't-implement boundaries at each phase.
tags:
- architecture
- adr
- design-review
- governance
- workflow
agents:
- hermes-internal
- intelligence
- pirlo
---

# Architecture Workflow — 分阶段架构评审与 ADR 设计

## 使用时机

收到以下类型的任务时加载此 skill：

- 「以 XX 委员会身份评估以下问题」
- 「ADR 草案」
- 「架构评审 / Architecture Review」
- 「Implementation Design（实现设计）」
- 需要产出 ADR 文档、设计文档、或架构决策记录的复杂设计与分析任务

## 核心原则

### 1. 分阶段交付，明确边界

架构工作必须拆分为以下三个阶段，**每个阶段都有严格的交付物和禁止事项**：

```
Phase A: Architecture Review         → 只分析，不设计
Phase B: ADR Draft + Implementation  → 只设计，不实现
          Design
Phase C: Closeout                    → 只收口，不扩展
```

### 2. 用户校正的高频模式

本 skill 开发过程中，用户反复纠正了以下越界行为。**必须遵守：**

| 指令类型 | 越界行为 | 用户反馈 |
|----------|---------|---------|
| 「以委员会身份评估」 | 输出设计方案而非分析 | 「只做分析不实现」 |
| 「ADR 草案 + 设计」 | 开始编码/写文件/生成 patch | 「不准编码」「不准修改文件」「不准进入开发」 |
| 「Implementation Design」 | 写代码/生成 diff | 「不要写代码」「不要生成 Patch」 |
| 设计验收通过后 | 提议扩展 Phase 2 | 「已冻结范围」|

**规则：在没有收到「开始实施」指令之前，所有架构工作止于文档。** 没有「顺便实现一下」——即使方案再明确，也必须等待用户确认「开始实施」才能动手。

### 3. 交付物格式

标准的架构评审交付物结构（来自本 skill 开发过程的实战验证）：

#### Phase A — Architecture Review

```markdown
# Architecture Review Document

## 一、问题矩阵（高频/低频 x 高影响/低影响）

## 二、逐项问题分析（问题 → 根因 → 影响 → 频率 → 象限）

## 三、值得解决吗（投入 vs 收益 + ROI 判断）

## 四、优先级排序（P0-P3）

## 五、风险分析（场景 → 概率 → 影响 → 规避方案）

## 六、ADR 建议（每个待解决问题一个子节）

## 七、总结（优先级路线 + 核心判断）
```

#### Phase B — Implementation Design

```markdown
Closeout Memory Check 后的 ADR 草案结构（已验收）：

## 1. 现有调用链分析（当前执行链 + 插入位置）
## 2. 文件级改动设计（文件清单 + 改动说明 + 兼容性）
## 3. 流程设计（流程图 + 职责 + 执行细节）
## 4. 输出协议设计（统一格式 + 字段定义 + 静默规则）
## 5. Backward Compatibility（不启用时的行为 + 风险 + 降级方案）
## 6. 验收标准（功能性 + 兼容性 + 噪声控制 + 试运行）
```

#### Phase C — Closeout

```markdown
## 收口状态（✅ Accepted + Implemented + Verified）

## 已冻结范围（明确不做什么）

## 后续观察项（Dogfood 期观察维度 + 记录格式）
```

## 检查清单

### Phase A 交付前自检

- [ ] 是否只做了分析，没有设计/实现？
- [ ] 问题分析是否包含了根因，而非表面描述？
- [ ] 优先级排序是否有明确的决策标准（P0-P3）？
- [ ] 风险分析是否包含概率和规避方案？
- [ ] ADR 建议是否只是建议，不是指令？

### Phase B 交付前自检

- [ ] 是否只做了设计文档，没有修改代码/文件/Patch？
- [ ] 改动设计是否标注了兼容性（是否破坏现有行为）？
- [ ] 是否有明确的插入位置（在现有流程的哪一步之后）？
- [ ] 是否有降级/回退方案？
- [ ] 验收标准是否可量化验证？

### Phase C 交付前自检

- [ ] ADR 状态是否已标记（Draft / Accepted / Implemented / Verified）？
- [ ] ADR INDEX.md 是否已追加（首次创建，或追加新行）？
- [ ] 如果涉及项目状态变更（PROJECT.md），是否已在 Memory Check 中输出 `Project State Update Suggested`，且只有用户确认后才执行更新？
- [ ] 冻结范围是否已明确声明？
- [ ] Dogfood 观察项是否已记录？
- [ ] 记忆是否已更新（MEMORY.md 权威索引指针 + 观察项）？

## 技术验证技术：Dry-Run Validation

在设计阶段和实现阶段之间（或实现后、文件操作前），用 dry-run 验证设计逻辑是否正确。这在「不允许修改文件」的阶段尤其重要。

### 何时使用

- 设计方案完成、用户要求验证后再实施时
- 修改涉及多个 skill 的联动逻辑（如 verification-loop + closeout）
- 输出协议有状态分支（4 种 status、去重规则、权限边界）

###  验证流程

1. **选择测试场景** — 覆盖正常路径、边界条件、错误路径、安全边界。典型覆盖：happy path + 不触发条件 + 重复提案 + 越权
2. **从 skill 定义提取预期输出** — 读 trigger signals、不触发条件、输出格式声明的 literal 文本作为预期
3. **逐场景模拟** — 对每个场景，描述任务模拟 → 匹配 skill 触发条件 → 输出预期格式
4. **检查安全边界** — 子 Agent 权限、自动写入禁止、Pending 标记
5. **输出验证表格** — 场景编号 → 预期 → 实际 dry-run 输出 → 是否通过 → 备注

### 验证表格格式

```markdown
| # | 场景 | 预期 | 实际 dry-run 输出 | ✅ 通过 | 备注 |
|---|------|------|------------------|:------:|------|
| 1 | ... | ... | ... | ✅ | ... |
```

### 边界检查（额外验证）

在一个独立表格中覆盖边界条件（如触发阈值、跨 session 去重、并发状态变更等），每个边界附上「是否符合设计」的判断。

### 产出承诺

- dry-run 验证不修改任何文件、不写入 memory、不创建文档
- 验证结果按场景输出，不汇总为单一「通过/不通过」
- 验证后标记版本号（如「1/1 场景通过」或「5/5 场景通过」）

---

## 项目状态（PROJECT.md）变更收口流程

当 feature 实施完成后触发了项目状态变更（如 phase.active 推进、deployment.target 变更），按以下流程执行 Closeout Memory Check 中的 `Project State Update Suggested` 分支。

### 何时触发

- 用户确认更新 PROJECT.md 中的某个 state key
- 或 Memory Check 在 dogfood 期输出了 `Project State Update Suggested` 且用户确认

### 更新规则（ADD-only）

1. **禁止覆盖** — 不可以直接修改现有条目的 value 字段
2. **旧条目标记 superseded** — 找到旧 key 所在行，将其 status 列从 `current` 改为 `superseded`
3. **新条目 ADD** — 在表格末尾追加新行，status = `current`
4. **source 规则** — CLI 命令用 `cli:<command>`，会话确认用 `session-<date>/<phase>`，ADR 用 `ADR-<slug>`
5. **recent 快照区** — 旧条目直接移除（不标记 superseded），只保留最近 3 条

### 示例（实战验证）

```
旧: | phase.active | v0.1 — 最小闭环 | ADR-codex-like-agent-workbench | 2026-06-03 | current |
新: | phase.active | v0.1 — 最小闭环 | ADR-codex-like-agent-workbench | 2026-06-03 | superseded |
新: | phase.active | v0.1 — dogfood 观察期 | session-2026-06-08/project-context-phase2-closeout | 2026-06-08 | current |
```

### 不做的事

- 不自动写 PROJECT.md（必须等待 `Pending: user confirmation required` 被解除）
- 不改子 Agent 权限模型
- 不新增依赖或 CLI 工具

## Pitfalls

**场景**：设计方案非常明确，觉得「就差一行命令/一个文件了，顺手写了算了」。
**后果**：用户反馈「只做设计不实现」。会打断信任。
**规避**：严格遵守 Phase 边界。即使方案 100% 明确，也在用户说「开始实施」之后才动手。

### 2. 「讨论已定事项」陷阱

**场景**：用户确认了 A 方案，但在 B 的讨论中又回头重新讨论 A。
**后果**：用户反馈「确认过的决策不重新讨论」。
**规避**：Phase A 交付时标注「已确认」和「未确认」事项。后面的阶段只推进未确认项。

### 3. 「输出太粗」陷阱

**场景**：方案只有方向描述，没有具体步骤、文件清单、验收标准。
**后果**：用户反馈「太粗了，需要细化到可交接执行」。
**规避**：每一阶段的交付物必须包含编号子任务、文件清单、验收条件、回退方案。拿不准时按「能直接交接给另一个独立执行者」的颗粒度写。

### 4. 「越界写文件」陷阱

**场景**：设计阶段觉得「建个空文件/更新索引没什么」，顺手写了文件。
**后果**：违反「只设计不实现」的约定。
**规避**：任何文件操作（写文件、创建目录、patch）都必须在明确的「实现阶段」授权下执行。设计阶段的输出只停留在对话中，不落地。

## 参考

- 本 skill 产出自 ADR-XXX-001（Closeout Memory Check）的全生命周期设计过程
- 实战验证：用户校正了 4 次「不越界实现」后，后续回合完全对齐
- **参考资料（本 skill 目录下）：**
  - `references/dry-run-validation-example-closeout-memory-check.md` — 5 场景 dry-run 验证实战，可作其他 feature 验证模板
  - `references/project-state-addonly-closeout-example.md` — PROJECT.md ADD-only 状态变更实战
