# Hermes 统一 Task/Run 合同 — Phase 1-6 总结

> 日期：2026-06-11
> 状态：**Phase 1-6 完成**

---

## 1. 提交清单 (19 commits, 3 repos)

| Phase | .hermes | hermes-agent | hermes-desktop |
|-------|---------|-------------|----------------|
| 1A-D | 4 | — | — |
| 2A-C | 3 | `80d5b9db2` | — |
| 3A-C | 3 | — | — |
| 4A-C | 3 | — | — |
| 5A-C | 3 | — | — |
| 6A-B | 1 | — | `c27dae4` |
| **Total** | **17** | **1** | **1** |

---

## 2. 能力矩阵

| 能力 | Pipeline | Delegate | Kanban | Control | Fleet | Desktop |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 只读投影 | ✅ | ✅ | ✅ | — | — | — |
| Journal | ✅ | ✅ | ✅ | ✅ | — | — |
| 确定性 ID | ✅ | ✅ | ✅ | ✅ | — | — |
| SQLite mode=ro | — | — | ✅ | — | — | — |
| 控制命令 | — | — | ✅ | ✅ | — | — |
| CAS 并发 | — | — | ✅ | ✅ | — | — |
| FleetSnapshot | — | — | — | — | ✅ | — |
| Fleet UI | — | — | — | — | — | ✅ |

---

## 3. 测试 (1,283 total)

```
Desktop: 844 tests (73 files)
Backend: 439 tests (304 projection + 135 delegate)
Phase 1: SHA 508b3c70..., 747 records, 14/14 acceptance
```

---

## 4. 安全边界

- IPC 无参数 + symlink 防护 + 1MB limit
- 错误净化：不泄露路径/堆栈/文件内容
- Renderer 无法读取任意文件
- Desktop 不重新计算 Fleet 状态
- FleetSnapshot 是可删除重建的派生视图

---

## 5. 已知限制

- GUI smoke 未验收（需 Desktop 运行环境）
- Fleet builder 未集成 daemon
- Delegate model_ref 非唯一 → unassigned
- Pipeline/Delegate 控制推迟
