# Hermes Browser Runtime / BrowserProvider — 大一统架构

Date: 2026-06-06
Status: Architecture + phased implementation in progress. Phase 1 / 2A / 2B / 2C are implemented in Desktop. Phase 2D safety design is complete (contract types + test added; no execution code).
Prerequisite audit: [Browser Workspace 状态审计](../research/browser-workspace-mvp-evaluation.md)
Sibling designs:
- [BrowserContextProvider Adapter Design](./browser-context-provider-design.md)

---

## 目录

1. [目标定义](#1-目标定义)
2. [当前 Provider / Surface 清单](#2-当前-provider--surface-清单)
3. [Capability Matrix](#3-capability-matrix)
4. [BrowserSnapshot Schema](#4-browsersnapshot-schema)
5. [BrowserActionRequest Schema](#5-browseractionrequest-schema)
6. [BrowserActionResult Schema](#6-browseractionresult-schema)
7. [Actor 模型](#7-actor-模型)
8. [Permission Policy](#8-permission-policy)
9. [Handoff 模型](#9-handoff-模型)
10. [Obscura 的位置](#10-obscura-的位置)
11. [分阶段实施计划](#11-分阶段实施计划)

---

## 1. 目标定义

### 1.1 BrowserRuntime（浏览器运行时）

**BrowserRuntime** 是一个浏览器引擎实例——一个可以加载页面、执行 JavaScript、渲染 DOM 的 Chromium（或兼容）进程。它是物理资源，不是接口。

| Runtime 实例 | 位置 | 生命周期 | 当前用途 |
|-------------|------|---------|---------|
| Electron `WebContentsView` | Desktop 主进程 `browser-session.cjs` | 跟随 Desktop 窗口，mount/unmount | 用户 right-rail 浏览 |
| `agent-browser` 管理的 headless Chromium | `browser_tool.py` → subprocess | 跟随 task session，由 cleanup thread 回收 | Agent 自动化 |
| Cloud Browser（Browserbase/Browser Use） | 远程 WebSocket | 跟随 task session | Agent 自动化（云端） |
| Lightpanda | `agent-browser --engine lightpanda` | 同 agent-browser | 快速 headless 导航快照 |

**关键特性**：一台机器上可以同时跑多个 BrowserRuntime 实例。当前 audited 状态是 Desktop 和 agent-browser 各自启动一个 Chromium，互不知晓。

### 1.2 BrowserProvider（浏览器提供者）

**BrowserProvider** 是抽象接口，统一不同 BrowserRuntime 的访问方式。它定义了：

- **Read 面**：如何从浏览器获取上下文（URL、title、DOM、screenshot、selection、clipboard）
- **Action 面**：如何请求浏览器执行操作（navigate、click、type、eval），以及是否需要审批
- **Session 面**：如何创建/销毁 session，如何 handoff

当前 `agent.browser_provider.BrowserProvider`（`hermes-agent/agent/browser_provider.py:49`）只覆盖 cloud provider 的 session 生命周期（`create_session` / `close_session` / `emergency_cleanup`），不覆盖 read/action 面。本文档定义大一统的 BrowserProvider 接口，将其扩展到所有 provider 类型。

### 1.3 统一后的架构

```text
┌─ Hermes Agent ──────────────────────────────────────────────────────────┐
│                                                                          │
│   browser_tool.py                                                       │
│        │                                                                 │
│        ▼                                                                 │
│   ┌──────────────────────┐                                              │
│   │  BrowserProviderRouter │  ← 根据 task 上下文选择 provider              │
│   └──────┬───────────────┘                                              │
│          │                                                               │
│    ┌─────┼──────────────┬──────────────────┬──────────────┐             │
│    ▼     ▼              ▼                  ▼              ▼             │
│  ┌────┐┌──────────┐┌──────────┐┌──────────────┐┌─────────────────┐     │
│  │Dskp││AgentBrwsr││CloudBrwsr││CloudBrwsr    ││   Obscura       │     │
│  │Vis ││Provider  ││(bwsrbase)││(browser-use) ││   Provider      │     │
│  │Prov││          ││          ││              ││  (future)       │     │
│  └──┬─┘└────┬─────┘└────┬─────┘└──────┬───────┘└────────┬────────┘     │
│     │       │           │             │                │              │
│     ▼       ▼           ▼             ▼                ▼              │
│  Electron agent-    Browserbase   Browser Use     headless Chromium   │
│  WebCont- browser   Cloud         Cloud           (fast lane, no      │
│  entsView CLI       Browser       Browser         heavyweight)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 当前 Provider / Surface 清单

### 2.1 已存在的 Provider（有运行代码）

#### DesktopVisibleProvider

| 属性 | 值 |
|------|----|
| **代码位置** | `apps/desktop/electron/browser-session.cjs` + `apps/desktop/electron/main.cjs:5392-5679` |
| **Bridge 暴露** | `apps/desktop/electron/preload.cjs:119-161` → `window.hermesDesktop.browser` |
| **UI 组件** | `apps/desktop/src/app/browser-workspace.tsx:68-451` |
| **Runtime 引擎** | Electron `WebContentsView`（Chromium），session partition `persist:hermes-browser` |
| **当前状态** | **Phase 2C — read-only snapshot + approval-gated Desktop `navigate`; no click/type/eval execution** |
| **Agent 可访问** | ❌ 不。完全独立于 Agent runtime。Agent 没有路径连接到此 provider。 |
| **用户可访问** | ✅ right-rail Browser tab，URL 栏、前进/后退/刷新按钮 |
| **Read API** | `getState()`, `getDomSummary()`, `getScreenshot()`, `getSelectedText()` |
| **Action API** | `navigate()`, `reload()`, `stop()`, `goBack()`, `goForward()` — 全部被 `requireUserSource()` gate 保护（`main.cjs:5399-5405`） |
| **持久化** | Cookies/Local Storage/IndexedDB 持久化在 `persist:hermes-browser` partition |

**当前暴露的 IPC 方法清单**：

```
hermes:browser:is-available       → { available: bool, reason?: string }
hermes:browser:mount              → { ok: bool }
hermes:browser:unmount            → { ok: bool }
hermes:browser:set-bounds         → { ok: bool }
hermes:browser:get-state          → { url, title, canGoBack, canGoForward, isLoading }
hermes:browser:get-dom-summary    → { title, description, headings[], textPreview (3KB) }
hermes:browser:get-screenshot     → { dataURL (PNG base64), width, height }
hermes:browser:get-selected-text  → { text }
hermes:browser:navigate           → { ok, url, error? }     requires source:"user"
hermes:browser:reload             → { ok, error? }           requires source:"user"
hermes:browser:stop               → { ok, error? }           requires source:"user"
hermes:browser:go-back            → { ok, canGoBack, error? } requires source:"user"
hermes:browser:go-forward         → { ok, canGoForward, error? } requires source:"user"
```

#### AgentBrowserProvider

| 属性 | 值 |
|------|----|
| **代码位置** | `tools/browser_tool.py:1-3864` |
| **Runtime 引擎** | `agent-browser` CLI（npm 包），管理独立 headless Chromium 进程 |
| **当前状态** | **生产可用**。10 个注册 tool，全功能 agent action。 |
| **Agent 可访问** | ✅ 通过 `browser_*` tool call |
| **用户可访问** | ❌ 不。headless，无 UI surface。 |
| **Read API** | `browser_snapshot`, `browser_vision`, `browser_console`, `browser_get_images` |
| **Action API** | `browser_navigate`, `browser_click`, `browser_type`, `browser_scroll`, `browser_back`, `browser_press`, `browser_console(expression=...)` |
| **Session** | 按 `task_id` 隔离，通过 `_active_sessions` dict 管理。支持 inactivity timeout 清理线程。 |
| **引擎选择** | 支持 Chrome / Lightpanda 切换（`browser_tool.py:636-681`） |

**当前注册的 10 个 tool**（`browser_tool.py:3782-3863`）：

| Tool | 类型 | 备注 |
|------|------|------|
| `browser_navigate` | action | 导航 + 返回 compact snapshot |
| `browser_snapshot` | read | Accessibility tree 文本快照 |
| `browser_click` | action | 点击 @eN ref |
| `browser_type` | action | 向 input 输入文本 |
| `browser_scroll` | action | 上下滚动 |
| `browser_back` | action | 浏览器后退 |
| `browser_press` | action | 键盘按键 |
| `browser_get_images` | read | 页面图片列表 |
| `browser_vision` | read | 截图 + 视觉分析 |
| `browser_console` | read/action | console 输出 + **任意 JS 执行**（`expression` 参数） |

#### CloudBrowserProvider

| 属性 | 值 |
|------|----|
| **ABC 定义** | `agent/browser_provider.py:49-176` |
| **Registry** | `agent/browser_registry.py:48-193` |
| **插件路径** | `plugins/browser/browserbase/`, `plugins/browser/browser_use/`, `plugins/browser/firecrawl/` |
| **当前状态** | **生产可用**。用于 cloud browser session 管理。 |
| **Provider 数量** | 3：Browserbase, Browser Use, Firecrawl |
| **Session 合约** | `create_session(task_id)` → `{ session_name, bb_session_id, cdp_url, features }` |
| **Auto-detect** | Browser Use → Browserbase 顺序，按 `is_available()` 过滤（`browser_registry.py:107-110`） |

**注意**：CloudBrowserProvider 当前只定义 session 生命周期（`create_session` / `close_session` / `emergency_cleanup`），不直接暴露 read/action 方法。Read/action 由 `browser_tool.py` 通过 `agent-browser --cdp <url>` 统一驱动——provider 只提供 `cdp_url`。

### 2.2 未来 Provider

#### ObscuraProvider（Phase 5）

| 属性 | 值 |
|------|----|
| **设计状态** | 未开始。本文档定义其位置和合约。 |
| **目标** | 针对信息检索（非交互）的极快 headless lane。用于 `web_search` / `web_extract` 的替代 backend，以及不需要登录态的快速 page snapshot。 |
| **引擎候选** | Lightpanda、专用 headless Chromium pool、Rust CDP client |
| **与 Desktop Chromium 的关系** | 不替代。Desktop WebContentsView 保持登录态和交互能力。Obscura 是无状态的「快车道」。 |

---

## 3. Capability Matrix

| Capability | DesktopVisibleProvider | AgentBrowserProvider | CloudBrowserProvider | ObscuraProvider (future) |
|------------|----------------------|---------------------|---------------------|--------------------------|
| `visible` | ✅ right-rail | ❌ headless | ❌ remote | ❌ headless |
| `hasLoginState` | ✅ persist partition | ❌ 临时 profile | ❌ 按 session | ❌ 无状态 |
| `canReadDom` | ✅ innerText (3KB) | ✅ aria snapshot | ✅ CDP | ✅ 计划 |
| `canScreenshot` | ✅ `capturePage()` | ✅ via CLI | ✅ CDP | ⚠️ 取决于引擎（LP 不支持） |
| `canNavigate` | ✅ user-gated | ✅ agent | ✅ agent | ✅ agent |
| `canClick` | ❌ | ✅ agent | ✅ agent | ❌ 非交互 lane |
| `canType` | ❌ | ✅ agent | ✅ agent | ❌ 非交互 lane |
| `canEval` | ❌ | ✅ agent | ✅ agent | ❌ 非交互 lane |
| `requiresApprovalForAgentAction` | ✅ 当前所有 action 被 `requireUserSource()` 阻止 | ❌ 无需审批（现有行为） | ❌ 无需审批（现有行为） | N/A（无 action） |
| `supportsFastHeadless` | ❌ 依赖 GUI 进程 | ⚠️ 标准 Chromium headless | ❌ | ✅ 目标 <100ms 首次快照 |

---

## 4. BrowserSnapshot Schema

大一统的只读上下文快照。**当前不存在**——这是本文档定义的新合约。

```typescript
/**
 * BrowserSnapshot — the unified read-only context payload.
 *
 * This is the SINGLE payload that the Agent receives from any BrowserProvider.
 * The Provider is responsible for populating whichever fields its runtime
 * supports; the Agent treats missing fields as "not available from this
 * provider."
 *
 * COMPARISON TO CURRENT STATE:
 * - Desktop: getState() + getDomSummary() + getScreenshot() + getSelectedText()
 *   return these fields in SEPARATE IPC calls with DIFFERENT shapes.
 *   BrowserSnapshot unifies them.
 * - Agent: browser_snapshot returns ariaSnapshot text only.
 *   browser_vision returns screenshot separately.
 *   BrowserSnapshot unifies them.
 * - Cloud: CDP-based, same split as Agent.
 */

interface BrowserSnapshot {
  // ── Identity ──────────────────────────────────────────────────
  /** ISO 8601 timestamp of capture. */
  capturedAt: string;

  /** Which provider produced this snapshot. */
  source: {
    provider: "desktop-visible" | "agent-headless" | "cloud-browserbase"
            | "cloud-browser-use" | "cloud-firecrawl" | "obscura";
    /** Session identifier within the provider. */
    sessionKey: string;
    /** Whether this is a read-only provider or permits agent actions. */
    mode: "read_only" | "agent_action" | "approval_required";
  };

  // ── Page state ────────────────────────────────────────────────
  activeTab: {
    /** Full URL. */
    url: string;
    /** Document title. */
    title: string;
    /** Whether the page is still loading. */
    isLoading: boolean;
    /** Whether back-history exists. */
    canGoBack: boolean;
    /** Whether forward-history exists. */
    canGoForward: boolean;
    /** Navigation source of the current page. */
    navigationSource: "user" | "agent" | "system";
  };

  // ── DOM content ───────────────────────────────────────────────
  dom: {
    /**
     * Structured accessibility tree text (ariaSnapshot).
     * Source: agent-browser "snapshot" command or CDP Accessibility.getFullAXTree.
     * Contains interactive @eN refs when the provider supports them.
     * Max 20 KB, clipped.
     */
    ariaSnapshot: string | null;

    /**
     * Raw body text extract.
     * Source: document.body.innerText (Electron) or CDP Runtime.evaluate.
     * Max 10 KB, clipped.
     */
    bodyText: string | null;

    /**
     * Meta description.
     * Source: document.querySelector('meta[name="description"]').
     */
    metaDescription: string | null;

    /**
     * Top-level headings (h1-h3), up to 20.
     * Each heading text clipped to 200 chars.
     */
    headings: Array<{ tag: string; text: string }>;
  };

  // ── User context ──────────────────────────────────────────────
  userContext: {
    /**
     * User-selected text on the page.
     * Source: window.getSelection().toString().
     * Max 10 KB, clipped. Empty string if nothing selected.
     */
    selectedText: string;

    /**
     * System clipboard text preview.
     * Max 2 KB, clipped. Empty string if clipboard is empty
     * or clipboard read permission is disabled.
     */
    clipboardPreview: string;
  };

  // ── Visual ────────────────────────────────────────────────────
  screenshot: {
    /**
     * Reference to the captured screenshot.
     * May be a file path, data URI, or null if provider doesn't support
     * screenshots or capture failed.
     */
    ref: string | null;
    /** Image width in pixels. */
    width: number;
    /** Image height in pixels. */
    height: number;
    /** Size in bytes. */
    sizeBytes: number;
  };

  // ── Browser console (best-effort) ─────────────────────────────
  console: {
    /** Recent console messages (log/warn/error), up to 50. */
    messages: Array<{ level: string; text: string }>;
    /** Recent uncaught JS exceptions, up to 20. */
    errors: Array<{ message: string }>;
  } | null;

  // ── Limits applied ────────────────────────────────────────────
  limits: {
    maxAriaSnapshotChars: number;
    maxBodyTextChars: number;
    maxSelectionChars: number;
    maxClipboardChars: number;
    maxTotalBytes: number;
    actualTotalBytes: number;
  };

  // ── Any error encountered during capture (per-field) ──────────
  errors: Array<{ field: string; message: string }>;
}
```

### 当前到目标字段映射

| Snapshot 字段 | DesktopVisible 当前来源 | AgentBrowser 当前来源 | Cloud 当前来源 |
|--------------|----------------------|---------------------|--------------|
| `activeTab.url` | `hermes:browser:get-state` → `wc.getURL()` | `browser_snapshot` aria text 中的 URL | CDP `Page.navigate` 的返回 |
| `activeTab.title` | `hermes:browser:get-state` → `wc.getTitle()` | `browser_snapshot` output 解析 | CDP `Runtime.evaluate('document.title')` |
| `activeTab.isLoading` | `hermes:browser:get-state` → `wc.isLoading()` | 无直接对应 | CDP `Page.loadEventFired` |
| `dom.ariaSnapshot` | ❌ 不存在（Desktop 无 accessibility tree） | `browser_snapshot` 的完整 output | `agent-browser --cdp snapshot` |
| `dom.bodyText` | `hermes:browser:get-dom-summary` → `textPreview` | 无直接对应（需从 aria 文本解析） | `agent-browser --cdp eval 'document.body.innerText'` |
| `dom.headings` | `hermes:browser:get-dom-summary` → `headings[]` | 无 | `agent-browser --cdp eval` |
| `screenshot` | `hermes:browser:get-screenshot` → dataURL | `browser_vision` output 中的 path | `agent-browser --cdp screenshot` |
| `userContext.selectedText` | `hermes:browser:get-selected-text` | ❌ headless 中无意义 | ❌ 远程 browser 中无意义 |
| `userContext.clipboardPreview` | ❌ 设计文档要求但未实现 | ❌ | ❌ |

---

## 5. BrowserActionRequest Schema

Agent 请求浏览器执行操作的统一 schema。**当前不存在**——浏览器 action 目前直接在 `browser_tool.py` 中通过 subprocess 调用 `agent-browser` CLI 执行，没有任何抽象层。

```typescript
/**
 * BrowserActionRequest — unified action request from Agent to any BrowserProvider.
 *
 * DESIGN NOTE (Phase 1 — contract only):
 * This schema is defined in the architecture document but MUST NOT be
 * implemented until Phase 3+.  The existing browser_tool.py tool handlers
 * continue to function unchanged.  When a BrowserProviderRouter is built
 * (Phase 4), it translates existing tool calls into BrowserActionRequest
 * and dispatches to the selected provider.
 */

interface BrowserActionRequest {
  /** Unique request ID (generated by the caller). */
  requestId: string;

  /** ISO 8601 timestamp. */
  requestedAt: string;

  /** Which actor initiated this action. */
  actor: "agent" | "user" | "system";

  /** The task context this action belongs to. */
  taskId: string;

  /** The action to perform. */
  action: BrowserAction;

  /**
   * Why the actor is requesting this action.
   * Required for agent-initiated actions — shown in approval UI.
   */
  reason?: string;
}

type BrowserAction =
  | NavigateAction
  | ClickAction
  | TypeAction
  | ScrollAction
  | BackAction
  | PressKeyAction
  | EvalAction
  | ScreenshotAction
  | SnapshotAction;

interface NavigateAction {
  type: "navigate";
  url: string;
}

interface ClickAction {
  type: "click";
  /** Element ref from aria snapshot (e.g. "@e5"). */
  ref: string;
}

interface TypeAction {
  type: "type";
  ref: string;
  text: string;
}

interface ScrollAction {
  type: "scroll";
  direction: "up" | "down";
}

interface BackAction {
  type: "back";
}

interface PressKeyAction {
  type: "press_key";
  key: string;
}

interface EvalAction {
  type: "eval";
  /** JavaScript expression to evaluate in page context. */
  expression: string;
}

interface ScreenshotAction {
  type: "screenshot";
  /** Optional natural-language question about the screenshot. */
  question?: string;
  /** Whether to overlay @eN annotations. */
  annotate?: boolean;
}

interface SnapshotAction {
  type: "snapshot";
  /** Full page content or compact interactive elements only. */
  full?: boolean;
}
```

---

## 6. BrowserActionResult Schema

```typescript
/**
 * BrowserActionResult — unified result from a BrowserActionRequest.
 */

interface BrowserActionResult {
  /** Echoes the request ID. */
  requestId: string;

  /** ISO 8601 timestamp of execution. */
  executedAt: string;

  /** Which provider executed this action. */
  executedBy: {
    provider: string;
    sessionKey: string;
  };

  /** Execution status. */
  status: "executed" | "rejected" | "failed" | "pending_approval";

  /**
   * If status is "pending_approval", the action was queued for user
   * review and has not yet executed.  The Agent should wait.
   */
  approvalId?: string;

  /** Error details when status is "failed" or "rejected". */
  error?: string;

  /**
   * The snapshot captured AFTER the action completed.
   * Always present for navigate/click/type/scroll — the action result
   * carries a fresh page state so the Agent doesn't need a separate
   * snapshot call.
   */
  postActionSnapshot?: BrowserSnapshot;

  /**
   * For eval actions: the return value of the expression.
   */
  evalResult?: unknown;

  /**
   * For screenshot actions: reference to the captured screenshot.
   */
  screenshotRef?: string;

  /**
   * Whether a fallback provider was used (e.g. Lightpanda → Chrome).
   */
  fallback?: {
    from: string;
    to: string;
    reason: string;
  };
}
```

---

## 7. Actor 模型

每个 browser action 和 snapshot 请求都关联一个 **actor**。Actor 决定 permission 检查路径。

```
┌──────────────────────────────────────────────────────────────┐
│                        Actor Model                           │
├──────────┬─────────────────────┬─────────────────────────────┤
│  Actor   │  定义               │  Permission 默认             │
├──────────┼─────────────────────┼─────────────────────────────┤
│  user    │ 物理用户在 Desktop   │  所有 action                │
│          │ UI 上操作浏览器      │  ALLOW（不检查）             │
│          │ （URL 栏、按钮等）   │                             │
├──────────┼─────────────────────┼─────────────────────────────┤
│  agent   │ Agent 通过 tool      │  取决于 provider 的         │
│          │ call 请求 action     │  requiresApprovalForAgent-  │
│          │                      │  Action 字段                │
├──────────┼─────────────────────┼─────────────────────────────┤
│  system  │ 系统自动操作         │  ALLOW（内部操作）           │
│          │ （如 handoff、       │                             │
│          │  初始化导航）        │                             │
└──────────┴─────────────────────┴─────────────────────────────┘
```

### 当前状态

| Actor | DesktopVisible | AgentBrowser | CloudBrowser |
|-------|---------------|-------------|-------------|
| `user` | ✅ `main.cjs:5404` — `payload.source === 'user'` gate 放行 | N/A（headless，无用户） | N/A |
| `agent` | ❌ `requireUserSource()` 拦截 | ✅ 无需审批，直接通过 `_run_browser_command()` | ✅ 无需审批 |
| `system` | ❌ 同样被 `requireUserSource()` 拦截 | ✅ 内部路径不受限 | ✅ 内部路径不受限 |

### 目标状态（Phase 4+）

```
agent action → BrowserProviderRouter
                  │
                  ├─ provider.requiresApprovalForAgentAction === false
                  │     → dispatch directly
                  │
                  └─ provider.requiresApprovalForAgentAction === true
                        → emit ActionProposal event
                        → UI shows proposal to user
                        → user approves/rejects
                        → if approved: dispatch
                        → notify agent of result
```

---

## 8. Permission Policy

每个 (provider, action_type, actor) 三元组映射到一个 permission 决策。

```typescript
type PermissionDecision = "allow" | "deny" | "approval_required";

interface PermissionPolicy {
  /** Which provider this rule applies to. "*" means all. */
  provider: string;

  /** Which action type. "*" means all. */
  action: string;

  /** Which actor. "*" means all. */
  actor: "user" | "agent" | "system" | "*";

  /** The decision for this rule. */
  decision: PermissionDecision;
}
```

### 默认 Policy 表

| Provider | Action | Actor | Decision | 理由 |
|----------|--------|-------|----------|------|
| `desktop-visible` | `navigate` | `user` | `allow` | 用户在自己桌面 UI 中导航 |
| `desktop-visible` | `navigate` | `agent` | `approval_required` | Agent 不应在用户可见窗口自动导航 |
| `desktop-visible` | `click` | `agent` | `approval_required` | 用户必须看见并批准每次交互 |
| `desktop-visible` | `type` | `agent` | `approval_required` | 用户必须看见并批准每次输入 |
| `desktop-visible` | `eval` | `agent` | `approval_required` | JS 执行是高风险操作 |
| `desktop-visible` | `snapshot` | `agent` | `allow` | 只读操作，安全 |
| `desktop-visible` | `screenshot` | `agent` | `allow` | 只读操作，安全 |
| `agent-headless` | `*` | `agent` | `allow` | 无 UI surface，agent 独占，现有行为 |
| `agent-headless` | `navigate` | `agent` | `allow` | 现有行为 |
| `cloud-*` | `*` | `agent` | `allow` | 云端 headless，无用户 UI，现有行为 |
| `obscura` | `navigate` | `agent` | `allow` | 无状态快车道 |
| `obscura` | `snapshot` | `agent` | `allow` | 核心能力 |
| `obscura` | `click` | `agent` | `deny` | 非交互 lane |
| `obscura` | `eval` | `agent` | `deny` | 非交互 lane |

### 当前状态

- **DesktopVisible**：所有 agent action 通过 `requireUserSource()` 被隐式 `deny`。没有 `approval_required` 中间状态。
- **AgentBrowser / Cloud**：没有 permission 检查。Agent 的所有 browser tool call 直接执行。
- **Permission policy 机制**：不存在。本文档定义的 policy 表在 Phase 1 之前不会实现。

---

## 9. Handoff 模型

Handoff 是将浏览器 session 从一个 provider 转移到另一个 provider 的能力。

### 场景

#### 场景 A：background → visible

```
1. Agent 在 agent-headless provider 中打开了 github.com/gu87/trendradar
2. Agent 导航、点击、读取数据 — 全部在 headless 中完成
3. 用户想知道 Agent 看到了什么
4. Handoff: session 从 agent-headless 迁移到 desktop-visible
5. 用户的 right-rail Browser tab 现在显示 agent 打开的页面
6. 导航来源标记为 "agent"
```

#### 场景 B：visible → background

```
1. 用户在 desktop-visible 中浏览并登录了 internal dashboard
2. 用户想让 Agent 继续操作这个页面
3. Handoff: session 从 desktop-visible 迁移到 agent-headless
4. Agent 在 headless Chromium 中接管同一个页面
5. 需要 clone session state（cookies、localStorage）
```

### Handoff 合约

```typescript
interface BrowserHandoffRequest {
  /** Which actor initiated the handoff. */
  initiatedBy: "user" | "agent";

  /** Source provider + session key. */
  from: {
    provider: string;
    sessionKey: string;
  };

  /** Target provider. */
  to: {
    provider: string;
    /** Optional: create a new session or reuse existing. */
    sessionKey?: string;
  };

  /**
   * What to transfer.
   * "url": navigate target to the same URL.
   * "session_state": clone cookies + localStorage + sessionStorage.
   * "full": transfer everything including history stack.
   */
  transfer: "url" | "session_state" | "full";
}

interface BrowserHandoffResult {
  ok: boolean;
  /** The new session key in the target provider. */
  sessionKey: string;
  /** The URL after handoff. */
  url: string;
  /** Any error that occurred. */
  error?: string;
}
```

### Handoff 实现可行性

| Transfer 级别 | desktop→headless | headless→desktop | 难度 |
|--------------|------------------|------------------|------|
| `url` | ✅ `wc.loadURL()` | ✅ `agent-browser open <url>` | 低 |
| `session_state` | ⚠️ 需要导出 Electron session cookies → 注入 headless Chromium | ⚠️ 需要导出 headless profile → 注入 Electron session | 中 |
| `full` | ❌ 不可行，history stack 在两个引擎间不可序列化 | ❌ 同上 | 高，不建议 |

### 当前状态

**不存在任何 handoff 机制。** DesktopVisible 和 AgentBrowser 是两个完全独立的 Chromium 实例，没有 session 迁移路径。

---

## 10. Obscura 的位置

### Obscura 是什么

Obscura 是一个 **极快的专用 headless lane**，用于信息检索（非交互）场景。它不是 Desktop Chromium 的替代品。

### 为什么需要 Obscura

当前 agent-browser headless Chromium 启动一个完整浏览器进程，首次导航到 `about:blank` 再导航到目标页面——首字节时间通常在 2-5 秒。对于 `web_search` / `web_extract` / "快速看一眼这个页面" 场景，这个延迟过高。

### Obscura 的设计定位

```
┌──────────────────────────────────────────────────────────────┐
│                    Browser 使用场景                           │
├─────────────────────┬──────────────────┬─────────────────────┤
│                      │                  │                     │
│  Desktop Chromium    │  Headless Agent  │  Obscura            │
│  (WebContentsView)   │  Chromium        │  (fast lane)        │
│                      │                  │                     │
│  • 用户交互          │  • Agent 自动化  │  • 信息检索         │
│  • 登录态            │  • 表单填写      │  • 快速 page peek   │
│  • 多 tab            │  • 复杂交互      │  • web_extract 查询 │
│  • 截图              │  • 视觉分析      │  • 无 JS 页面快照   │
│  • 持久化            │  • JS eval       │                     │
│                      │                  │                     │
│  启动: 跟随 app      │  启动: ~1-2s     │  启动: <100ms       │
│  内存: ~200MB        │  内存: ~150MB    │  内存: <50MB        │
│  引擎: Chromium      │  引擎: Chromium  │  引擎: Lightpanda   │
│                      │  (或 Lightpanda) │  或最小 Chromium    │
└─────────────────────┴──────────────────┴─────────────────────┘
```

### Obscura 的能力边界

| 能力 | Obscura 支持 | 备注 |
|------|------------|------|
| `navigate` + `snapshot` | ✅ 核心能力 | 目标 <100ms 首次快照 |
| `screenshot` | ⚠️ 引擎相关 | Lightpanda 不支持截图 |
| `click` / `type` / `eval` | ❌ | 非交互 lane |
| `scroll` | ⚠️ 如果需要 "load more" | 可能是有限支持的唯一边际情况 |
| `hasLoginState` | ❌ | 无 cookie/session 持久化 |
| `visible` | ❌ | 完全 headless |

### Obscura 不替代什么

- **不替代 Desktop Chromium**：用户仍通过 Desktop Browser Workspace 浏览需要登录的网站。
- **不替代 Agent headless Chromium**：需要交互（click/type/form fill）的场景仍走标准 agent-browser。
- **不替代 Cloud providers**：需要 residential proxy / stealth 的场景仍走 Browserbase/Use。

Obscura 是一个 **补充 lane**，不是替代 lane。

---

## 11. 分阶段实施计划

### Phase 1：Contract Only（Week 1-2）

**Implementation status (2026-06-07)**：已完成 Desktop TypeScript contract：
`hermes-agent/apps/desktop/src/app/browser-runtime/types.ts`。

**目标**：定义 TypeScript + Python 的 interface/schema，不做任何实现。

**交付物**：
1. `agent/browser_runtime_provider.py` — Python `BrowserRuntimeProvider` ABC
   - 扩展当前 `BrowserProvider`（`agent/browser_provider.py:49`），增加 read action 方法
   - 定义 `get_snapshot()` / `execute_action()` / `handoff()` 抽象方法
   - 定义 `requires_approval_for(action_type: str) -> bool`
2. `apps/desktop/src/browser/browser-provider-types.ts` — TypeScript 类型定义
   - `BrowserSnapshot` / `BrowserActionRequest` / `BrowserActionResult` interface
   - `PermissionPolicy` / `PermissionDecision` type
   - `BrowserHandoffRequest` / `BrowserHandoffResult` interface
3. Capability matrix 文档更新（即本文档的最终版）

**不改动**：`browser_tool.py`、`main.cjs`、`browser-session.cjs`、任何现有代码。

---

### Phase 2：DesktopVisibleProvider Adapter（Week 3-4）

**Implementation status (2026-06-07)**：
- Phase 2A 已完成：`desktop-visible-provider.ts` 通过现有 preload bridge 组合 `BrowserSnapshot`，不新增 Electron IPC。
- Phase 2B 已完成：`action-gateway.ts` / `action-gateway-ui.tsx` 提供 proposal / approve / deny / log UI。
- Phase 2C 已完成最小执行闭环：用户批准后仅允许 Desktop `navigate(url)`，仍通过现有 `source:"user"` gate；`click` / `type` / `eval` 继续不执行。
- **Phase 2D 已完成**：安全设计文档 + contract types（`BrowserActionSafetyContext`, `ElementFingerprint`, `PreActionVerification`），不含执行代码。新增 `BrowserActionRequest.safetyContext?` 和 `BrowserActionResult.preActionVerification?` 字段。`eval` / `press_key` / `scroll` 被声明为永久 deny。`click` / `type` 保持 deny，等待 Phase 2E-2F 实现安全模型后再改为 `approval_required`。

**Phase 2D 设计文档**：[Desktop Agent Action Safety Design](./desktop-browser-agent-action-safety.md)

**目标**：将 Desktop 已有的 browser IPC 封装到 `BrowserRuntimeProvider` 接口下。

**修改文件**：
1. `apps/desktop/electron/main.cjs` — 新增 **1 个 IPC handler**：
   - `hermes:browser:get-snapshot` — 组合 `get-state` + `get-dom-summary` + `get-screenshot` + `get-selected-text`，返回 `BrowserSnapshot` JSON
2. `apps/desktop/electron/preload.cjs` — 暴露 `getSnapshot()` 方法
3. `apps/desktop/src/browser/desktop-visible-provider.ts`（新建）— 实现 TypeScript 侧 `BrowserRuntimeProvider` interface，桥接 preload API

**能力**：
- `get_snapshot()` → ✅ 实现
- `execute_action(navigate)` → ✅ Phase 2C：用户批准后执行，仍走 `source:"user"` gate
- `execute_action(click/type/eval)` → ❌ 不实现，等待单独安全设计
- `handoff()` → ❌ 不实现

**不改动**：`browser_tool.py` 不感知 DesktopVisibleProvider。Agent 仍通过 agent-browser CLI 工作。

---

### Phase 3：AgentBrowserProvider Adapter（Week 5-6）

**目标**：将 agent-browser CLI 封装到 `BrowserRuntimeProvider` 接口下。

**修改文件**：
1. `tools/browser_tool.py` — **不改变现有 tool handler**，新增一个 `AgentBrowserProvider` 类
   - `get_snapshot(task_id)` → 组合 `browser_snapshot()` + `browser_vision()` + `browser_console()` 结果，映射到 `BrowserSnapshot`
   - `execute_action(task_id, action)` → 分发到现有 `browser_navigate()` / `browser_click()` / `browser_type()` 等
   - `handoff()` → 占位（未来实现）
   - `requires_approval_for()` → `return False`（现有行为）
2. `agent/browser_runtime_provider.py` — 注册 `AgentBrowserProvider` 到 provider registry

**能力**：
- `get_snapshot()` → ✅ 实现，通过现有 tool 函数组合
- `execute_action()` → ✅ 实现，通过现有 tool 函数分发
- `handoff()` → ❌ 占位

**不改动**：现有 `browser_navigate` 等注册 tool 继续正常工作。Provider 是额外的一层封装。

---

### Phase 4：Router / Handoff（Week 7-10）

**目标**：Agent browser tool 调用通过 `BrowserProviderRouter` 路由到正确的 provider。

**修改文件**：
1. `tools/browser_tool.py` — 在 `_get_session_info()` (`:1651`) 中增加 router 逻辑：
   - 检测 `HERMES_DESKTOP_BROWSER_CDP_URL` 环境变量 → 路由到 DesktopVisible CDP 端点
   - 否则按现有逻辑（cloud provider → agent-browser headless）
2. `apps/desktop/electron/main.cjs` — **新增 CDP relay**：
   - 在 `hermes:browser:mount` (`:5455`) 中 attach `wc.debugger`
   - 启动 localhost WebSocket server，relay CDP 消息到 WebContents
   - 新增 `hermes:browser:get-cdp-url` IPC handler 返回 CDP 端点
3. Handoff 实现：
   - `headless → visible`：Desktop 通过 CDP 连接到 headless 的相同 CDP URL，`wc.loadURL()` 到当前页面
   - `visible → headless`：导出 Electron session cookies，注入 headless Chromium user data dir

**能力**：
- Router 根据 task 上下文选择 provider
- Agent 可以读写 Desktop 用户正在看的同一个 WebContents（通过 CDP）
- Handoff 支持 `url` 级别（双向），`session_state` 级别（headless → desktop only）

**关键约束**：Desktop 的 `requireUserSource()` gate 继续保护用户主导的 UI navigation。Agent 通过 CDP 的操作走 `agent` actor → `approval_required` policy。

---

### Phase 5：ObscuraProvider（Week 11+）

**目标**：提供一个极快的 headless lane，用于信息检索场景。

**交付物**：
1. `plugins/browser/obscura/provider.py` — 实现 `BrowserRuntimeProvider`
   - 使用 Lightpanda 引擎（`agent-browser --engine lightpanda`）
   - `get_snapshot()` → 导航 + 快照，目标 <100ms
   - `execute_action()` → 只支持 `navigate` + `snapshot` + `scroll`（如需）
   - `requires_approval_for()` → `return False`（无交互，无审批需要）
2. Router 更新：`web_search` / `web_extract` / 快速 page peek → 自动路由到 Obscura
3. 预热池：启动时 pre-warm 1-2 个 Lightpanda 进程

**依赖**：`agent-browser` v0.25.3+ 的 Lightpanda 支持已就绪（`browser_tool.py:636-681` 已有 `_get_browser_engine()` 逻辑）。Obscura 复用它。

**不做**：不要求 Obscura 支持 click/type/eval/login-state/screenshot。它是一个单一用途的检索 lane。

---

## 附录 A：当前代码引用速查

| 内容 | 文件 | 行号 |
|------|------|------|
| Desktop WebContentsView 创建 | `apps/desktop/electron/browser-session.cjs` | `56-135` |
| Desktop browser IPC handlers | `apps/desktop/electron/main.cjs` | `5392-5679` |
| Desktop `requireUserSource()` gate | `apps/desktop/electron/main.cjs` | `5399-5405` |
| Desktop browser preload bridge | `apps/desktop/electron/preload.cjs` | `119-161` |
| Desktop browser TypeScript types | `apps/desktop/src/global.d.ts` | `84-104`, `417-477` |
| Desktop browser UI component | `apps/desktop/src/app/browser-workspace.tsx` | `68-451` |
| Agent browser tool 全部实现 | `tools/browser_tool.py` | `1-3864` |
| Agent browser tool schemas | `tools/browser_tool.py` | `1470-1617` |
| Agent browser tool 注册 | `tools/browser_tool.py` | `3782-3863` |
| Cloud BrowserProvider ABC | `agent/browser_provider.py` | `49-176` |
| Provider registry | `agent/browser_registry.py` | `48-193` |
| Browserbase provider plugin | `plugins/browser/browserbase/provider.py` | `46-217+` |
| Browser Use provider plugin | `plugins/browser/browser_use/provider.py` | `104-253+` |
| BrowserContextProvider 设计文档 | `docs/architecture/browser-context-provider-design.md` | `1-918` |

## 附录 B：术语表

| 术语 | 定义 |
|------|------|
| **BrowserRuntime** | 一个浏览器引擎进程实例（Chromium/Lightpanda） |
| **BrowserProvider** | 统一不同 BrowserRuntime 的抽象接口 |
| **BrowserProviderRouter** | 根据 task 上下文和 capability 需求选择 provider 的调度器 |
| **DesktopVisibleProvider** | 封装 Electron WebContentsView 的 provider，用户可见 |
| **AgentBrowserProvider** | 封装 agent-browser CLI 的 provider，headless |
| **CloudBrowserProvider** | 封装远程浏览器（Browserbase/Use）的 provider |
| **ObscuraProvider** | 极快 headless 检索 lane，无交互，无登录态 |
| **BrowserSnapshot** | 统一的只读页面上下文快照 |
| **BrowserActionRequest** | 统一的浏览器操作请求 |
| **Handoff** | 将 browser session 从一个 provider 迁移到另一个 |
| **Actor** | 发起 browser 操作的实体：user / agent / system |
| **PermissionPolicy** | (provider, action, actor) → allow / deny / approval_required 的规则 |
