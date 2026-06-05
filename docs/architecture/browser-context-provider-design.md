# Hermes BrowserContextProvider — Adapter Design

Date: 2026-06-06
Status: Architecture design (read-only, no implementation commitment)
Based on:
- [Browser Workspace MVP Evaluation](../research/browser-workspace-mvp-evaluation.md)
- [Embedded Browser Workspace v0.1 Spec](../research/browser-workspace-embedded-mvp-spec.md)
- [Embedded Browser Workspace PoC Plan](../research/browser-workspace-embedded-poc-plan.md)
- [Embedded Browser Workspace PoC Results](../research/browser-workspace-embedded-poc-results.md)

---

## 1. Product Boundary

### What this document defines

This document defines the **BrowserContextProvider** — the single interface
through which the Hermes Agent reads browser context. It is the adapter
boundary between Hermes runtime and the embedded browser engine.

The PoC proved the embedded browser is feasible. This document defines the
contract for making it production-grade — without writing production code.

### Core design decisions (carried forward from spec)

| Decision | Source |
|----------|--------|
| Embedded browser is primary path | MVP Evaluation § Embedded vs External |
| External browser adapter is fallback only | MVP Evaluation |
| Read-only Agent boundary for MVP | MVP Spec § 7 |
| Hermes-native plugin layer, not Chrome extensions | MVP Spec § 6 |
| Right rail placement in Hermes Desktop | MVP Spec § 2 |
| Built-in static scripts for DOM/selection extraction | PoC Results § 5 |
| Future actions must be approval-gated | MVP Spec § 8 |

### What BrowserContextProvider is not

- It is not a browser-automation API (no Playwright/Puppeteer semantics).
- It is not a general-purpose web scraping interface.
- It is not a user-facing UI component — it is a data contract.
- It is not a plugin runtime — it calls plugins, but plugins are defined separately.

---

## 2. Architecture Overview

```text
┌── Hermes Desktop ──────────────────────────────────────────────────┐
│                                                                      │
│  ┌─ Chat ──────────┐  ┌─ Agent Run ──────┐  ┌─ Right Rail ────────┐│
│  │                  │  │                  │  │  Files | Diff       ││
│  │  User types.     │  │  Agent reads     │  │  Logs  | Artifacts  ││
│  │  Agent responds. │  │  context, plans, │  │        | Browser ◀──││
│  │                  │  │  executes tools. │  │                     ││
│  │                  │  │       │          │  │  ┌─ Browser ──────┐ ││
│  │                  │  │       │ reads    │  │  │ URL bar        │ ││
│  │                  │  │       ▼          │  │  │ WebContents    │ ││
│  │                  │  │  ┌────────────┐  │  │  │ Context panel  │ ││
│  │                  │  │  │ Browser    │  │  │  └───────────────┘ ││
│  │                  │  │  │ Context    │  │  │                     ││
│  │                  │  │  │ Provider   │◄─┼──┤                     ││
│  │                  │  │  │ (adapter)  │  │  │                     ││
│  │                  │  │  └─────┬──────┘  │  │                     ││
│  │                  │  │        │         │  │                     ││
│  │                  │  │        ▼         │  │                     ││
│  │                  │  │  ┌────────────┐  │  │                     ││
│  │                  │  │  │ Browser    │  │  │                     ││
│  │                  │  │  │ Workspace  │  │  │                     ││
│  │                  │  │  │ Service    │  │  │                     ││
│  │                  │  │  └─────┬──────┘  │  │                     ││
│  │                  │  │        │         │  │                     ││
│  └──────────────────┘  └──────┬─┼─────────┘  └─────────────────────┘│
│                               │ │                                    │
│                               ▼ ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Embedded Browser Session                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │   │
│  │  │ Electron │  │ Browser  │  │ Tab      │  │ Profile       │ │   │
│  │  │ WebContents│  │ Windows  │  │ Manager  │  │ (~/.hermes/  │ │   │
│  │  │ View     │  │          │  │          │  │  browser/)    │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └───────────────┘ │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  Plugin Layer                                             │  │   │
│  │  │  github-pr │ github-issue │ chatgpt-conversation │ ...    │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  Evidence / Snapshot / Events                             │  │   │
│  │  │  Screenshots │ Snapshots │ DOM extracts │ Event log       │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer | Responsibility |
|-------|---------------|
| **BrowserContextProvider** | Data contract. Exposes read-only methods to Agent. Enforces size/clip/redact limits. Dispatches to BrowserWorkspaceService. |
| **BrowserWorkspaceService** | Lifecycle. Manages BrowserWindows, TabManager, Profile, proxy config, plugin registry, event bus. |
| **Embedded Browser Session** | Rendering engine. Electron WebContentsView. Handles `getURL()`, `getTitle()`, `capturePage()`, static `executeJavaScript()`. |
| **Plugin Layer** | Context enrichment. Matches URL patterns, extracts structured page-type context. |
| **Evidence / Events** | Observability. Snapshots, screenshots, event log. Feeds debug panel and timeline. |

---

## 3. BrowserContextProvider Interface

This is a TypeScript contract, not implementation code. It defines the single
boundary through which the Agent reads browser context.

```typescript
/**
 * BrowserContextProvider
 *
 * The ONLY interface through which the Hermes Agent reads browser context.
 * All methods are read-only. No action methods (click, type, submit,
 * navigate) are exposed here.
 */

interface BrowserContextProvider {
  // ── Snapshot ────────────────────────────────────────────────────

  /** Full structured snapshot of the current browser state. */
  getCurrentSnapshot(): Promise<BrowserContextSnapshot>;

  // ── Tabs ────────────────────────────────────────────────────────

  /** List all open tabs with metadata. */
  getTabs(): Promise<TabInfo[]>;

  /** Get the currently active tab. */
  getActiveTab(): Promise<TabInfo>;

  // ── Screenshot ──────────────────────────────────────────────────

  /**
   * Capture a screenshot of the current active tab.
   * Returns a file reference or base64 data URI.
   */
  captureScreenshot(options?: ScreenshotOptions): Promise<ScreenshotResult>;

  // ── Text extraction ─────────────────────────────────────────────

  /**
   * Extract readable DOM text via built-in static script.
   * Max 20 KB, clipped.
   */
  getReadableText(tabId?: string): Promise<string>;

  /**
   * Extract user-selected text via built-in static script.
   * Returns empty string if nothing is selected.
   * Max 10 KB, clipped.
   */
  getSelectedText(tabId?: string): Promise<string>;

  /**
   * Preview current system clipboard text.
   * Returns empty string if clipboard is empty or disabled.
   * Max 2 KB, clipped.
   */
  getClipboardPreview(): Promise<string>;

  // ── Events ──────────────────────────────────────────────────────

  /** Get recent browser events (last N, default 20). */
  getRecentEvents(limit?: number): Promise<BrowserEvent[]>;

  // ── Event subscription ──────────────────────────────────────────

  /**
   * Subscribe to browser events.
   * Returns an unsubscribe function.
   * Events are delivered as push notifications, not polling.
   */
  subscribeToBrowserEvents(
    handler: (event: BrowserEvent) => void,
    filter?: EventFilter
  ): () => void;
}

/**
 * Methods intentionally NOT exposed in MVP.
 * These may appear in a future Approval-gated ActionProvider,
 * not in BrowserContextProvider.
 */
type NotInMVP =
  | "click"
  | "type"
  | "submit"
  | "navigateAsAgent"
  | "executeJavaScript(userProvidedCode)"
  | "sendInputEvent"
  | "dispatchInputEvent";
```

### Size limits

| Field | Max size | Source |
|-------|----------|--------|
| `getReadableText()` | 20 KB | `document.body.innerText` via static script |
| `getSelectedText()` | 10 KB | `window.getSelection().toString()` via static script |
| `getClipboardPreview()` | 2 KB | `clipboard.readText()` |
| `captureScreenshot()` | 500 KB image | `webContents.capturePage()` → PNG, max 1920px width |
| `getCurrentSnapshot()` total text | 100 KB | All text fields combined, excluding screenshot |

---

## 4. BrowserContextSnapshot Schema

```typescript
interface BrowserContextSnapshot {
  /** ISO 8601 timestamp of when this snapshot was captured. */
  capturedAt: string;

  /** Identifies the provider and mode. */
  source: {
    provider: "hermes-embedded-browser";
    mode: "read_only";
  };

  /** Hermes profile ID this browser workspace belongs to. */
  profileId: string;

  /** The currently active tab, with extracted context. */
  activeTab: ActiveTabContext;

  /** All open tabs (MVP: may be a single tab initially). */
  tabs: TabInfo[];

  /** Recent browser events (last 20). */
  recentEvents: BrowserEvent[];

  /** Plugin-extracted structured context. Null if no plugin matched. */
  pluginContext: Record<string, unknown> | null;

  /** What permissions are currently in effect for this snapshot. */
  permissions: {
    clipboardRead: boolean;
    selectedTextRead: boolean;
    domRead: boolean;
    screenshotCaptured: boolean;
  };

  /** Size limits applied to this snapshot. */
  limits: {
    maxDomChars: number;
    maxSelectionChars: number;
    maxClipboardChars: number;
    maxTotalSnapshotBytes: number;
    actualTotalBytes: number;
  };
}

interface ActiveTabContext {
  /** Unique tab identifier. */
  id: string;

  /** Full URL of the active page. */
  url: string;

  /** Document title. */
  title: string;

  /**
   * Page type classification.
   * Set by plugin match or URL heuristic.
   * Examples: "github-pr", "chatgpt-conversation", "generic-web".
   */
  pageType: string | null;

  /** Whether the page is still loading. */
  isLoading: boolean;

  /** Whether the page has a back-history entry. */
  canGoBack: boolean;

  /** Whether the page has a forward-history entry. */
  canGoForward: boolean;

  /**
   * Reference to the captured screenshot.
   * May be a file path or a data URI, depending on storage config.
   */
  screenshotRef: string | null;

  /**
   * DOM text summary.
   * Extracted via built-in static executeJavaScript script.
   * Max 20 KB, clipped.
   */
  domSummary: string | null;

  /**
   * User-selected text on the page.
   * Extracted via built-in static executeJavaScript script.
   * Empty string if nothing is selected. Max 10 KB, clipped.
   */
  selectedText: string;

  /**
   * Preview of current system clipboard contents.
   * Empty string if clipboard is empty or clipboardRead permission is off.
   * Max 2 KB, clipped.
   */
  clipboardTextPreview: string;
}

interface TabInfo {
  id: string;
  url: string;
  title: string;
  active: boolean;
  isLoading: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  favicon?: string;
}

interface ScreenshotOptions {
  /** Maximum width in pixels. Default 1920. */
  maxWidth?: number;
  /** Output format. Default "file". */
  format?: "file" | "dataUri";
}

interface ScreenshotResult {
  ref: string;         // file path or data URI
  width: number;
  height: number;
  sizeBytes: number;
  format: "png";
}
```

### Field notes

| Field | MVP | Post-MVP |
|-------|-----|----------|
| `pageType` | Plugin match or null | URL heuristic fallback |
| `pluginContext` | Only from first matching plugin | Plugin chain/composition |
| `screenshotRef` | File path under `~/.hermes/browser/screenshots/` | Configurable retention |
| `permissions.clipboardRead` | Always false until user opts in | Per-profile settings |
| `domSummary` | `document.body.innerText` only | Plugin-specific DOM parsers |

---

## 5. Browser Events

Events are emitted by the BrowserWorkspaceService and consumed by
`subscribeToBrowserEvents()`. They also feed the Agent timeline.

```typescript
type BrowserEvent =
  | BrowserOpenedEvent
  | TabCreatedEvent
  | TabActivatedEvent
  | TabClosedEvent
  | PageNavigationStartedEvent
  | PageNavigationCommittedEvent
  | PageTitleUpdatedEvent
  | PageLoadedEvent
  | SelectionChangedEvent
  | ClipboardCopiedEvent
  | ScreenshotCapturedEvent
  | ContextSnapshotCapturedEvent
  | PluginMatchedEvent
  | PluginExtractedEvent;

interface BaseEvent {
  /** ISO 8601 timestamp. */
  ts: string;
  /** Event type discriminator. */
  type: string;
}

interface BrowserOpenedEvent extends BaseEvent {
  type: "browser.opened";
  profileId: string;
}

interface TabCreatedEvent extends BaseEvent {
  type: "tab.created";
  tabId: string;
  url: string;
}

interface TabActivatedEvent extends BaseEvent {
  type: "tab.activated";
  tabId: string;
  previousTabId: string | null;
}

interface TabClosedEvent extends BaseEvent {
  type: "tab.closed";
  tabId: string;
}

interface PageNavigationStartedEvent extends BaseEvent {
  type: "page.navigation.started";
  tabId: string;
  url: string;
}

interface PageNavigationCommittedEvent extends BaseEvent {
  type: "page.navigation.committed";
  tabId: string;
  url: string;
}

interface PageTitleUpdatedEvent extends BaseEvent {
  type: "page.title.updated";
  tabId: string;
  title: string;
}

interface PageLoadedEvent extends BaseEvent {
  type: "page.loaded";
  tabId: string;
  url: string;
}

interface SelectionChangedEvent extends BaseEvent {
  type: "selection.changed";
  tabId: string;
  hasSelection: boolean;
  /** Length of selected text (not the text itself, for event size). */
  selectionLength: number;
}

interface ClipboardCopiedEvent extends BaseEvent {
  type: "clipboard.copied";
  /** Length of clipboard content (not the content itself). */
  contentLength: number;
}

interface ScreenshotCapturedEvent extends BaseEvent {
  type: "screenshot.captured";
  tabId: string;
  ref: string;
  sizeBytes: number;
}

interface ContextSnapshotCapturedEvent extends BaseEvent {
  type: "context.snapshot.captured";
  snapshotId: string;
  tabId: string;
  url: string;
}

interface PluginMatchedEvent extends BaseEvent {
  type: "plugin.matched";
  tabId: string;
  pluginId: string;
  url: string;
}

interface PluginExtractedEvent extends BaseEvent {
  type: "plugin.extracted";
  tabId: string;
  pluginId: string;
  contextKeys: string[];
}
```

### Event scope

Events are **workspace-scoped**: they apply to the current tab unless a
`tabId` is specified. The Agent subscribes to events for the active
workspace.

---

## 6. Storage / Profile Design

### Recommended production path

```
~/.hermes/browser/
```

Per Hermes profile (future):

```
~/.hermes/profiles/{profile_id}/browser/
```

### Storage layout

```
~/.hermes/browser/
  Default/                  ← Chromium profile data
    Cookies
    Local Storage/
    Session Storage/
    IndexedDB/
    Cache/
    Code Cache/
    Preferences
    Secure Preferences
    TransportSecurity
    Trust Tokens/
  screenshots/              ← Temporary screenshot storage
    {timestamp}_{tabId}.png
  snapshots/                ← Optional persistent snapshot storage
    {timestamp}_{snapshotId}.json
  downloads/
  plugins/
    manifest.json           ← Plugin registry
    github-pr.js
    github-issue.js
    chatgpt-conversation.js
```

### Retention policy

| Data | Retention | Reasoning |
|------|-----------|-----------|
| Cookies / Local Storage / IndexedDB | Persistent | Required for login state persistence |
| Session Storage | Session only | Standard Chromium behavior |
| Cache | Persistent, Chromium-managed | Performance |
| Screenshots | Last 10 per workspace, evict oldest | Disk usage; 10 screenshots at ~500 KB ≈ 5 MB max |
| Snapshots (JSON) | In-memory only, not persisted to disk | Privacy; only captured-on-demand |
| Evidence (PoC only) | `/tmp/`, not production | PoC traceability; not a production feature |
| Downloads | User-managed | Standard browser behavior |

### What is NOT stored in production

- Raw DOM text dumps longer than the Agent context window.
- Clipboard history.
- Full-page HTML.
- Screenshots older than the retention window.
- Selection text history.

---

## 7. Proxy Design

### Three modes

```typescript
type ProxyMode = "system" | "direct" | "custom";

interface ProxyConfig {
  mode: ProxyMode;
  /** Only when mode = "custom" */
  customRules?: string;       // e.g. "http://127.0.0.1:7890"
  /** Only when mode = "custom" */
  customBypassRules?: string; // e.g. "<local>, *.internal"
}
```

| Mode | Behavior | Use case |
|------|----------|----------|
| `system` | Inherit macOS system proxy (default). Chromium reads system proxy settings automatically. | User has Clash/Surge/Mihomo running; embedded browser follows automatically. |
| `direct` | No proxy. Direct connection. | User is on a direct network or wants to bypass proxy for specific reasons. |
| `custom` | Use `proxyRules` set on a dedicated session partition. Supports `http://`, `socks5://`, bypass rules. | User wants the embedded browser to use a specific proxy that differs from the system proxy. |

### What Hermes does NOT do

- Hermes does not implement a VPN or proxy server.
- Hermes does not detect Clash/Surge/Mihomo state.
- Hermes does not auto-switch proxy based on target URL.
- Hermes does not modify system proxy settings.

The proxy mode is a Hermes user preference. The actual proxy routing is
determined by the external tool running on the user's machine.

---

## 8. Hermes-native Plugin Layer

### Purpose

Plugins upgrade the generic `domSummary` into structured, page-type-aware
context. They are registered by URL pattern and run inside the renderer with
read-only WebContents access.

### Plugin registry (MVP)

| Plugin ID | URL Pattern | Context Extracted | Priority |
|-----------|-------------|-------------------|----------|
| `github-pr` | `github.com/*/pull/*` | PR title, author, base/head, changed files, CI status | MVP |
| `github-issue` | `github.com/*/issues/*` | Issue title, author, labels, assignees, status | MVP |
| `chatgpt-conversation` | `chatgpt.com/*` | Conversation title, message count, visible message preview | MVP |
| `vercel-deployment` | `vercel.com/*` | Deployment ID, status, build log summary | Future |
| `linear-issue` | `linear.app/*` | Issue ID, title, description, assignee, status | Future |
| `feishu-doc` | `*.feishu.cn/*` | Document title, content summary | Future |

### Plugin interface

```typescript
interface BrowserPlugin {
  /** Unique plugin identifier. */
  id: string;

  /** Human-readable name. */
  name: string;

  /** URL glob patterns this plugin applies to. */
  patterns: string[];

  /**
   * Called on page-load-complete. Returns true if this plugin can
   * extract context from the current page.
   */
  match(url: string, title: string): boolean;

  /**
   * Extract structured context from the active tab.
   * Receives the raw snapshot as input; returns plugin-specific output.
   */
  extract(input: PluginExtractInput): Promise<PluginExtractOutput>;

  /** Max characters of plugin output that may be injected into prompt. */
  maxOutputChars: number;

  /** Fields to redact before injecting into Agent prompt. */
  redactionRules?: RedactionRule[];
}

interface PluginExtractInput {
  tabId: string;
  url: string;
  title: string;
  domSummary: string;
  selectedText: string;
  clipboardTextPreview: string;
  screenshotRef: string | null;
}

interface PluginExtractOutput {
  /** Structured context specific to this page type. */
  context: Record<string, unknown>;

  /** Human-readable summary (max 500 chars). */
  summary: string;

  /** The page type classification. */
  pageType: string;
}

type RedactionRule =
  | { field: string; strategy: "strip" }
  | { field: string; strategy: "replace"; replacement: string };
```

### Plugin lifecycle

1. On `page.loaded` event, the plugin registry evaluates all registered
   plugins against the current URL.
2. For each plugin where `match(url, title)` returns true (first match wins):
   - Emit `plugin.matched` event.
   - Call `extract()` with the current snapshot input.
   - Emit `plugin.extracted` event with extracted keys.
   - Set `activeTab.pageType` and `snapshot.pluginContext`.
3. If no plugin matches, `pageType` is `null` and `pluginContext` is `null`.
   The generic `domSummary` is still populated.

### Plugin vs Chrome Extension

Hermes-native plugins are NOT Chrome extensions. They are:

- Bundled with Hermes Desktop (or user-installed via Hermes plugin system).
- Written in TypeScript/JS, running in the Electron renderer.
- Limited to the Hermes Plugin API — no access to Chrome Extension APIs.
- Not distributed through the Chrome Web Store.

---

## 9. Read-only Boundary

### The rule

> The Agent reads browser context through `BrowserContextProvider` only.
> There is no code path from Agent intent to browser action in MVP.

### What the Agent can do (MVP)

| Method | Returns | Notes |
|--------|---------|-------|
| `getCurrentSnapshot()` | `BrowserContextSnapshot` | Full structured snapshot |
| `getTabs()` | `TabInfo[]` | Tab metadata only |
| `getActiveTab()` | `TabInfo` | Single tab metadata |
| `captureScreenshot()` | `ScreenshotResult` | PNG file ref or data URI |
| `getReadableText(tabId?)` | `string` | 20 KB max, clipped |
| `getSelectedText(tabId?)` | `string` | 10 KB max, clipped |
| `getClipboardPreview()` | `string` | 2 KB max, clipped |
| `getRecentEvents(limit?)` | `BrowserEvent[]` | Last N events |
| `subscribeToBrowserEvents(handler, filter?)` | `unsubscribe()` | Push-based event stream |

### What the Agent CANNOT do (MVP)

- `navigate(url)` — no programmatic navigation.
- `click(selector)` — no UI interaction.
- `type(selector, text)` — no text input.
- `submit()` — no form submission.
- `executeJavaScript(userCode)` — no user/Agent-provided script execution.
- `sendInputEvent()` — no keyboard/mouse event injection.
- `closeTab()`, `newTab()`, `switchTab()` — no tab management.

### `executeJavaScript` constraint

`executeJavaScript` is used ONLY for built-in static scripts with zero
parameters:

- `EXTRACT_DOM_SCRIPT` — `document.body.innerText`, clip to 3000 (PoC) / 20 KB (production).
- `EXTRACT_SELECTION_SCRIPT` — `window.getSelection().toString()`, clip to 3000 (PoC) / 10 KB (production).
- Plugin extraction scripts — registered at build time, not user-supplied.

No user or Agent input ever reaches `executeJavaScript`. No dynamic code
generation, no `eval`, no `new Function`.

---

## 10. Approval-gated Future Actions

Future versions may introduce browser actions (click, type, navigate). These
are NOT part of the BrowserContextProvider. They belong in a separate
**ActionProvider** interface with an explicit approval gate.

### Proposed action model

```typescript
/**
 * Future: ActionProvider (NOT in MVP).
 * Separated from BrowserContextProvider to keep read-only boundary clean.
 */

interface ActionProposal {
  id: string;
  type: "click" | "type" | "navigate" | "submit";
  target: {
    tabId: string;
    selector?: string;
    url?: string;
    text?: string;
  };
  reason: string;           // why the Agent is requesting this action
  proposedAt: string;       // ISO 8601
}

interface ActionResult {
  proposalId: string;
  status: "approved" | "rejected" | "executed" | "failed";
  executedAt?: string;
  error?: string;
  /** Screenshot of the page after the action, if executed. */
  postActionScreenshotRef?: string;
}
```

### Events (future)

```
action.proposed   → Agent proposes an action; UI shows proposal to user.
action.approved   → User approves; action executes.
action.rejected   → User rejects; action is cancelled.
action.executed   → Action completed successfully.
action.failed     → Action failed; error recorded.
```

### Requirements for action gate

1. **Show to user.** The proposed action must be displayed with target
   description and reason before execution.
2. **User confirmation.** No action executes without explicit user approval.
3. **Audit trail.** Every proposal, approval, rejection, and execution is
   recorded in the timeline.
4. **Cancellable.** User can reject at any point before execution.
5. **No silent execution.** The Agent cannot bypass the approval gate.

### When to introduce actions

- MVP: Level 1 — Observe only. No action provider.
- v0.2: Level 2 — Suggest. Agent proposes; user performs manually.
- v0.3: Level 3 — Act (approve). Agent executes after explicit approval.
- TBD: Level 4 — Autonomous. Separate safety decision.

---

## 11. Integration With Agent Workbench

### How browser context enters the prompt

Browser context is **opt-in per run**, not silently injected. The user
must explicitly select what to include:

```
Prompt composition (user-facing):

  [ ] Include current page (URL + title + page type)
  [x] Include selected text
  [x] Include clipboard preview
  [ ] Include DOM summary
  [ ] Include screenshot

  [Insert into prompt]
```

When selected, context is injected with a labeled boundary:

```
--- Browser Context (2026-06-06T12:00:00Z) ---
Page: https://github.com/gu87/trendradar (GitHub Repository)
Selected: Auto-merge is enabled for this PR
Clipboard: Error: Cannot connect to database
---
```

### Timeline integration

Browser events appear as timeline entries in Agent runs:

```
12:00:00  [Browser]  Navigated to github.com/gu87/trendradar
12:00:02  [Browser]  Page loaded: TrendRadar
12:00:05  [Browser]  Plugin matched: github-repo
12:00:10  [Browser]  User selected text (142 chars)
12:00:12  [Browser]  Context inserted into prompt
```

### Run metadata

Agent runs that consume browser context include a reference:

```typescript
interface RunMetadata {
  // ... existing fields ...
  browserContext?: {
    snapshotId: string;
    includedFields: ("url" | "title" | "pageType" | "selection" | "clipboard" | "domSummary" | "screenshot")[];
    snapshotTimestamp: string;
  };
}
```

### Right rail Browser tab

The right rail Browser tab displays:

- **Toolbar** — URL bar (user-controlled in MVP), back/forward buttons.
- **Page surface** — embedded WebContents viewport.
- **Context panel** (below or toggleable):
  - Page type badge (e.g. "GitHub PR").
  - Plugin indicator.
  - Screenshot thumbnail.
  - Selected text preview.
  - Clipboard text preview.
  - "Insert into prompt" action.

### What is NOT injected

- Full browsing history is not injected into every run.
- All open tabs are not injected into every run.
- Screenshots are not injected unless user explicitly selects them.
- Plugin output is injected only if a plugin matched and user opted in.

---

## 12. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | **WebContentsView production stability.** PoC used electron-vite dev mode. Need to verify behavior in packaged Electron app, especially around `capturePage()` and `executeJavaScript` reliability under load. | Open | Needs packaged-app testing |
| 2 | **Profile path: global vs per-Hermes-profile.** Current spec suggests `~/.hermes/browser/`. Should it be per Hermes profile (`~/.hermes/profiles/{id}/browser/`)? | Open | Depends on whether Hermes profiles share browser state |
| 3 | **Screenshot retention policy.** "Last 10" is proposed. Is this correct? Should retention be configurable? Where are screenshots stored — `~/.hermes/browser/screenshots/` or `~/.hermes/data/`? | Open | Needs UX input |
| 4 | **Plugin API versioning.** How do plugins declare compatibility with BrowserContextProvider versions? What happens when a plugin fails to extract — fall back to generic DOM summary silently or surface the error? | Open | Design plugin manifest format |
| 5 | **Clipboard privacy.** PoC reads clipboard without user opt-in. Production must require explicit opt-in. Should clipboard be OFF by default? Should it be per-workspace or global? | Open | Privacy-sensitive, needs design review |
| 6 | **Multi-tab memory pressure.** PoC used single-tab WebContentsView. Production multi-tab could increase memory significantly. Need profiling before committing to multi-tab MVP. | Open | Single-tab MVP reduces this risk |
| 7 | **External browser fallback.** Spec says external adapters are fallback. Should BrowserContextProvider support a second provider type (e.g. `"mcp-chrome"`), or is that a separate integration point? | Open | Adapter design can accommodate this later |
| 8 | **ChatGPT DOM changes over time.** ChatGPT frequently changes its DOM structure. Plugin extraction may break. How to detect and report extraction failures? | Open | Monitoring/metrics needed for plugin health |
| 9 | **Snapshot frequency.** Should `getCurrentSnapshot()` be throttled? If Agent calls it in a loop, it could cause performance issues. | Open | Consider debounce or cache TTL |
| 10 | **Offline behavior.** What happens if the embedded browser has no network? Should the provider return cached last-known-good snapshot? | Open | Degrade gracefully |

---

## 13. Recommended Next Step

Do not implement the full feature yet.

The next step is a **narrow implementation plan for an MVP skeleton** that
proves the BrowserContextProvider adapter works inside Hermes Desktop:

### MVP skeleton scope

1. **Embedded browser right rail shell.** A minimal Browser tab in the right
   rail with URL bar and WebContents viewport. User-controlled navigation
   only.
2. **Persistent profile.** Profile stored at `~/.hermes/browser/` (or
   configured path). Cookies/Local Storage survive app restart.
3. **BrowserContextProvider read-only interface.** Implement
   `getCurrentSnapshot()`, `getActiveTab()`, `captureScreenshot()`,
   `getReadableText()`, `getSelectedText()`, `getClipboardPreview()`.
4. **Snapshot display.** Right rail context panel shows URL, title, page
   type, selected text, clipboard preview.
5. **Screenshot.** Thumbnail in context panel, captured on demand.
6. **Selected text / clipboard / DOM summary.** Extracted via built-in
   static scripts, clipped to limits.
7. **No Agent actions.** No click/type/submit/navigate. No approval gate.
   No plugin layer (that is v0.2).

### What the MVP skeleton proves

- BrowserContextProvider works inside Hermes Desktop (not just a standalone PoC).
- Session persistence works with Hermes' own Electron process.
- Context flows from browser to Agent prompt.
- Right rail integration is functional.

### What comes after

- v0.2: Plugin layer (GitHub PR, ChatGPT conversation).
- v0.3: Approval-gated actions (click, type).
- v0.4: Multi-tab support.
- Future: External adapter fallback.
