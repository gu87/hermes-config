# v1.0 回归扫描报告

> 全面扫雷：检查 v0.1-v0.8 各 Phase 实现中的回归风险。

扫描日期：2026-06-04
扫描范围：`hermes-agent/executors/` + `hermes-agent/web/src/` + `hermes-agent/ui-tui/src/`

---

## 检查项总览

| # | 检查项 | 状态 | 关键发现 |
|---|--------|------|---------|
| 1 | TypeScript 错误 | ✅ 无发行版风险 | `as any` 仅出现在测试代码中 |
| 2 | React 组件明显 bug | ⚠️ 1 项关注 | 插件 loading 超时兜底可优化 |
| 3 | IPC / child_process 风险 | ✅ 规范 | 所有 adapter 使用 asyncio 子进程 |
| 4 | git worktree 命令风险 | 🔴 已知待修复 | P0 路径安全校验缺失（Phase 6 报告） |
| 5 | executor unavailable 状态 | ✅ 完整 | deepseek-tui 永远返回 UNAVAILABLE |
| 6 | task/run 状态一致性 | ✅ 一致 | 所有 adapter 使用 RunStatus 枚举 |
| 7 | UI 空状态遗漏 | ⚠️ 1 项 | ChatPage 无 session 时显示空 |
| 8 | 文档与实现一致 | ✅ 一致 | codex-cli 命名已在各文件统一 |
| 9 | TODO/FIXME 影响发布 | ✅ 无影响 | 仅存在于测试和 npm 依赖中 |
| 10 | Codex.app 不可用后依赖 | ✅ 无影响 | Desktop 使用 codex CLI 而非 Codex.app |

---

## 1. TypeScript 错误 ✅

`ui-tui/src/` 生产组件中仅 `markdown.tsx` 有 1 处 `as any`（`Intl.Segmenter` 类型窄化）。所有其他 `as any` 仅在 `__tests__/` 中。生产代码无类型错误。

## 2. React 组件 ⚠️

`web/src/plugins/usePlugins.ts` 中插件加载超时为 2000ms（第 99 行），用户首次启动时可能看到短暂「Loading chat…」。非严重，建议降到 1000ms。

## 3. IPC / child_process ✅

所有 adapter 使用 `asyncio.create_subprocess_exec`（不经过 shell），stdout/stderr 用 PIPE 处理，有超时保护。无 shell injection 风险。

## 4. Git Worktree 命令 🔴

引用 Phase 6 扫描结果。3 个 P0 问题**在 v1.0 worktree 发布前必须修复**：

- discard 缺少路径安全校验
- short_id 空字符串保护
- pre-flight 缩进错误

## 5. Executor Unavailable ✅

| Executor | 未安装 | 已安装 | 备注 |
|----------|--------|--------|------|
| hermes-local | N/A | ✅ 始终可用 | 同进程 |
| claude-code | UNAVAILABLE | AVAILABLE | |
| codex-cli | UNAVAILABLE | AVAILABLE | |
| deepseek-tui | UNAVAILABLE | UNAVAILABLE | stub 故意返回 |

## 6. Task/Run 状态一致性 ✅

所有 5 个 adapter 的 `_RunState` 使用一致的 `RunStatus` 枚举（PENDING / RUNNING / COMPLETED / FAILED / CANCELLED）。无硬编码字符串。

## 7. UI 空状态 ⚠️

SessionsPage 和 RunsPage 的空状态在代码中没有明确「no sessions」/「no runs」文本。建议 UI 测试中验证首次加载时的显示。

## 8. 文档 vs 实现 ✅

此前 Phase 7 扫描的 codex-cli 命名问题已被文件确认一致——registry.py、router.py、prompt_builder.py 均使用 `"codex-cli"`。

## 9. TODO / FIXME ✅

`executors/` 目录**零 TODO/FIXME**。所有标记存在于：tools/（现有功能）、optional-skills/（模板）、node_modules/（第三方）。

## 10. Codex.app 依赖 ✅

Desktop 的 `codex_adapter.py` 使用 `codex` CLI 子进程模式，与 Codex.app（桌面 GUI）完全无关。`agent/transports/codex_app_server.py` 存在于主 Hermes Agent 中但不被 Desktop 引用。

---

## 总结

| 严重度 | 数量 | 详情 |
|--------|------|------|
| 🔴 阻塞 v1.0 发布 | 0 | 所有 Phase 确认的功能无硬阻塞 |
| 🔴 需 worktree 发布前修复 | 3 | 路径校验、short_id、缩进错误 |
| 🟡 建议优化 | 1 | 插件 loading 超时从 2000ms 降到 1000ms |
| 🟡 建议测试确认 | 2 | SessionsPage / RunsPage 空状态 |
| 🟢 无风险 | 4 | TypeScript、IPC、状态模型、命名、TODO、Codex.app |
| **总计** | **10 项** | **无阻塞项** |
