# Hermes Embedded Browser Workspace v0.1 Spec

Date: 2026-06-06
Status: Design specification (read-only, no implementation commitment)
Based on: [Browser Workspace MVP Evaluation](./browser-workspace-mvp-evaluation.md)

---

## 1. Product Goal

Hermes Embedded Browser Workspace is a **shared browser workspace inside
Hermes Desktop**. The user and the Agent share the same web world — the user
opens pages, logs in, reads, and copies; the Agent observes context and uses
it to help.

This is not a browser-shell product, an Operator clone, or a Playwright
automation surface. It is a workspace — like Files, Diff, and Logs, but for
the web.

Core principle:

```text
User and Agent share the same browser workspace.
The user controls the browser. The Agent observes it.
```

Design reference: Orion — light, fast, clean, extensible.

---

## 2. UI Placement in Hermes Desktop

### Position

Browser Workspace lives in the **right rail**, alongside existing workspace
tabs:

```text
┌──────────────────────────────────────────────────────────┐
│  Chat / Session Sidebar  │  Main Work Surface              │  Right Rail      │
│                           │  (Terminal / Agent Run Timeline)│  ┌────────────┐ │
│                           │            │  │ Files      │ │
│                           │            │  │ Diff       │ │
│                           │            │  │ Logs       │ │
│                           │            │  │ Artifacts  │ │
│                           │            │  │ Browser  ◀─│─ new tab
│                           │            │  └────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Relationship to existing features

| Existing Feature | Relationship to Browser Workspace |
|---|---|
| Chat | Browser context can be inserted into Chat prompt ("Use current page") |
| Agent Run | Browser context is available as prompt context, not as an automation target |
| Timeline | Browser events (URL changes, page loads) can appear as timeline entries |
| Changed Files | Unrelated — Browser Workspace does not modify files |
| Diff | Browser Workspace can show page snapshots; Diff is for code changes |
| Review / QA | Browser context can inform review; review does not control the browser |
| Kanban | Unrelated — distinct feature |

### What the Browser tab shows

- **Toolbar** — URL bar (read-only in MVP), back/forward buttons (disabled in MVP), tab list dropdown.
- **Page surface** — the embedded Chromium viewport, full height.
- **Context panel** (below or toggleable) — page type badge, plugin indicator, screenshot thumbnail, selected text, clipboard preview, "Insert into prompt" action.

### What it does not show

- Full browser chrome replacing the terminal.
- Auto-action buttons.
- Hidden automation state.

---

## 3. Browser Profile

### Storage

```text
~/.hermes/browser/
  Default/
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
  Downloads/
  plugins/
```

All standard Chromium profile data is stored under `~/.hermes/browser/`,
isolated from the user's system browser profile.

### Persistence guarantees

| Data | Survives app restart | Notes |
|---|---|---|
| Cookies (including session cookies) | Yes | Standard Chromium behavior with persistent profile |
| Local Storage / Session Storage | Yes (Local), No (Session — standard spec behavior) | Session Storage clears per spec |
| IndexedDB | Yes | Used by apps like ChatGPT for conversation caching |
| Cache | Yes | Page load performance |
| Login state (OAuth tokens, sessions) | Yes | Dependent on cookie + Local Storage persistence |
| Downloads | Yes | Stored under `Downloads/` |
| Site permissions (camera, mic, notifications) | Yes | Stored in Preferences |
| Extensions | N/A | Chrome Web Store extensions are not loaded |

### System proxy inheritance

The embedded browser inherits the system proxy configuration from the host
Electron process. No separate proxy configuration is needed.

### Profile isolation from system browser

The embedded browser profile is **completely isolated** from the user's
default Chrome/Safari/Edge profile. This is intentional:

- Hermes does not read or write the user's system browser data.
- Login state in Hermes Browser Workspace is independent of login state in the user's default browser.
- This isolation protects user privacy and avoids profile-lock conflicts.

---

## 4. Tabs Model

### Tab management

```typescript
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
```

MVP capabilities:

- **New tab** — user creates a new tab (Hermes-defined new-tab page).
- **Tab list** — visible in the Browser Workspace toolbar.
- **Active tab switching** — user clicks to switch; URL bar updates.
- **Tab close** — user closes a tab.
- **Tab persistence** — open tabs survive app restart (restored from session state).

MVP does not include:

- Tab drag-reorder.
- Tab groups.
- Tab pinning.
- Tab search.

### History

Browsing history is scoped to the browser workspace only:

```typescript
interface HistoryEntry {
  id: string;
  url: string;
  title: string;
  visitTime: number;
  transitionType: "link" | "typed" | "reload" | "auto_subframe";
}
```

History is available as context for the Agent but is **not silently injected**
into every run. The user must explicitly opt to share history.

### Page lifecycle

| Event | Description |
|---|---|
| `page-load-committed` | URL changes (navigation committed) |
| `page-load-complete` | Page finished loading (DOM ready) |
| `page-title-updated` | Document title changed |
| `page-favicon-updated` | Favicon changed |
| `page-failed` | Navigation or load error |

These events feed the Browser Events timeline and can trigger plugin
re-evaluation.

---

## 5. Context Snapshot

### Snapshot shape

```typescript
interface BrowserContextSnapshot {
  capturedAt: string;          // ISO 8601
  source: {
    provider: "hermes-embedded-browser";
    mode: "read_only";
  };
  activeTab: {
    id: string;
    url: string;
    title: string;
    pageType: string | null;   // from plugin or URL heuristic
    pluginMatch: string | null;
    isLoading: boolean;
    selectedText: string;
    clipboardTextPreview: string;
    domSummary: string;
    screenshotRef: string;     // path or data URI
  };
  tabs: TabInfo[];
  recentHistory: HistoryEntry[];
  recentEvents: BrowserEvent[];
}
```

### Field requirements

| Field | Source | Max size | Notes |
|---|---|---|---|
| `url` | `webContents.getURL()` | Full | Redact query tokens post-MVP |
| `title` | `webContents.getTitle()` | Full | |
| `pageType` | Plugin or URL heuristic | N/A | |
| `pluginMatch` | Plugin registry | N/A | Null if no plugin matched |
| `selectedText` | `webContents.executeJavaScript('window.getSelection().toString()')` | 10 KB | Clip to max |
| `clipboardTextPreview` | `electron.clipboard.readText()` | 2 KB | Only if user has explicitly enabled clipboard sharing |
| `domSummary` | `document.body.innerText` via executeJavaScript, truncated | 20 KB | Must not inject raw HTML |
| `screenshotRef` | `webContents.capturePage()` → PNG → base64 or file ref | 500 KB image | Resize to max 1920px width |
| `tabs` | `BrowserView` or tab manager | Full | |
| `recentHistory` | Chromium history DB | Last 50 entries, since parameter | |
| `recentEvents` | Event log | Last 20 events | |

### Size limits

All text fields are clipped before injection into Agent prompt. The hard limit
per snapshot is **100 KB total text** (excluding screenshot). This prevents
accidental megabyte-context injection.

---

## 6. Hermes-native Plugin Layer

### Purpose

Instead of depending on Chrome Web Store extensions, Hermes Browser Workspace
uses a **Hermes-native plugin layer**. Plugins are small TypeScript/JS modules
registered by URL pattern that extract structured context from known pages.

### Plugin registry

| Plugin ID | URL Pattern | Context Extracted |
|---|---|---|
| `github-pr` | `github.com/*/pull/*` | PR title, author, base/head branch, changed files, CI status |
| `vercel-log` | `vercel.com/*` | Deployment ID, status, build log text, error extraction |
| `linear-issue` | `linear.app/*` | Issue ID, title, description, assignee, status, labels |
| `chatgpt-conversation` | `chatgpt.com/*`, `chat.openai.com/*` | Conversation title, message count, selected message text |
| `claude-conversation` | `claude.ai/*` | Conversation title, message count, selected message text |

### Plugin interface

```typescript
interface BrowserPlugin {
  id: string;
  name: string;
  patterns: string[];  // URL glob patterns
  activate(tab: TabInfo): boolean;
  extract(tab: TabInfo, webContentsId: number): Promise<PageContext>;
}

interface PageContext {
  title?: string;
  summary: string;
  metadata: Record<string, unknown>;
}
```

### Plugin lifecycle

1. On `page-load-complete`, the plugin registry checks all registered plugins
   for URL pattern match.
2. The first matching plugin's `activate()` is called.
3. If `activate()` returns `true`, `extract()` is called to produce structured
   context.
4. Plugin output replaces the generic DOM summary in the context snapshot.

### Plugin precedence

1. Plugin match → use plugin output as primary context.
2. No plugin match → fall back to generic DOM summary + URL heuristic for page type.
3. Multiple plugin matches → use the first registered match (registration order).

### Plugins vs Chrome extensions

| | Hermes-native plugin | Chrome Web Store extension |
|---|---|---|
| Distribution | Bundled with Hermes Desktop | User installs from Chrome Web Store |
| API surface | Hermes Plugin API (narrow, typed) | Chrome Extension API (broad) |
| Permissions | None — plugin runs in renderer with WebContents access | Requires extension manifest permissions |
| Update model | Hermes app update | Chrome Web Store auto-update |
| MVP support | Yes | No |

---

## 7. Read-only MVP Permission Boundary

### The boundary

The `BrowserContextProvider` interface enforces read-only access. There is no
code path from the Agent to browser action.

```text
Agent                   BrowserContextProvider            Embedded Browser
  │                            │                              │
  │  get_current_context()      │                              │
  │ ─────────────────────────► │                              │
  │                            │  webContents.getURL()        │
  │                            │ ──────────────────────────► │
  │                            │  webContents.getTitle()      │
  │                            │ ──────────────────────────► │
  │                            │  capturePage()               │
  │                            │ ──────────────────────────► │
  │                            │  executeJavaScript(...)      │
  │                            │ ──────────────────────────► │
  │                            │                              │
  │  BrowserContextSnapshot    │                              │
  │ ◄───────────────────────── │                              │
  │                            │                              │
  │  click("selector")         │                              │
  │ ─────────────────────────► │  BLOCKED — no handler       │
  │                            │                              │
```

### Methods exposed to Agent (MVP)

```text
get_current_context()      → BrowserContextSnapshot
get_tab_list()             → TabInfo[]
get_screenshot(tabId)      → base64 PNG
get_dom_summary(tabId)     → string (clipped)
get_selected_text(tabId)   → string (clipped)
get_clipboard_snippet()    → string (clipped, opt-in only)
get_recent_history(limit)  → HistoryEntry[]
get_recent_events(limit)   → BrowserEvent[]
```

### Methods intentionally absent from MVP

```text
navigate(url)              → NOT EXPOSED
new_tab(url)               → NOT EXPOSED
close_tab(tabId)           → NOT EXPOSED
switch_to_tab(tabId)       → NOT EXPOSED
click(selector)            → NOT EXPOSED
type(selector, text)       → NOT EXPOSED
submit_form(selector)      → NOT EXPOSED
execute_javascript(code)   → NOT EXPOSED (except read-only built-ins)
```

### Agent prompt restrictions

- Browser context is **opt-in per run**, not silently injected.
- User must explicitly select which context elements to include (page, selection, clipboard, screenshot).
- The prompt injection is scoped and labeled as browser context.

---

## 8. Approval-gated Future Actions

### Approval levels

After MVP, browser actions can be introduced through the existing Hermes
approval gate:

```text
Level 1: Observe       (MVP)     Agent reads browser context. No user approval needed.
Level 2: Suggest       (v0.2)    Agent proposes actions. User performs them manually.
Level 3: Act (approve) (v0.3)    Agent executes after explicit Hermes approval.
Level 4: Autonomous    (TBD)     Out of scope until separate safety decision.
```

### Integration with Hermes approval gate

When Level 3 actions are introduced:

```text
Agent: "Click the 'Deploy' button on the Vercel page."
  → Hermes approval dialog appears:
      [Approve] [Deny] [Show page screenshot]
  → If approved, execute action via WebContents API.
  → Record action in run timeline.
```

The approval gate reuses the existing Hermes review/approval pattern:

- Same UI component as review gate.
- Same timeline recording.
- Same audit trail.

### Action whitelist for Level 3

Not all browser actions should be approvable. Initial whitelist:

- `navigate(url)` — navigate to a new URL.
- `click(selector)` — click a specific element.
- `type(selector, text)` — type into an input field.
- `scroll(direction)` — scroll the page.

Explicitly excluded from Level 3:

- `submit_form(selector)` — requires additional confirmation step.
- `download_file(url)` — requires user-specified download path.
- `execute_javascript(code)` — not exposed to Agent.
- `fill_password(selector)` — never exposed.

---

## 9. MVP Validation Checklist

Before declaring v0.1 ready, the following must pass on a real Hermes Desktop
build with the embedded browser enabled:

| # | Validation | Pass/Fail |
|---|---|---|
| 1 | ChatGPT can log in and login persists across app restart | ☐ |
| 2 | Claude can log in and login persists across app restart | ☐ |
| 3 | GitHub can log in and login persists across app restart | ☐ |
| 4 | Vercel can log in and login persists across app restart | ☐ |
| 5 | System proxy is used by the embedded browser | ☐ |
| 6 | `capturePage()` produces a valid PNG screenshot | ☐ |
| 7 | `document.body.innerText` returns readable summary under 20 KB | ☐ |
| 8 | `window.getSelection().toString()` returns selected text | ☐ |
| 9 | `electron.clipboard.readText()` returns clipboard content | ☐ |
| 10 | Agent has no code path to `click`, `type`, `submit`, or `navigate` | ☐ |
| 11 | Open tabs survive app restart (restored from session state) | ☐ |
| 12 | Multiple tabs work independently (separate navigation, separate context) | ☐ |
| 13 | Opening a GitHub PR triggers the `github-pr` plugin (if installed) | ☐ |
| 14 | Browser context insertion into Chat prompt works without error | ☐ |

Fail condition: any required validation fails.

---

## 10. Open Questions

### Q1: Electron BrowserView vs WebContentsView

Electron 30+ recommends `WebContentsView` over the deprecated `BrowserView`.
Which API should Hermes target?

- `WebContentsView` — modern, recommended, but API surface slightly different.
- `BrowserView` — deprecated but widely used and documented.

**Recommendation:** Start with `WebContentsView`. Fall back to `BrowserView`
only if Electron version compatibility requires it.

### Q2: Plugin compatibility scope

Should Hermes-native plugins be compatible with any existing plugin format?

- Chrome extension manifest format — no, too broad.
- MCP tool format — maybe, for future interop with mcp-chrome as fallback.
- Custom Hermes format — yes, this is the primary target.

**Recommendation:** Start with the custom `BrowserPlugin` TypeScript interface.
Evaluate MCP tool format interop as a post-MVP enhancement.

### Q3: Profile storage path

Should the browser profile be configurable?

- Default: `~/.hermes/browser/`.
- Custom: user-configurable in Hermes settings.
- Multiple profiles: per-Hermes-profile browser profiles (e.g., `~/.hermes/profiles/work/browser/`).

**Recommendation:** Ship with `~/.hermes/browser/` as the default. Add
per-Hermes-profile support in v0.2. Do not make it configurable in v0.1 to
avoid support burden.

### Q4: Privacy redlines

What must never happen, even post-MVP?

1. **Never silently inject browser context into Agent prompt.**
2. **Never store browsing history outside `~/.hermes/browser/`.**
3. **Never share browser profile data with external servers** (telemetry, cloud sync).
4. **Never auto-submit forms or auto-send messages** without explicit per-action approval.
5. **Never expose password fields to Agent context** — redact `input[type=password]` values from DOM summary.

### Q5: Memory and performance

An embedded Chromium instance adds significant memory overhead (~100-200 MB
per renderer process on macOS). v0.1 should:

- Only create the embedded browser when the Browser Workspace tab is first opened (lazy init).
- Unload background tabs' renderer processes when not in use (Chromium's built-in tab discarding).
- Cap the number of concurrent renderer processes.

### Q6: Download handling

Where do downloads go?

- Default: `~/Downloads/` — same as the user's default browser.
- Alternative: `~/.hermes/browser/Downloads/` — scoped to Hermes.

**Recommendation:** `~/.hermes/browser/Downloads/` to avoid cluttering the
user's default Downloads folder. Add a "Show in Finder" action in the
Browser Workspace toolbar.

### Q7: Certificate and enterprise proxy support

Enterprise environments may use custom CA certificates and authenticated
proxies. The embedded browser should:

- Trust the system keychain (macOS) or system certificate store (Windows/Linux).
- Respect the system proxy settings (already inherited from Electron).
- Support proxy authentication if Chromium's built-in prompt is sufficient.

Custom CA injection and proxy PAC files are deferred to post-MVP.

---

## Appendix A: Terminology

| Term | Definition |
|---|---|
| Browser Workspace | The full feature: embedded browser + context provider + plugin layer + UI |
| Embedded Browser | The Chromium/Electron surface that renders web pages inside Hermes Desktop |
| Context Snapshot | The structured data capture of the current browser state, sent to the Agent |
| Plugin | A Hermes-native JS module that extracts structured context from a known web page |
| BrowserContextProvider | The internal interface boundary between Agent and Browser Workspace |
| Right Rail | The right-side panel area in Hermes Desktop containing Files, Diff, Logs, Artifacts, and Browser tabs |

## Appendix B: Reference Documents

- [Browser Workspace MVP Evaluation](./browser-workspace-mvp-evaluation.md) — candidate evaluation and architecture rationale
- Orion Browser: https://kagi.com/orion/ — design reference
- Electron WebContentsView docs: https://www.electronjs.org/docs/latest/api/web-contents-view
