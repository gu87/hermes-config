# Desktop Browser Agent Action Safety Design

Date: 2026-06-07
Status: Design document (read-only; no execution code for click/type/eval)
Based on:
- [Browser Runtime / BrowserProvider 大一统架构](./browser-runtime-provider-unification.md)
- [BrowserContextProvider Adapter Design](./browser-context-provider-design.md)
- `apps/desktop/src/app/browser-runtime/action-gateway.ts` (Phase 2C)
- `apps/desktop/electron/main.cjs:5392-5679` (`requireUserSource` gate + IPC handlers)

---

## 1. 为什么 click/type 不能直接开放？

### 1.1 当前 Desktop Browser 的安全边界

Desktop 的嵌入式浏览器是一个 **用户可见的 Electron WebContentsView**，与用户的登录态、cookie、localStorage 同在 `persist:hermes-browser` session partition。

当前安全门控：

```
main.cjs:5394-5400
function requireUserSource(payload) {
  const valid = payload && typeof payload === 'object' && payload.source === 'user'
  if (!valid) {
    rememberLog('[browser] blocked navigation without source:"user"')
  }
  return valid
}
```

这个 gate 只检查 `source === 'user'`。Phase 2C 允许 Agent 批准的 `navigate` 绕过它，因为：
- `navigate` 的目标是 URL，用户在看 URL 栏时可以一眼判断目标是否安全
- 导航到错误 URL 的可逆性高（back 按钮即可恢复）
- URL 是透明的、可审计的字符串

### 1.2 click/type 为什么不适用同一模型

| 风险维度 | navigate | click | type |
|---------|----------|-------|------|
| **目标可审计性** | URL 是透明字符串，用户一眼可知 | `@e5` 是不透明 ref，用户不知道对应哪个元素 | `@e3` + "text" 部分透明，但用户不知道目标 input 的上下文 |
| **操作可逆性** | 高（back 按钮） | 取决于目标操作：可能是提交表单→不可逆 | 取决于目标 input：可能是转账金额、删除确认 |
| **表面攻击面** | 只能改变 URL | 可能触发 form submit、delete action、OAuth consent | 可能输入敏感内容、触发 autocomplete |
| **如果被滥用** | Agent 把你导航到钓鱼页面→你能看到 URL | Agent 在你登录的 GitHub 上点击 "Delete repository" → 你看到的是 `@e5`，不知道是什么 | Agent 在你登录的银行页面输入转账金额 → 你看不到完整上下文 |
| **页面状态依赖** | URL 独立于页面 DOM 状态 | click 的正确性依赖于 `@eN` ref 仍然有效（页面可能已变化） | type 的正确性依赖于目标 input 仍然存在且可写 |

### 1.3 核心结论

**click/type 需要比 navigate 更严格的安全模型**，因为：
1. 目标元素是不透明的 ref（用户无法从 `@e5` 判断这是什么按钮）
2. 操作后果可能不可逆（提交、删除、支付）
3. Agent 的 ref 可能已过期（页面 DOM 在 snapshot 之后发生了变化）

---

## 2. Agent Action 的最小安全模型

### 2.1 安全层级

```
┌─────────────────────────────────────────────────────┐
│             Desktop Agent Action Safety             │
├─────────────────────────────────────────────────────┤
│ Layer 1: ACTION FILTER                              │
│   ▶ 哪些 action 类型允许进入审批队列？               │
│   ▶ deny: eval, press_key, scroll (在 Desktop 上)   │
│   ▶ allow to propose: click, type, navigate         │
├─────────────────────────────────────────────────────┤
│ Layer 2: TARGET RESOLUTION                          │
│   ▶ 将 @eN ref 解析为可见信息：                      │
│   ▶ - 元素文本内容（innerText）                       │
│   ▶ - 元素标签名 + 属性摘要（tagName, type, href）    │
│   ▶ - 元素在页面中的位置描述（"near heading X"）       │
│   ▶ - 元素截图裁剪（可选，视觉确认）                  │
├─────────────────────────────────────────────────────┤
│ Layer 3: USER CONFIRMATION                           │
│   ▶ 展示解析后的目标信息给用户                        │
│   ▶ click：一次确认（看到目标描述 + 页面快照）         │
│   ▶ type：二次确认（看到目标 input + 要输入的文本）    │
│   ▶ 用户 Allow / Deny                               │
├─────────────────────────────────────────────────────┤
│ Layer 4: PRE-ACTION SNAPSHOT                        │
│   ▶ 在用户批准后、执行前，捕获即时快照                 │
│   ▶ 验证 ref 仍然有效（元素存在）                     │
│   ▶ 如果 ref 失效→返回 failed + pre-action snapshot │
├─────────────────────────────────────────────────────┤
│ Layer 5: EXECUTION                                  │
│   ▶ 通过 Electron IPC 执行真实操作                   │
│   ▶ click: webContents.sendInputEvent               │
│   ▶ type: webContents.sendInputEvent + insertText   │
│   ▶ 记录执行时间、结果                               │
├─────────────────────────────────────────────────────┤
│ Layer 6: POST-ACTION SNAPSHOT                       │
│   ▶ 操作后立即捕获页面快照                            │
│   ▶ 与 pre-action snapshot 对比（可选 diff）          │
│   ▶ 写入 action log                                 │
└─────────────────────────────────────────────────────┘
```

### 2.2 安全模型核心原则

1. **用户必须知道 Agent 要操作什么。** `@e5` 不够——必须解析为人类可读的描述。
2. **操作前后状态必须可审计。** pre + post snapshot 形成完整证据链。
3. **ref 不是可信的持久引用。** 每次执行前必须验证 ref 仍然有效。
4. **type 需要比 click 更严格的确认。** 用户必须看到要输入的完整文本。
5. **eval 永远不允许在 Desktop 上执行。** 没有安全边际。

---

## 3. BrowserActionRequest 需要补哪些字段

### 3.1 当前 `BrowserActionRequest`（Phase 1）

```typescript
// apps/desktop/src/app/browser-runtime/types.ts:401-429
export interface BrowserActionRequest {
  requestId: string
  requestedAt: string
  actor: BrowserActor
  taskId: string
  action: BrowserActionKind
  reason?: string
  targetProvider?: BrowserProviderId
}
```

### 3.2 需要新增的字段（Phase 2D 设计）

```typescript
/**
 * Fields added in Phase 2D to make click/type safety-reviewable.
 *
 * NONE of these change the existing Phase 1/2A/2B/2C behaviour.
 * They are optional on BrowserActionRequest — providers that don't
 * need them (headless, cloud) ignore them.  DesktopVisibleProvider
 * populates them at proposal time and reads them at execution time.
 */
interface BrowserActionSafetyContext {
  // ── Page identity at proposal time ───────────────────────────────
  /**
   * The page URL when the action was proposed.
   * Used at execution time to verify the user hasn't navigated away.
   */
  originUrl: string

  /**
   * The page title when the action was proposed.
   * Shown in approval UI for context.
   */
  originTitle: string

  // ── Target element resolution ────────────────────────────────────
  /**
   * Human-readable description of the target element, resolved from
   * the @eN ref at proposal time.
   *
   * Example (click):
   *   "button 'Submit PR' (tag: button, type: submit)
   *    near heading 'Create Pull Request'"
   *
   * Example (type):
   *   "input field 'Search' (tag: input, type: text, placeholder: 'Search...')
   *    inside form 'nav-search'"
   */
  targetDescription: string

  /**
   * The ref ID from the aria/accessibility snapshot (e.g. "@e5").
   * Carried through for execution — the executor re-resolves it
   * against the live page.
   */
  targetRef: string

  /**
   * For `type` actions: the full text the agent wants to type.
   * Displayed verbatim in the approval UI for user review.
   * Max 500 chars.  Longer text is clipped with a warning.
   */
  typeText?: string

  // ── Element identity for ref validation ──────────────────────────
  /**
   * Element selector hints used at execution time to validate that
   * the target element is still the one the agent intended.
   *
   * These are captured at proposal time from the live DOM via
   * `executeJavaScript`.  At execution time they are re-read and
   * compared.  If the text or attributes have changed materially,
   * the executor returns `failed` with a diff.
   */
  elementFingerprint?: {
    /** element.tagName at proposal time */
    tagName: string
    /** element.textContent trimmed to 200 chars */
    textContent: string
    /** element.id if present */
    id: string | null
    /** element.getAttribute('name') if present */
    name: string | null
    /** element.getAttribute('type') if present (for <input>) */
    inputType: string | null
    /** element.getAttribute('aria-label') if present */
    ariaLabel: string | null
    /** element.getBoundingClientRect() → { x, y, w, h } at proposal time */
    rect: { x: number; y: number; w: number; h: number }
  }

  // ── Risk classification ──────────────────────────────────────────
  /**
   * Conservative risk level assigned by the system at proposal time.
   *
   * - `low`: click on a link, type into a search box
   * - `medium`: click on a button, type into a form field
   * - `high`: click on a submit/delete button, type into a payment/credential field
   *
   * The risk level drives UI treatment (color, extra confirmation).
   * Default: `medium`.
   */
  riskLevel: 'low' | 'medium' | 'high'
}
```

### 3.3 更新后的 `ClickAction` 和 `TypeAction`

```typescript
// 当前（Phase 1）:
export interface ClickAction {
  type: 'click'
  ref: string
}

export interface TypeAction {
  type: 'type'
  ref: string
  text: string
}

// Phase 2D 建议新增 optional safety field：
// 这两个 interface 不变。安全上下文通过 BrowserActionRequest
// 的 safetyContext? 字段携带，不破坏现有 action type 结构。
```

### 3.4 `BrowserActionRequest` 的最终形态

```typescript
export interface BrowserActionRequest {
  // ── Existing (Phase 1) ─────────────────────────────
  requestId: string
  requestedAt: string
  actor: BrowserActor
  taskId: string
  action: BrowserActionKind
  reason?: string
  targetProvider?: BrowserProviderId

  // ── New (Phase 2D) ─────────────────────────────────
  /**
   * Safety context for user-visible providers (Desktop).
   * Populated at proposal time by the provider adapter.
   * Absent for headless/cloud providers.
   */
  safetyContext?: BrowserActionSafetyContext
}
```

---

## 4. UI 确认设计

### 4.1 确认流程（click）

```
Agent proposes click(@e5)
        │
        ▼
DesktopVisibleProvider resolves @e5 in live DOM
→ targetDescription: "button 'Submit PR' near heading 'Create PR'"
→ elementFingerprint: { tagName: 'BUTTON', textContent: 'Submit PR', ... }
        │
        ▼
PendingActionCard 显示:
  ┌─────────────────────────────────────────────┐
  │ 🖱 Agent wants to click                      │
  │                                             │
  │ Target: button "Submit PR"                  │
  │   tag: BUTTON, type: submit                 │
  │   near: heading "Create Pull Request"       │
  │                                             │
  │ Page: https://github.com/gu/trendradar/...  │
  │ Reason: Agent wants to submit the PR form   │
  │ Risk: ⚠ MEDIUM                              │
  │                                             │
  │ [👁 Preview page]  [✓ Allow]  [✗ Deny]     │
  └─────────────────────────────────────────────┘
```

### 4.2 确认流程（type）

type 需要 **二次确认**：第一次确认目标 input，第二次确认文本内容。

```
Agent proposes type(@e3, "fix: update dependencies to v3.2.1")
        │
        ▼
PendingActionCard 显示:
  ┌─────────────────────────────────────────────┐
  │ ⌨ Agent wants to type                       │
  │                                             │
  │ Target: input field "PR Title"              │
  │   tag: INPUT, type: text                    │
  │   placeholder: "Enter PR title"             │
  │   inside: form near heading "Create PR"     │
  │                                             │
  │ Text to type:                               │
  │ ┌─────────────────────────────────────────┐ │
  │ │ fix: update dependencies to v3.2.1      │ │
  │ └─────────────────────────────────────────┘ │
  │                                             │
  │ Page: https://github.com/gu/trendradar/...  │
  │ Reason: Agent wants to fill the PR title    │
  │ Risk: ⚠ MEDIUM                              │
  │                                             │
  │ [✓ Allow]  [✗ Deny]                        │
  └─────────────────────────────────────────────┘
```

### 4.3 元素高亮方案

**MVP 方案**：在 `captureScreenshot` 返回的截图上，用红色半透明框标记目标元素的位置（使用 `elementFingerprint.rect`）。

```
┌──────────────────────────────────┐
│                                  │
│   Create Pull Request            │
│                                  │
│  ┌──────────────────────────┐    │
│  │ PR Title: [____________] │    │  ← 红色虚线框标记 type 目标
│  └──────────────────────────┘    │
│                                  │
│  ┌──────────┐                    │
│  │ Submit PR│ ← 红色高亮标记     │  ← 红色虚线框标记 click 目标
│  └──────────┘                    │
│                                  │
└──────────────────────────────────┘
```

**实现**：在 `PendingActionCard` 中展示截图 thumbnail，Canvas overlay 绘制框。不侵入 WebContents。

**MVP 可以不实现高亮**，先依赖文本描述（`targetDescription`）。高亮是 UX 改进而不是安全门控。

### 4.4 风险级别视觉区分

| 风险 | 颜色 | 额外确认 |
|------|------|---------|
| `low` | 绿色/灰色 | 无 |
| `medium` | 黄色/amber | 无（MVP） |
| `high` | 红色 | **二次确认 dialog**："This is a high-risk action. Are you sure?" |

---

## 5. 执行前后 Snapshot

### 5.1 Pre-action Snapshot

```typescript
/**
 * Captured IMMEDIATELY before executing a click/type action,
 * after user approval and before IPC call.
 */
interface PreActionVerification {
  /** Timestamp just before execution. */
  verifiedAt: string

  /** The page URL at execution time. */
  currentUrl: string

  /** Whether the target ref is still valid. */
  refValid: boolean

  /**
   * If refValid is false, why the ref was invalidated:
   * - "element_removed" — element no longer in DOM
   * - "text_changed" — element text differs from fingerprint
   * - "navigation" — page URL changed since proposal
   * - "page_unloaded" — page is no longer the active tab
   */
  invalidationReason?: string

  /**
   * Current element fingerprint at execution time.
   * Compared against safetyContext.elementFingerprint.
   */
  currentFingerprint?: ElementFingerprint

  /**
   * Snapshot of the page before the action.
   * Always captured regardless of ref validity.
   */
  snapshot: BrowserSnapshot
}
```

### 5.2 Post-action Snapshot

```typescript
/**
 * Captured IMMEDIATELY after executing a click/type action.
 * Stored in BrowserActionResult.postActionSnapshot.
 */
// Already exists in BrowserActionResult:
//   postActionSnapshot?: BrowserSnapshot

// Phase 2D adds a pre-action snapshot for comparison:
interface BrowserActionResult {
  // ... existing fields ...

  /**
   * Pre-action verification snapshot + ref validation.
   * NEW in Phase 2D — only populated for click/type on Desktop.
   */
  preActionVerification?: PreActionVerification
}
```

### 5.3 Snapshot Timeline

```
User Allow click(@e5)
        │
        ▼  t=0ms
capture pre-action snapshot + validate ref
        │
        ├─ ref invalid → return { status: "failed", error: "Element removed" }
        │
        ▼  t≈50ms  ref valid
execute click via IPC (webContents.sendInputEvent)
        │
        ▼  t≈100ms
wait for page to start responding (~200ms or did-navigate event)
        │
        ▼  t≈300ms
capture post-action snapshot
        │
        ▼
return { status: "executed", preActionVerification, postActionSnapshot }
```

---

## 6. 失败记录

### 6.1 失败分类

| 失败类型 | `status` | `error` | 何时发生 |
|---------|----------|---------|---------|
| `ref_expired` | `failed` | "Target element @e5 no longer exists on the page" | pre-action ref 验证失败 |
| `ref_text_mismatch` | `failed` | "Target element text changed from 'Submit PR' to 'Delete PR'" | pre-action fingerprint 不匹配 |
| `navigation_occurred` | `failed` | "Page navigated from https://... to https://... since proposal" | pre-action URL 检查失败 |
| `execution_timeout` | `failed` | "Click did not produce a page response within 5s" | 操作后页面无响应 |
| `ipc_error` | `failed` | "IPC call failed: <Electron error>" | IPC 调用异常 |
| `bridge_unavailable` | `failed` | "Desktop browser bridge is unavailable" | bridge 不存在 |
| `action_denied_by_user` | `denied` | "User denied the action" | 用户点 Deny |
| `action_denied_by_policy` | `denied` | "Action 'eval' is blocked by desktop-visible policy" | policy 拒绝 |

### 6.2 Action Log 记录内容

每条 log entry（`BrowserActionResult`）包含：
- `requestId` — 可追溯到原始 `BrowserActionRequest`
- `status` — executed / denied / failed
- `error` — 失败原因（英文，agent 可理解）
- `executedAt` — 时间戳
- `executedBy` — provider + sessionKey
- `preActionVerification` — 操作前快照 + ref 验证（新增）
- `postActionSnapshot` — 操作后页面状态

---

## 7. 仍然禁止的 Action

### 7.1 永久禁止列表（Desktop）

| Action | 决策 | 理由 |
|--------|------|------|
| `eval` | **永久 deny** | 在用户登录的页面上执行任意 JS——安全边界不可接受。Agent 已经可以通过 agent-browser 在自己的 headless 实例中 eval。 |
| `press_key` | **永久 deny** | `Enter` 可以提交表单，`Tab` 可以切换焦点。等同于 click + type 的组合，且更不透明。 |
| `scroll` | **deny（Desktop 上）** | Desktop 浏览器是用户主导的。Agent 不应在用户可见窗口自动滚动——会让用户困惑。Agent 可以 snapshot 后在自己的 headless 中 scroll。 |
| `console(expression=...)` | **永久 deny** | 等同于 eval。只允许 `console(clear=true)` 读取 console 输出。 |

### 7.2 未来可能开放列表（需进一步安全设计）

| Action | 条件 |
|--------|------|
| `scroll` | 只有当用户显式启用 "允许 Agent 自动滚动" 设置时 |
| `press_key` | 只有当 target 是明确的非提交 input（如搜索框），且 key 不是 Enter |

### 7.3 MVP（Phase 2E-2F）支持范围

| Action | Phase 2E (MVP) | 备注 |
|--------|---------------|------|
| `click` | ✅ | 含 full safety model（target resolution + pre-action ref 验证 + post-action snapshot） |
| `type` | ✅ | 含 full safety model + 二次文本确认 |
| `navigate` | ✅ | 已在 Phase 2C 支持 |
| `snapshot` | ✅ | 已在 Phase 2A 支持 |
| `back` | ❌ | 暂不支持——Desktop 上 back 是用户导航操作 |
| `scroll` | ❌ | 见上 |
| `press_key` | ❌ | 见上 |
| `eval` | ❌ | 永久 deny |
| `vision` | ❌ | Desktop 已有 getScreenshot，vision 是 agent-browser 的多模态分析——Desktop 不需要 |
| `get_images` | ❌ | 可通过 DOM script 在 snapshot 中间接获取 |
| `console` | ❌ | Desktop WebContents 的 console 输出不暴露给 renderer（安全考虑） |

---

## 8. 实施计划

### Phase 2D：Safety Design（本文档）

- ✅ 产出本设计文档
- ✅ 更新 `types.ts` 增加 `BrowserActionSafetyContext` 和 `ElementFingerprint` 类型
- ✅ 更新 `BrowserActionRequest` 增加 `safetyContext?` 字段
- ✅ 更新 `DesktopVisibleProvider` 的 policy 声明
- ✅ 更新大一统文档的 Phase 2D 状态
- ✅ 添加 contract-level tests
- ❌ 不写执行代码

### Phase 2E：Target Resolution + Element Fingerprint（后续）

- 在 `DesktopVisibleProvider` 中实现 ref → element fingerprint 解析
- 通过 `webContents.executeJavaScript()` 读取目标元素的 tagName/textContent/rect/attributes
- 生成 `targetDescription` 人类可读文本
- 更新 `PendingActionCard` UI 显示解析后的目标信息

### Phase 2F：Click/Type Execution（后续）

- 在 Electron `main.cjs` 中新增两个 IPC handler：
  - `hermes:browser:click-element` — 接收 element selector + fingerprint，执行 `sendInputEvent`
  - `hermes:browser:type-text` — 接收 element selector + text + fingerprint，执行焦点+输入
- 在 `DesktopVisibleProvider` 中实现 pre-action ref 验证 + post-action snapshot
- 更新 `PendingActionCard` UI 显示风险级别和二次确认

---

## 9. 测试计划

### 9.1 Contract-level tests（Phase 2D，本文档范围内）

新增测试文件 `desktop-visible-provider.test.ts` 中增加：

```
describe('BrowserActionSafetyContext', () => {
  it('has all required fields for click safety')
  it('has typeText for type actions')
  it('riskLevel defaults to medium')
  it('elementFingerprint captures tagName, textContent, rect')
})

describe('Desktop policy — click/type/eval', () => {
  it('click requires approval for agent')
  it('type requires approval for agent')
  it('eval is permanently denied for agent')
  it('press_key is permanently denied for agent')
})
```

新增测试文件 `types.test.ts` 中增加：

```
describe('Phase 2D types', () => {
  it('BrowserActionRequest accepts optional safetyContext')
  it('BrowserActionSafetyContext has originUrl and targetDescription')
  it('ElementFingerprint has tagName, textContent, rect')
})
```

### 9.2 后续实现阶段的测试（Phase 2E-2F，不在本文档范围内）

- `desktop-visible-provider.test.ts`：mock `executeJavaScript` 返回值，验证 target resolution
- `action-gateway.test.ts`：完整 propose → resolve → approve → execute → snapshot 生命周期
- `main.cjs` IPC test：验证 `hermes:browser:click-element` 和 `hermes:browser:type-text` IPC handler

---

## 10. 类型定义变更清单

### 10.1 `types.ts` 新增

```typescript
// ═══════════════════════════════════════════════════════════════════════════
// 10. Phase 2D — Desktop Agent Action Safety
// ═══════════════════════════════════════════════════════════════════════════

/** Risk level for a proposed browser action. */
export type BrowserActionRiskLevel = 'low' | 'medium' | 'high'

/** Element identity fingerprint captured at proposal time. */
export interface ElementFingerprint {
  tagName: string
  textContent: string
  id: string | null
  name: string | null
  inputType: string | null
  ariaLabel: string | null
  rect: { x: number; y: number; w: number; h: number }
}

/** Safety context for user-visible providers. */
export interface BrowserActionSafetyContext {
  originUrl: string
  originTitle: string
  targetDescription: string
  targetRef: string
  typeText?: string
  elementFingerprint?: ElementFingerprint
  riskLevel: BrowserActionRiskLevel
}

/** Captured immediately before executing a click/type action. */
export interface PreActionVerification {
  verifiedAt: string
  currentUrl: string
  refValid: boolean
  invalidationReason?: string
  currentFingerprint?: ElementFingerprint
  snapshot: BrowserSnapshot
}
```

### 10.2 `BrowserActionRequest` 更新

```typescript
export interface BrowserActionRequest {
  // ... existing fields ...
  safetyContext?: BrowserActionSafetyContext  // NEW
}
```

### 10.3 `BrowserActionResult` 更新

```typescript
export interface BrowserActionResult {
  // ... existing fields ...
  preActionVerification?: PreActionVerification  // NEW
}
```

---

## 附录 A：与 `browser_tool.py` 的对比

| 方面 | `browser_tool.py` (agent-browser headless) | Desktop (Phase 2D design) |
|------|-------------------------------------------|--------------------------|
| click 执行 | `agent-browser click @e5` → CDP `Input.dispatchMouseEvent` | `webContents.sendInputEvent({ type: 'mouseDown', ... })` |
| type 执行 | `agent-browser fill @e3 "text"` → CDP `Input.insertText` | `webContents.sendInputEvent({ type: 'keyDown', ... })` + `insertText` |
| ref 来源 | `agent-browser snapshot` → aria tree @eN | 不适用——Desktop 无 accessibility tree。需要 `executeJavaScript` 手动解析。 |
| 安全门控 | 无。Agent 在自己的 headless 中自由操作。 | 用户审批 + ref 验证 + pre/post snapshot |
| eval | `browser_console(expression=...)` → `Runtime.evaluate` | 永久禁止 |
| 可见性 | headless | 用户可见 |

**关键差异**：agent-browser 的 headless Chromium 是 Agent 独占的——没有用户登录态，没有用户数据。Desktop WebContentsView 是用户共享的——有用户 cookie/session。这就是为什么 Desktop 需要安全模型而 headless 不需要。

---

## 附录 B：修改文件清单（本文档范围内）

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/architecture/desktop-browser-agent-action-safety.md` | **新建** | 本文档 |
| `docs/architecture/browser-runtime-provider-unification.md` | **更新** | 补 Phase 2D 状态 |
| `apps/desktop/src/app/browser-runtime/types.ts` | **更新** | 新增 `BrowserActionSafetyContext`, `ElementFingerprint`, `PreActionVerification`；`BrowserActionRequest` 加 `safetyContext?`；`BrowserActionResult` 加 `preActionVerification?` |
| `apps/desktop/src/app/browser-runtime/types.test.ts` | **更新** | 新增 contract-level tests |
| `apps/desktop/src/app/browser-runtime/desktop-visible-provider.ts` | **更新** | 更新 policy（声明 eval/press_key 永久 deny） |
| `apps/desktop/src/app/browser-runtime/desktop-visible-provider.test.ts` | **更新** | 新增 policy 测试 |
