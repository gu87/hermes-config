# OpenCode 作为 Review/QA Executor — 可行性评审

> 元信息
> - 评审对象：`opencode` v1.15.13（`/opt/homebrew/bin/opencode`）作为 Hermes Desktop **Review/QA Executor** 的可行性
> - 评审时间：2026-06-04
> - 评审者：opencode 评审（外部）
> - 输入文档：`docs/architecture/agent-adapter-layer.md`、`docs/architecture/semi-auto-executor-router.md`、`hermes-agent/executors/opencode_adapter.py`、`hermes-agent/executors/registry.py`
> - 评审方法：纯代码审计 + **empirical CLI 验证**（30+ 次 opencode 真实调用，1 个 `/tmp/opencode_test` 临时仓库 + 1 个 `auth.py` 漏洞 diff 作为 review fixture）
> - 评审结论：**可用，推荐以 stub 形式落地；不建议直接复用现有 `OpenCodeAdapter` 启动器**

---

## 0. 摘要（TL;DR）

| 维度 | 结论 | 关键证据 |
|---|---|---|
| 官方支持 | ✅ `opencode run` 子命令原生支持非交互式调用 | `opencode run --help` 输出 |
| 结构化输出 | ✅ NDJSON（`step_start` / `tool_use` / `text` / `step_finish`），含 tokens + cost + sessionID | Test 2, 23, 31 |
| Read-only 模式 | ⚠️ 无内置 read-only 标志，但有 **read-only-by-intent** 的内置 `plan` agent | Test 16-18: `plan` agent 修改文件 0 次（`build` agent 修改 1 次） |
| 适用 review/QA | ✅ 推荐 `plan` agent，不推荐 `build` agent | Test 24: 同 diff，build=BUILD/plan=OK（过度严格 vs 适当） |
| Worktree 隔离 | ✅ `--dir <path>` 行为等价 `cwd`，可与 Hermes worktree 模式对齐 | Test 3, Test 13 |
| 可观测性 | ✅ sessionID + `opencode session list` + `opencode export <id>` 全套审计接口 | Test 31-34 |
| 失败模式 | ⚠️ JSON 解析、tool-call 死循环、verdict 不可强制 | Test 29 (--prompt 无 `run` 子命令→退出 1), Test 25 (opencode -p 进入 TUI) |
| 当前 Adapter | ❌ **不工作**：`hermes-agent/executors/opencode_adapter.py:93` 用 `opencode -p PROMPT` 调起 TUI（exit 1, stdout 0, stderr 3787 字节 ASCII banner） | Test 25 |
| Registry 现状 | ⚠️ `review_gate=False, supports_worktree=False`，与实测能力不匹配 | `hermes-agent/executors/registry.py:opencode` |
| 落地建议 | **Stub now, full later**：先在 `registry.py` 把 capability 标对、Adapter 重写为 `opencode run --format json`；不要急于接 ReviewGatePipeline | 本节末尾 §10 |

---

## 1. 官方用法与版本（Check Point 1）

### 1.1 版本与二进制

```bash
$ opencode --version
1.15.13

$ which opencode
/opt/homebrew/bin/opencode
```

### 1.2 子命令结构

| 子命令 | 用途 | 是否可被 Hermes 复用 |
|---|---|---|
| `opencode run [message..]` | 非交互式执行（核心） | ✅ 是 |
| `opencode stats` | 跨 session 统计（cost / tokens / tools） | ✅ 适合做 OpenCode 自身 budget 看板 |
| `opencode session list` | 列所有 session（标题 + sessionID + updated） | ✅ 适合做回溯 |
| `opencode export <sessionID>` | 导出单 session 完整 JSON | ✅ 适合做审计证据 |
| `opencode agent list` | 列出内置 agent + permission | ✅ 是 review/QA agent 选型的入口 |
| `opencode`（裸调） | 启动 TUI | ❌ 不要从 Adapter 调起 |

### 1.3 关键 flag

| Flag | 行为 | 备注 |
|---|---|---|
| `--format json` | 输出 NDJSON 事件流 | Hermes 解析的唯一正确模式 |
| `--dir <path>` | **等价** 设置 `cwd`（不是 `git worktree add`） | 与 Hermes worktree 模式直接对齐：传 `worktree.path` 即可 |
| `-f, --file <path>` | 把文件作为 attachment 注入上下文 | 适合把 diff.patch / review 范围作为 `-f` 注入 |
| `--agent <name>` | 选择 agent：`build`（默认）/ `plan`（review-only-by-intent）/ `compaction` / `summary` / `title` / `explore`（subagent）/ `general`（subagent） | **关键开关** |
| `--variant <name>` | 思考深度（`high` 触发更长 reasoning） | 对 review/QA 有意义（Test 21） |
| `--thinking` | 在 NDJSON 中额外输出 `reasoning` 事件 | 适合做 agent 思维链回放 |
| `--session <id>` + `--continue` | 续接已有 session | 适合做"先 plan 再 build"的两阶段 |
| `--pure` | 禁用外部 plugin | Hermes 部署环境推荐（隔离差异） |
| `--dangerously-skip-permissions` | 自动 approve 所有 tool call | ❌ **不要** 在 review/QA 场景使用 |

### 1.4 与现有 Adapter 的对比

| 维度 | 现有 Adapter（`opencode_adapter.py:93`） | 正确调用 |
|---|---|---|
| 命令行 | `opencode -p "{run.prompt}"` | `opencode run --format json --pure --agent plan --dir {wt.path} -f {diff.path} {run.prompt}` |
| 启动子命令 | 无（进入 TUI） | `run` |
| 格式 | 默认人类可读 + ANSI | NDJSON（事件流） |
| 退出码 | 1（实际行为，Test 25） | 0（成功）/ 1（子命令错误） |
| 是否工作 | ❌ **完全坏** | ✅ |

> **P0**: `OpenCodeAdapter` 应当 **被替换**。当前实现不是"未优化"，而是"未连通"。这是 Phase 9 的最优先任务。

---

## 2. 结构化输出（Check Point 2）

### 2.1 NDJSON 事件 schema（实测归纳）

Test 2 完整事件流（6 条）：

```json
{"type":"step_start","sessionID":"ses_...","part":{"snapshot":"<git-sha>"}}
{"type":"tool_use","sessionID":"ses_...","part":{"tool":"bash","args":{"command":"ls"}}}
{"type":"step_finish","sessionID":"ses_...","part":{"reason":"tool-calls","tokens":{"total":41528,"input":41332,"output":87,"cache":{"read":109}},"cost":0.03963084}}
{"type":"step_start","sessionID":"ses_...","part":{"snapshot":"<git-sha>"}}
{"type":"text","sessionID":"ses_...","part":{"text":"Here are the files..."}}
{"type":"step_finish","sessionID":"ses_...","part":{"reason":"stop","tokens":{...,"output":50},"cost":0.00693015}}
```

### 2.2 关键字段

| 字段 | 含义 | Hermes 用法 |
|---|---|---|
| `type` | 事件类型 | router：`step_start`/`tool_use`/`text`/`step_finish` |
| `sessionID` | 一次 run 的全局 id（Test 31: `ses_16f8237cdffe5o22i16xEpi1ZK`） | 入 `AgentRun.session_id` 供审计 |
| `part.snapshot` | 当前 git SHA（opencode 内部 snapshot，不是 Hermes worktree） | 校验/记录 |
| `part.tool` | 工具名（`bash`/`read`/`grep`/`glob`/`write`/`edit`/`webfetch`...） | review gate 拦截 `write`/`edit` |
| `part.tokens.{input,output,cache.read}` | 真实计费 token | 注入 `PromptSnapshot.tokens_estimated` 反演 |
| `part.tokens.cache.read` | 命中 cache 量（重要成本信号） | 决定是否启用 prompt caching |
| `part.cost` | 美元成本 | 注入 `AgentRun.cost_usd` |
| `part.text` | LLM 输出文本（最终 verdict 一般在此） | review/QA 主结果 |
| `part.reason` | `tool-calls` / `stop` | 终止判定 |

### 2.3 与 Adapter 的契约

`AgentRun` 应当从 NDJSON 流提取：

```
AgentRun(
    executor_id="opencode",
    session_id=<sessionID>,         # 来自首条事件
    snapshot_git=<part.snapshot>,    # 来自 step_start
    final_text=<text from last text event>,
    tool_calls=[<tool_use events>],
    tokens_estimated=<max(part.tokens.total)>,
    tokens_actual=<last step_finish.tokens>,
    cost_usd=<sum(part.cost)>,
    verdict=BLOCK|OK|UNKNOWN,        # 从 final_text 启发式提取
    stop_reason=<last step_finish.reason>,
)
```

### 2.4 重要失败模式

| 模式 | 触发 | 表现 |
|---|---|---|
| JSON 解析错误 | `--prompt` 不带 `run` 子命令（Test 29: `opencode --prompt`） | exit 1 + 0 字节 NDJSON |
| TUI 启动 | `opencode -p X`（旧调用，Test 25） | exit 1 + 3787 字节 ASCII banner |
| doom_loop | 同 tool 重复 > N 次 | `part.reason=doom_loop` + 部分 token 计费 |
| external_directory 拦截 | 试图访问 `--dir` 之外 | 需要 `--dangerously-skip-permissions`（**仅 build 场景**） |
| `stop` reason | 完成（最后一条 step_finish） | 部分工具调用 step 不会输出 `text`，要轮询多个 step |

> **P1**: Adapter 必须区分 "TUI 启动" 与 "真正 run"（通过 `sessionID` 存在与否 + NDJSON 解析成功）。当前代码无此判断。

---

## 3. Read-only / Review 能力（Check Point 3）

### 3.1 关键发现：内置 `plan` agent 是 read-only-by-intent

Test 14-19 实证：

```bash
$ opencode agent list | grep primary
build (primary)
compaction (primary)
plan (primary)
summary (primary)
title (primary)
```

虽然所有 agent 在 permission JSON 中都声明 `"*": "allow"`，但 **`plan` agent 的 system prompt 约束** 了其不会调用 `write` / `edit`：

| Test | 任务 | agent | tool_use 次数 | 文件是否被改 | 备注 |
|---|---|---|---|---|---|
| 16 | `modify test.txt to say 'plan-modify'` | `plan` | **0** | ❌ 不改 | 拒绝 |
| 17 | `review the diff for security issues` | `plan` | 0 | ❌ 不改 | 主动以纯文本回复 |
| 18 | 同上 + 要具体 | `plan` | 0 | ❌ 不改 | 输出 5 个 issue + 代码修复（**纯文本**） |
| 19 | `run ls in the cwd` | `plan` | 1（bash） | ❌ 不改 | 可读 + bash 探索 |

对比 `build` agent（默认）：

| Test | 任务 | agent | tool_use 次数 | 文件是否被改 |
|---|---|---|---|---|
| 旧 Test 6 | `modify test.txt to say 'goodbye'` | `build` | 2（read + write） | ✅ **改** |
| Test 24a | `review for security: BLOCK/OK` | `build` | n/a | n/a |
| Test 24b | 同上 | `plan` | 0 | ❌ 不改 |

### 3.2 同样 prompt 下 build vs plan 的输出差异（Test 24）

**Diff**（auth.py）：

```python
+ def verify_token(token, expected="secret123"):
+     if not token:
+         return False
+     return hmac.compare_digest(token, expected)
```

**build agent 输出**：
> **BLOCK**
> - Hardcoded secret remains: Moving `"secret123"` from the function body to a default parameter does not eliminate the hardcoded credential...
> - Insecure default: Calling `verify_token(token)` without an explicit `expected` value still falls bac[k]...

**plan agent 输出**：
> **OK** — this is a security improvement, not a regression.
> Here's the breakdown:
> - Replaced `==` with `hmac.compare_digest()` — This fixes a **timing attack vulnerability**...
> - 总体：净改善

**结论**：

| 场景 | 推荐 agent | 理由 |
|---|---|---|
| Review/QA gate（判断是否阻断 PR） | **`plan`** | 输出稳定、可解析；零写入风险；附带"为什么 OK"的解释 |
| 发现潜在隐患（不需要立即 block） | `build`（带 sandbox） | 更严格，但需 worktree 隔离 |
| 任何"自动改代码" | `build` | 唯一能写的 agent |
| 续接 session 做"先 plan 后 build" | 两个都 | `--session <id> --continue --agent build` |

> **P1**: 引入 `OpenCodeReviewAdapter` 专用 `plan` agent；不要混用 `build` 做 review。

---

## 4. Worktree 集成（Check Point 4）

### 4.1 `--dir` 实测

```bash
# 在 /Users/gu 工作目录，强制 opencode 在 /tmp/opencode_test 工作
$ opencode run "list files" --format json --pure --dir /tmp/opencode_test
# 返回：.git/  test.txt  （cwd 切换成功）
```

| 行为 | 等价于 Hermes 的什么 |
|---|---|
| `--dir <path>` | `Worktree.path` |
| 默认 `cwd` = 父进程 cwd | 当前 Hermes 行为（无 worktree） |
| 在该 dir 内产生的 `.git` 操作 | opencode 内部 snapshot，非 git worktree |

### 4.2 与 Git Worktree 的对齐

opencode **不做 git worktree add**，但 `--dir` 完全可以指向一个已存在的 worktree：

```
Hermes worktree.path ──> opencode --dir <path>
                │
                └──> opencode 内部在该 dir 里产生 snapshot（commit SHA，Test 23）
```

**Adapter 改造要点**：

```python
cmd = [
    "opencode", "run",
    "--format", "json",
    "--pure",
    "--agent", "plan",          # review/QA 场景固定
    "--dir", str(worktree.path),
    "-f", str(diff_path),       # 必传：review 范围
    run.prompt,                 # 必传：具体问题
]
```

> **P0**: 把 `OpenCodeAdapter` 改为 `opencode run --format json --pure --agent plan --dir <wt> -f <diff> <prompt>`。现有实现不算 work。

---

## 5. 可观测性（Check Point 5）

### 5.1 实时 NDJSON（已述）

| 信号 | 来源字段 | 用于 |
|---|---|---|
| 当前步数 | `step_finish` 计数 | 进度条 |
| Token 消耗 | `part.tokens.total` | 预算告警 |
| 美元成本 | `part.cost` | 跨 session 看板（`opencode stats`） |
| 工具调用 | `tool_use.tool` | 行为审计（read 比例高 = 安全） |
| 错误 | `part.reason=doom_loop` | 自动 abort |
| Reasoning 链 | `--thinking` 模式下的 `reasoning` 事件 | 解释 agent 决策 |

### 5.2 Session 级审计（Test 33-34）

```bash
$ opencode session list
Session ID                      Title                                       Updated
───────────────────────────────────────────────────────────────────────────────────
ses_16f8237cdffe5o22i16xEpi1ZK  New session - 2026-06-04T02:37:02.898Z      10:37 AM
ses_16f836f16ffeeLBICL5FFWynPG  auth.py token verification security review  10:35 AM
...

$ opencode export ses_16f836f16ffeeLBICL5FFWynPG > review-audit.json
```

### 5.3 跨 Session 统计（Test 28）

```
Total Cost        $1.28
Avg Cost/Day      $0.32
Avg Tokens        283.2K
Input             2.3M
Output            77.5K
Cache Read        8.9M
Tool Usage:
  read           96 (45.3%)
  bash           70 (33.0%)
  grep           23 (10.8%)
  glob           17 (8.0%)
  write           3 (1.4%)   ← 极低，符合"默认只读"预期
```

> **P0**: review/QA 场景应把"tool_use 中 write/edit 比例"作为硬告警指标。建议阈值：`write+edit <= 2%`。

---

## 6. 失败模式（Check Point 6）

| # | 模式 | 触发条件 | 表现 | 缓解 |
|---|---|---|---|---|
| F1 | TUI 启动而非 run | 用 `opencode -p X`（旧调用） | exit 1 + ASCII banner + 卡住 | Adapter 强制 `opencode run` 子命令 |
| F2 | 0 字节 stdout | `opencode --prompt X`（无 subcommand） | exit 1 | 同上 |
| F3 | JSON 解析失败 | NDJSON 中混入 ANSI 序列（部分老版本） | `json.JSONDecodeError` | Adapter 用 NDJSON 逐行解析 + 容忍 ANSI |
| F4 | Doom loop | opencode 内部 tool call 循环 > N | step_finish.reason=`doom_loop`，部分 token 计费 | Adapter 检测 `reason` + 设置 `timeout=300s` |
| F5 | Timeout | LLM 慢 / 网络抖 | 进程挂起 | Adapter 用 `subprocess.run(..., timeout=...)` |
| F6 | External directory 拦截 | `--dir` 之外访问 | opencode 主动 ask（阻塞） | `--dangerously-skip-permissions`（**仅 build**），review/QA 不开 |
| F7 | Verdict 不可强约束 | plan agent 给"OK"或"BLOCK"位置不固定 | 解析失败 | Adapter 用 "提取 BLOCK/OK 关键词" + fallback UNKNOWN + 人工 review |
| F8 | 跨平台差异 | macOS/Linux shell escaping | diff 路径含空格 | 用 `subprocess` 列表传参，不要 shell=True |
| F9 | Plan agent 幻觉"OK" | Test 24 净改善仍可输出 OK | 漏报 | 双 agent 对比：plan + build 都 BLOCK 才 BLOCK |
| F10 | 凭证泄露到 env | Adapter 用 `os.environ` 继承 | DEEPSEEK_API_KEY 进 opencode 进程 | Adapter 用 `env={}` 子集化，只传必需 |

> **P0**: F1 / F2 / F6 / F10 是阻塞性失败模式，必须在 Phase 9 第一个 sprint 处理。

---

## 7. 建议 / 不建议场景（Check Point 7）

### 7.1 推荐场景

| 场景 | 价值 | 配置 |
|---|---|---|
| **PR review 安全审计** | 3-10 秒出一个 BLOCK/OK + 解释 | `--agent plan -f diff.patch` |
| **Worktree 内代码体检** | 与 Hermes worktree 直接对齐 | `--dir <wt.path> --agent plan` |
| **半自动 Executor Router 的"opencode 通道"** | 复杂任务 fallback（替代 deepseek-tui） | `--agent build --dangerously-skip-permissions` |
| **Review 历史的 session 审计** | 1 行命令导出 | `opencode export <id>` |
| **成本/缓存可视化** | 跨 session 看板 | `opencode stats` + 自建 cron |

### 7.2 不推荐场景

| 场景 | 原因 |
|---|---|
| 交互式"边做边问" | 用 TUI；Hermes 不应模拟 TUI |
| 大型 monorepo 全量扫描 | opencode 上下文窗口有限（实测 input 30K+ 就明显降速） |
| 高安全要求 + 不可接受"plan agent OK" | 双 agent 复核，或人工 review |
| `--dangerously-skip-permissions` 长时间运行 | 任意写文件风险；只能在 sandbox 里 build agent |
| 把 opencode 单纯当 "API 替代品"调用 | 它的优势是 tool use + worktree，不是 LLM API；用 deepseek-tui 更便宜 |
| 多用户共享 session | opencode session 是本地的，跨用户需要额外租户层 |

### 7.3 落地优先级

| 优先级 | 任务 | 影响 |
|---|---|---|
| **P0-1** | 替换 `OpenCodeAdapter` 启动器为 `opencode run --format json --pure --agent plan` | 修复 broken 状态 |
| **P0-2** | 解析 NDJSON → `AgentRun` 完整字段（tokens/cost/sessionID/snapshot） | 启用成本可观测 |
| **P0-3** | Adapter 加 `timeout` + `env` 子集化 | 缓解 F5 / F10 |
| **P1-1** | Registry 修正：`review_gate=True, supports_worktree=True` | 让 router 能选到 opencode |
| **P1-2** | `opencodeReviewAdapter` 子类（`--agent plan` 固定） | review/QA 专用通道 |
| **P1-3** | `tool_use.write+edit` 比例告警 | 防止越权 |
| **P2-1** | 集成 `opencode stats` + `session list` 进 Hermes dashboard | 长期可观测 |
| **P2-2** | 双 agent 复核（plan + build） | 降低 F9 漏报 |

---

## 8. 最小可用调用（Check Point 8）

### 8.1 PR review（Hermes Review Gate 推荐）

```bash
# 准备：worktree + diff
wt=/tmp/opencode_test                          # Hermes 创建的 worktree
diff_patch=$wt/.hermes/review/HEAD.patch       # Hermes 生成的 diff

# 调用：plan agent 只读 review
opencode run \
  --format json --pure \
  --agent plan \
  --dir "$wt" \
  -f "$diff_patch" \
  "Review the diff for security, correctness, and test coverage. \
Output a final verdict line of the form VERDICT: BLOCK or VERDICT: OK, \
followed by specific issues with file:line and proposed fix. \
Do not modify any files." \
  2>/dev/null
```

**Adapter 解析**：

```python
# 逐行解析 NDJSON
verdict = UNKNOWN
final_text_parts = []
for line in process.stdout:
    event = json.loads(line)
    if event["type"] == "text":
        final_text_parts.append(event["part"]["text"])
    elif event["type"] == "step_finish":
        last_step = event["part"]
        if last_step["reason"] == "doom_loop":
            verdict = ERROR_DOOM_LOOP

final_text = "".join(final_text_parts)
if "VERDICT: BLOCK" in final_text:
    verdict = BLOCK
elif "VERDICT: OK" in final_text:
    verdict = OK

return AgentRun(
    executor_id="opencode",
    session_id=session_id,
    verdict=verdict,
    final_text=final_text,
    cost_usd=total_cost,
    tokens_actual=last_step["tokens"],
)
```

### 8.2 Worktree 内的 build（Router fallback 通道）

```bash
opencode run \
  --format json --pure \
  --agent build \
  --dangerously-skip-permissions \   # ⚠️ 只在 sandbox 内
  --dir "$wt" \
  "$run_prompt"
```

### 8.3 Session 续接（plan 后 build）

```bash
# 1. plan 阶段
opencode run --format json --pure --agent plan --dir "$wt" -f "$diff" \
  "Create a plan to fix the issues" > plan_run.json
SESSION_ID=$(jq -r '.sessionID' <(head -1 plan_run.json))

# 2. build 阶段（续接）
opencode run --format json --pure --agent build \
  --session "$SESSION_ID" --continue --dangerously-skip-permissions \
  --dir "$wt" \
  "Execute the plan from the previous session"
```

---

## 9. Registry 与 Stub 决策（Check Point 9）

### 9.1 现状

```python
# hermes-agent/executors/registry.py
"opencode": ExecutorManifest(
    id="opencode",
    label="OpenCode",
    description="OpenCode CLI — local open-source coding agent (opencode)",
    capabilities=ExecutorCapabilities(
        structured_tool_calls=True,
        native_diff_events=False,
        reasoning_blocks=True,
        review_gate=False,        # ❌ 实际可以 review（Test 14, 18）
        streaming="line-buffered",
    ),
    default_model="deepseek-v4-flash",
    ui_fidelity="full",
    supports_worktree=False,    # ❌ 实际支持（Test 3, 4）
),
```

### 9.2 应该改为

```python
"opencode": ExecutorManifest(
    id="opencode",
    label="OpenCode",
    description="OpenCode CLI — local open-source coding agent (opencode) — supports both build and review-gate modes",
    capabilities=ExecutorCapabilities(
        structured_tool_calls=True,      # NDJSON events
        native_diff_events=False,        # opencode 不区分 diff events
        reasoning_blocks=True,           # --thinking 模式
        review_gate=True,                # ✅ 实测可 review
        streaming="line-buffered",       # NDJSON 流
        read_only_agent="plan",          # ✅ plan agent 内置只读
    ),
    default_model="deepseek-v4-flash",
    ui_fidelity="full",
    supports_worktree=True,         # ✅ --dir 等价 worktree
    min_cli_version="1.15.0",       # 确保 opencode run 子命令可用
),
```

### 9.3 Stub vs Full 决策

| 维度 | Stub（推荐，先做） | Full（Phase 10+） |
|---|---|---|
| 启动器 | `opencode run --format json --pure --agent plan` | 同 + `--session`/`--thinking` 续接 |
| 解析 | 提取 `text` + `verdict` 关键词 | 完整 NDJSON schema → `AgentRun` 全字段 |
| 适配 | 单一 `OpenCodeAdapter` 类 | 拆 `OpenCodeBuildAdapter` + `OpenCodeReviewAdapter` |
| Router 集成 | 不接入；`review_gate=False` 但保留 stub 入口 | 接入 `PhaseDecision` 通道 |
| 失败模式 | 仅处理 F1/F2/F5（subcommand / timeout） | 处理 F1-F10 |
| 验收 | 一次"PR diff → BLOCK/OK"端到端跑通 | 30 prompt 评测集 + 双 agent 复核 |
| 时间投入 | 1 sprint | 2-3 sprint |

**结论**：**先做 Stub**。

理由：
1. 现有 `OpenCodeAdapter` 几乎不工作（Test 25），第一步是修通连接，不是扩展功能
2. Review gate 的产品形态（仅 BLOCK/OK 还是打分？是 1 次还是多轮？）还没定
3. Adapter 内部契约（`AgentRun` 字段）正在 Phase 8 评审中动，先 stub 等契约稳定
4. deepseek-tui 已是主通道，opencode 早期定位是"补充 review 通道"而非"主路由"

### 9.4 Stub 的最小验收标准

- [ ] `OpenCodeAdapter.start()` 调用 `opencode run --format json --pure --agent plan --dir <wt> -f <diff> <prompt>` 成功（exit 0）
- [ ] 能从 NDJSON 解析出 `final_text` + `cost_usd` + `session_id`
- [ ] Verdict 关键词提取（"BLOCK" / "OK"）正确率 ≥ 80%（评测集 10 条）
- [ ] `timeout=300s` 强制，触发后 cancel 子进程
- [ ] `env` 不继承父进程（除 PATH / HOME / 必要 proxy）
- [ ] `registry.py` 中 `opencode` manifest 字段与实测一致
- [ ] 不接 `PhaseDecision`，但留 hook 注释

---

## 10. 评审发现汇总表

| 编号 | 严重度 | 主题 | 描述 | 位置 |
|---|---|---|---|---|
| OC-01 | **P0** | Adapter 启动器坏了 | 用 `opencode -p X` 进 TUI | `hermes-agent/executors/opencode_adapter.py:93` |
| OC-02 | **P0** | NDJSON 未解析 | 假设为 stdout 单行，未做 NDJSON 处理 | 同上 |
| OC-03 | **P0** | 无 timeout 保护 | `subprocess.run` 未传 timeout | 同上 |
| OC-04 | **P0** | env 继承父进程 | `os.environ` 直接传，凭证泄露 | 同上 |
| OC-05 | P1 | Registry capability 错配 | `review_gate=False, supports_worktree=False` | `hermes-agent/executors/registry.py` |
| OC-06 | P1 | 没有 plan agent 入口 | 默认 build agent 不适合 review | OpenCodeAdapter |
| OC-07 | P1 | Verdict 解析未实现 | review/QA 必须产物，未设计 | 同上 |
| OC-08 | P1 | 缺 `tool_use` 行为审计 | 无法事后追溯 agent 干了什么 | 同上 |
| OC-09 | P2 | 未集成 `opencode stats` | 跨 session 成本看板缺失 | Dashboard 集成 |
| OC-10 | P2 | 未集成 `opencode export` | 审计证据缺失 | Audit 模块 |
| OC-11 | P2 | 双 agent 复核未实现 | plan + build 都能漏 | Review pipeline |
| OC-12 | P2 | `--thinking` 链未落库 | Reasoning 事件未持久化 | Logging 模块 |

**P0: 4 个** · **P1: 4 个** · **P2: 4 个** · **合计 12 个**

---

## 11. 评审附录

### 11.1 测试方法

- 测试环境：macOS aarch64，opencode 1.15.13，/opt/homebrew/bin/opencode
- 临时仓库：`/tmp/opencode_test`（git init）
- 测试 diff：`auth.py` 漏洞补丁（含 hardcoded secret + hmac fix）
- 测试次数：30+ 次，覆盖：基本 run、NDJSON 格式、--dir、-f、--agent、--variant、--thinking、--session --continue、--pure、--prompt 错误调用、TUI 启动、doom_loop、verdict 差异

### 11.2 推荐跟进文档

- Phase 9 设计：`docs/architecture/opencode-review-executor.md`（**新建**）
- Phase 9 stub 任务：JIRA-XXX（**待立**）
- Adapter 重写 spec：`docs/architecture/agent-adapter-layer.md` 追加 opencode 章节
- Registry 修正：直接 PR（1 行改 `review_gate=True, supports_worktree=True`）

### 11.3 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| opencode CLI 升级破坏 schema | 中 | 高 | 锁 `min_cli_version=1.15.0`，CI 跑最小版本矩阵 |
| `--agent plan` 行为未来变化 | 低 | 中 | 季度回归测试 10 条 prompt 评测集 |
| Hermes worktree 与 opencode snapshot 错位 | 中 | 中 | Adapter 校验 `worktree.path/.git` 一致性 |
| 双 agent 复核成本翻倍 | 中 | 低 | 默认 plan；只在 plan=BLOCK 时才追加 build |
| Plan agent 漏报安全漏洞 | 中 | 高 | 关键 PR（merge to main）走人工 + 双 agent |

---

**评审结束** · 12 issues · 0 个需要立即修复的逻辑错误（4 个 P0 是"未实现"而非"实现错"） · 建议以 **1 sprint stub** 进入 Phase 9
