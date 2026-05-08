# Hermes 2.8 Upgrade Instruction

当前 Hermes 正在升级到 2.8，升级方向是 Harness Engineering。

请优先阅读以下两个文档：

1. `docs/plans/hermes-2.8-harness-engineering-plan.md`
2. `docs/plans/hermes-2.8-claude-code-task-brief.md`

## 执行原则

- 严格按任务书执行，不要自行跳 Sprint。
- 先完成 Sprint 0 Repository Audit。
- 每个 Sprint 完成后，必须生成阶段总结文档。
- 阶段总结文档统一放在：`docs/stages/sprint-xx/`
- 每个 Sprint 完成后，必须执行 Git commit。
- Event Log 必须从 Sprint 1 开始实现。
- 不要一次性大重构。
- 不要只改代码不写文档。
- 不要只写文档不改工程结构。
- 如果发现任务书与当前仓库结构冲突，优先适配当前仓库，并在阶段总结中说明原因。