# Hermes Browser Workspace — MVP Implementation Plan (Part 1)

Date: 2026-06-06
Status: Implementation plan (read-only, no implementation commitment)
Based on:
- [Browser Workspace MVP Evaluation](../research/browser-workspace-mvp-evaluation.md)
- [Embedded Browser Workspace v0.1 Spec](../research/browser-workspace-embedded-mvp-spec.md)
- [Embedded Browser Workspace PoC Results](../research/browser-workspace-embedded-poc-results.md)
- [BrowserContextProvider Adapter Design](../architecture/browser-context-provider-design.md)

---

## 1. Executive Summary

**Hermes Browser Workspace can proceed to MVP skeleton implementation
planning, but Phase 0 must come first.**

The PoC proved that an embedded Electron Chromium surface can render pages,
persist login state, inherit proxy, and extract read-only context. However:

1. **The PoC was a standalone electron-vite scaffold.** It did not run inside
   Hermes. The current Hermes runtime has NO Electron host — it is a Python
   backend + React web dashboard + CLI/TUI.

2. **Phase 0 must audit the implementation surface** to determine where and
   how the browser surface should be hosted. If the current production shell
   is a FastAPI-served React web dashboard, an embedded Chromium cannot be
   dropped in directly.

3. **The next 7 phases define the MVP skeleton.** The implementation is
   phased, read-only, embedded-first, and independently reversible.
   No phase requires a later phase to be useful.

### What this plan covers

- Browser Workspace as a right rail context layer in Hermes Desktop.
- BrowserContextProvider as the only Agent-facing read boundary.
- MVP is read-only — no click/type/submit/navigate from the Agent.
- Each phase is reversible and independently validatable.

### What this plan does NOT cover

- External browser adapters (fallback, not primary).
- Chrome Web Store extension compatibility.
- Agent action automation.
- Plugin layer (v0.2).
- Multi-tab support (v0.4).

---

## 2. Implementation Principles

Every phase must satisfy these principles. If a principle is violated, the
phase is reconsidered or re-scoped.

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **Preserve existing Agent Workbench flow.** Chat → Agent Run → Timeline → Changed Files → Review must remain the primary interaction loop. Browser Workspace is additive, not replacement. | The workbench is the product. Browser context enriches it; it does not become it. |
| 2 | **Right rail integration only.** Browser Workspace lives in the right rail. It does not become the main work surface. It does not replace Chat, Terminal, or Diff. | Spec § 2. Orion design reference. |
| 3 | **BrowserContextProvider is the only Agent-facing boundary.** The Agent reads browser context through a single typed interface. No raw WebContents, no direct Chromium API access. | Architecture design § 3. Read-only boundary. |
| 4 | **User controls browser, Agent observes.** The user opens pages, navigates, logs in, selects text, copies. The Agent only reads the resulting context. | Core principle from MVP Spec § 1. |
| 5 | **Embedded browser owns profile/session.** Login state, cookies, session storage live in Hermes-owned profile directory. Not exported from or imported to the user's system browser. | Spec § 3. Profile isolation. |
| 6 | **No Agent click/type/submit/navigate.** These are explicitly excluded from MVP. They may appear in a future approval-gated ActionProvider, not in BrowserContextProvider. | Spec § 7. Architecture § 10. |
| 7 | **No Chrome Web Store extension support in MVP.** Hermes-native plugins (v0.2) replace Chrome extensions. Chrome extension compatibility is not an MVP concern. | Spec § 6. |
| 8 | **No external browser adapter as primary path.** Embedded browser is primary. External adapters (mcp-chrome, BrowserMCP) are fallback for users who prefer their own Chrome. | MVP Evaluation § Embedded vs External. |
| 9 | **Each phase must be independently reversible.** If Phase 2 fails, Phase 1 must still work. If Phase 3 is blocked, Phase 2 must be removable without destabilizing Phase 1. | Prevents lock-in. Enables phased rollback. |

---

## 3. Current Implementation Surface

### Conservative assessment (as of 2026-06-06)

**There is no Electron host in the current Hermes runtime.**

The visible runtime surface is:

| Component | Path | Technology | Role |
|-----------|------|------------|------|
| Python CLI | `hermes_cli/main.py` (~12K LOC) | Python argparse | Main CLI entry, all subcommand dispatch |
| Interactive TUI | `cli.py` (~14K LOC) | Python prompt_toolkit | Interactive REPL, slash commands |
| Node.js TUI | `ui-tui/src/entry.tsx` | Node + Ink + React | Terminal TUI, JSON-RPC to Python gateway |
| React Web Dashboard | `web/src/App.tsx` (~850 LOC) | React + react-router | Web dashboard, sidebar, page layout |
| Dashboard Server | `dashboard/main.py` | FastAPI | Serves React static, API for gateway ops |
| API Server | `gateway/platforms/api_server.py` | FastAPI | `POST /v1/runs`, SSE events, approvals |

There is **no** `electron-main/`, `src/main/`, `src/preload/`, or
`src/renderer/` in the runtime. The `/Users/gu/.hermes` repo is a
knowledge/reference/docs repository, not the runtime codebase.

### Critical constraint

The embedded Chromium surface proven in the PoC (`/tmp/hermes-browser-poc`)
cannot be dropped into the current FastAPI + React dashboard. Electron
`WebContentsView` requires an Electron `BrowserWindow` host process — not a
web page served by a Python HTTP server.

**Phase 0 must answer: where does the Electron host live?**

### What exists that helps

- `config.yaml` — Hermes configuration, may provide host detection.
- `hermes_cli/main.py` — CLI already launches subprocesses (gateway, TUI).
- `ui-tui/` — proves Hermes can run a Node.js child process with structured IPC.
- `dashboard/main.py` — already serves a React SPA; could serve additional entry points.
- `~/.hermes/` — existing user data directory; browser profile path anchor.

### What does not exist (and must be created)

- An Electron main process in the Hermes runtime.
- A preload script for Electron IPC.
- A renderer-side browser workspace UI component.
- A BrowserContextProvider service.
- Any IPC channel between Python backend and a browser host.

---

## 4. Phase 0: Implementation Surface Audit

### Goal

Determine where the embedded Chromium host lives relative to the current
Hermes runtime. Do not start writing Browser Workspace code until this audit
is complete.

### Scope

- Read-only inspection of the runtime codebase (not this docs repo).
- Identify the current app shell: how does Hermes start? What process tree exists?
- Identify existing right rail or sidebar UI components.
- Identify existing state/event boundaries (API server, SSE, TUI gateway).
- Identify whether any Electron bootstrap code already exists.

### Likely files to inspect

```
hermes_cli/main.py            — CLI entrypoint, subcommand dispatch
cli.py                        — TUI REPL, process lifecycle
dashboard/main.py             — FastAPI server, static mount points
web/src/App.tsx               — React app shell, sidebar layout
web/src/ (other components)   — Right rail, workspace tabs, if any
config.yaml                   — Host configuration
hermes_cli/electron.py        — If it exists (to be confirmed)
ui-tui/package.json           — Node.js TUI dependencies
package.json                  — If it exists at repo root
hermes_state.py               — Session/shell state
```

### Questions to answer

1. **Host type.** Is the current Hermes production shell a FastAPI-served
   React SPA accessed via browser, a native Electron window, or a terminal
   TUI? (Current evidence: multiple shells exist in parallel.)

2. **Right rail existence.** Does the React dashboard already have a right
   rail / sidebar tab component? Where would Browser Workspace slot in?

3. **State boundary.** How does the Agent currently receive context? Where
   does browser context injection fit in the prompt composition pipeline?

4. **Event boundary.** Does a real-time event bus exist between the Python
   backend and the React frontend? (SSE over `/v1/runs/{id}/events` exists;
   is a similar channel available for workspace-level events?)

5. **Electron possibility.** Could the existing Node.js TUI (`ui-tui/`)
   infrastructure be extended to host an Electron `BrowserWindow`, or would
   a separate Electron process be required?

6. **Desktop surface.** Is there a "Hermes Desktop" app bundle, or is
   everything run from the CLI? If CLI-only, what is the plan for a desktop
   window host?

### Validation

- All answers documented in a Phase 0 audit output (not this plan).
- If no Electron host path exists, Phase 2 is blocked until a host decision
  is made.
- If Electron is impossible for the current architecture, the plan pivots: a
  separate Electron app launched by the CLI may be the minimum viable host.

### Rollback / no-op

Phase 0 is read-only. It modifies nothing. Rollback is trivial (don't use
the audit results).

---

## 5. Phase 1: Right Rail Browser Tab Shell

### Goal

Add a visible "Browser" tab to the right rail UI — empty state only. No
browser engine. No Agent integration. This proves the UI slot exists before
any engine work begins.

### Scope

- Add a "Browser" tab to the right rail tab bar (alongside Files, Diff, Logs,
  Artifacts, if they exist).
- Tab content is an empty state or placeholder:
  ```
  Browser Workspace
  Coming soon.
  ```
- No URL bar.
- No WebContents.
- No BrowserContextProvider.
- No IPC handler.
- No package dependency changes.

### Likely files touched

```
web/src/App.tsx                    — Add Browser to tab bar
web/src/components/RightRail/      — New or modify right rail component
web/src/components/BrowserTab/     — New: placeholder component
```

If the current Hermes desktop surface is TUI-only (`cli.py`), this phase may
instead add a placeholder menu entry or slash command. The exact target
depends on the Phase 0 audit result.

### Implementation notes

- Use the existing right rail component pattern. Do not create a new layout
  system.
- The Browser tab icon can be a simple globe or browser icon (Unicode).
- The placeholder content should match the visual style of other right rail
  tabs.
- No backend changes. No API changes. No new dependencies.

### Validation

- Hermes starts without errors.
- Right rail shows a Browser tab.
- Clicking Browser shows the placeholder.
- No existing functionality is broken.
- Switching between Browser and other tabs works correctly.

### Rollback

Remove the Browser tab entry from the tab bar array. Delete the
BrowserTab placeholder component. No state is persisted. No backend
artifacts exist. Fully reversible in a single commit revert.

---

## 6. Phase 2: Embedded Browser Host

### Goal

Embed a real Chromium surface into Hermes that is user-controlled and
persists login state. This is the first phase that brings the PoC's core
capability into Hermes — but it is still read-only and Agent-free.

### ⚠️ Host decision gate (from Phase 0)

If Phase 0 concludes that the current Hermes shell (FastAPI + React SPA)
cannot host an Electron `WebContentsView` directly, Phase 2 must first make
a host decision:

| Option | Description | Risk |
|--------|-------------|------|
| A: Separate Electron process | CLI launches a companion Electron app (similar to how `ui-tui/` runs a Node.js process). Browser window is a separate OS window. | Lower integration; separate window may feel disconnected from Hermes. |
| B: Electron wrapper for the React SPA | Hermes Desktop becomes an Electron app that loads the existing React SPA as its renderer. The same Electron process hosts the embedded Chromium. | Larger change; touches app startup and may affect the CLI/TUI path. |
| C: Electron-native right rail | Hermes Desktop is a full Electron app. Right rail is an Electron UI component, not a React component. | Most work; long-term destination but not Phase 2 scope. |

For MVP, Option A (separate Electron process) is the lowest-risk starting
point. It mirrors the existing `ui-tui/` pattern: Hermes CLI launches a child
process, communicates over IPC.

### Scope

- Create a minimal Electron host (single `BrowserWindow` with a
  `WebContentsView` for the browser surface).
- Launch from Hermes CLI (similar to `ui-tui` subprocess pattern).
- User-controlled URL bar.
- User-controlled navigation (Go button, back/forward buttons).
- Persistent profile at `~/.hermes/browser/`.
- System proxy inheritance (default Chromium behavior).
- No Agent access — no IPC handler for Agent context reads.
- No snapshot, no screenshot, no text extraction (that is Phase 3).

### Likely files touched

```
hermes_cli/browser.py             — New: CLI subprocess launcher for Electron host
browser-host/                     — New: minimal Electron app directory
  package.json                    — Electron + electron-vite dependencies
  src/main/index.ts               — Electron main process (BrowserWindow + WebContentsView)
  src/preload/index.ts            — Preload (no context bridge yet for Agent APIs)
  src/renderer/index.html         — Minimal toolbar renderer (URL bar, buttons)
  src/renderer/src/App.tsx        — Toolbar component
```

### Implementation notes

- **User manual navigation only.** The URL bar is a user-facing input, not an
  Agent API. There is no `loadURL` exposed via IPC to the Python process.
- **Persistent profile.** `BrowserWindow` opens with `app.setPath("userData",
  "~/.hermes/browser/")`. This gives cookie/localStorage persistence out of
  the box — same mechanism proven in the PoC.
- **Subprocess lifecycle.** Hermes CLI spawns the Electron process on
  `hermes browser start`. It kills the subprocess on `hermes browser stop` or
  on CLI exit. Standard pattern matching `ui-tui/`.
- **No context bridge for Agent.** The preload script is minimal — only
  user-facing UI APIs (navigateHuman, goBack, goForward). No `getState`,
  `captureSnapshot`, etc.
- **Window management.** The Electron window opens as a separate OS window.
  If the user prefers, it can be positioned to the right of the main Hermes
  terminal/SPA.

### Validation

- `hermes browser start` launches an Electron window.
- URL bar accepts input; Go navigates to the entered URL.
- Back/forward buttons work.
- Login to ChatGPT/GitHub works (manual user action).
- Close the Electron window. Re-open. Login state persists.
- `hermes browser stop` kills the Electron process cleanly.
- No crash on repeated open/close.
- No profile corruption across restarts.
- Existing CLI/TUI/web dashboard functionality is unaffected.

### Rollback

Remove `hermes_cli/browser.py` and the `browser-host/` directory. No changes
to existing Hermes subsystems. The `~/.hermes/browser/` profile directory can
be kept or deleted — deleting it removes all saved login state.

---

## 7. Phase 3: BrowserContextProvider Read-only Service

### Goal

Connect the embedded browser to the Hermes Agent through the
`BrowserContextProvider` interface. The Agent can now read browser context —
but cannot act on the browser. This is the first phase where the Agent
benefits from the browser workspace.

### Scope

- Implement the `BrowserContextProvider` interface in the Electron host
  as IPC handlers.
- Expose to the Python backend via a structured JSON-RPC or SSE channel
  (reusing the existing `api_server` event infrastructure where possible).
- Agent reads: `getCurrentSnapshot`, `getTabs`, `captureScreenshot`,
  `getReadableText`, `getSelectedText`, `getClipboardPreview`,
  `subscribeToBrowserEvents`.
- Context injection into Agent prompt (opt-in per run).
- Built-in static scripts for DOM/selection extraction (same approach as PoC).
- Size clipping and limits enforced at the provider boundary.

### TypeScript interface sketch (contract, not implementation)

```typescript
interface BrowserContextProvider {
  getCurrentSnapshot(): Promise<BrowserContextSnapshot>;
  getTabs(): Promise<TabInfo[]>;
  getActiveTab(): Promise<TabInfo>;
  captureScreenshot(options?: ScreenshotOptions): Promise<ScreenshotResult>;
  getReadableText(tabId?: string): Promise<string>;
  getSelectedText(tabId?: string): Promise<string>;
  getClipboardPreview(): Promise<string>;
  getRecentEvents(limit?: number): Promise<BrowserEvent[]>;
  subscribeToBrowserEvents(
    handler: (event: BrowserEvent) => void,
    filter?: EventFilter
  ): () => void;
}
```

Full type definitions are in [BrowserContextProvider Adapter Design
§3–4](../architecture/browser-context-provider-design.md).

### Forbidden methods (MVP)

These MUST NOT appear in the provider interface:

```
click(selector)               → NOT EXPOSED
type(selector, text)          → NOT EXPOSED
submit(selector)              → NOT EXPOSED
navigateAsAgent(url)          → NOT EXPOSED
executeJavaScript(userCode)   → NOT EXPOSED
sendInputEvent(event)         → NOT EXPOSED
dispatchInputEvent(event)     → NOT EXPOSED
```

### Implementation notes

- **IPC channel.** Electron main process registers `ipcMain.handle()` for
  each provider method. Preload exposes them via `contextBridge` — but
  *only* to the internal renderer. The Python backend receives context via
  a local HTTP endpoint or SSE stream served by the Electron main process or
  a sidecar.
- **executeJavaScript constraint.** Only built-in static scripts. No user or
  Agent input reaches `webContents.executeJavaScript()`. Same approach as PoC:
  `EXTRACT_DOM_SCRIPT` and `EXTRACT_SELECTION_SCRIPT` are module-level
  constants.
- **Clipboard opt-in.** `getClipboardPreview()` returns empty string unless
  the user has toggled clipboard sharing ON in the right rail (default: OFF).
- **Event subscription.** `subscribeToBrowserEvents` returns an unsubscribe
  function. Events are delivered via a push channel (WebSocket or SSE). Not
  polling.

### Validation

- `getCurrentSnapshot()` returns a valid `BrowserContextSnapshot` with URL,
  title, pageType, and extracted context.
- `getReadableText()` returns clipped DOM text (≤20 KB).
- `getSelectedText()` returns user-selected text or empty string.
- `getClipboardPreview()` returns clipboard text after user opt-in.
- `captureScreenshot()` returns a valid PNG file ref.
- `subscribeToBrowserEvents()` delivers events in real time.
- No forbidden method is callable from the Agent.
- `executeJavaScript` is never called with user/Agent-provided code.
- Context is not silently injected into every Agent run — user must opt in.

### Rollback

Disable the IPC handlers in the Electron main process. Remove the Agent-side
provider client. The browser window remains functional (Phase 2) but the
Agent can no longer read context. Reversible without affecting browser
session persistence.

---

## 8. Phase 4: Snapshot UI + Prompt Insertion

### Goal

Show browser context in the right rail and allow the user to explicitly
insert it into the Agent prompt. This is the first phase where browser
context visibly integrates with the Agent Workbench, but it remains
user-gated and read-only.

### Scope

- Right rail context panel displays:
  - Page URL and title.
  - Page type badge (from plugin match or "generic-web").
  - Screenshot thumbnail (click to expand).
  - DOM summary (first 500 chars with "show more").
  - Selected text (if any; "(none)" if empty).
  - Clipboard preview (if clipboard sharing enabled).
- "Insert into prompt" button — user explicitly clicks to inject context.
- Context injection is **opt-in per run**, not automatic.
- Injected context is labelled and scoped in the prompt:
  ```
  --- Browser Context (2026-06-06T12:00:00Z) ---
  Page: https://github.com/gu87/trendradar (GitHub Repository)
  Selected: Auto-merge is enabled for this PR
  ---
  ```
- Context size limit: 100 KB total text per injection (excluding screenshot).
- Redact known sensitive fields (API keys in URLs, auth tokens) before injection.

### Implementation notes

- The context panel is a read-only display component in the right rail. No
  write controls.
- The "Insert into prompt" action places a `browserContext` block into the
  prompt composition area. It does not immediately send the prompt.
- DOM summary is clipped to 20 KB before display. The full summary is
  available in the snapshot JSON but not injected.
- Screenshot is not injected by default — user must check an additional
  checkbox to include it (large token cost).
- Sensitive text redaction is a regex-based best-effort layer. It is not
  a security guarantee. Known patterns: `?token=`, `?key=`, `?api_key=`.
- No tabs/history data is injected unless the user explicitly selects them
  from a context picker.
- No hidden context injection exists. The Agent receives only what the user
  explicitly opted to include.

### Validation

- Right rail shows URL, title, page type badge, screenshot thumbnail,
  DOM summary, selected text, clipboard preview.
- "Insert into prompt" button is functional.
- Injected context appears in the prompt composition area with correct
  labelling and timestamps.
- Context is NOT automatically injected into any Agent run.
- No hidden context injection path exists.
- Screenshot is only included when user explicitly checks the checkbox.
- Sensitive URL query parameters are redacted.
- Context size does not exceed 100 KB.

### Rollback

Remove the context panel component from the right rail. Remove the prompt
insertion handler. Browser context is still available via the provider API
(Phase 3) but has no UI path into the prompt. Reversible without affecting
browser session or provider functionality.

---

## 9. Phase 5: Hermes-native Plugin MVP

### Goal

Replace the generic DOM summary with structured, page-type-aware context for
the most important pages the user visits. Plugins extract PR metadata, issue
details, conversation summaries — making browser context more useful to the
Agent than raw `body.innerText`.

### Scope

**MVP plugins:**

| Plugin ID | URL Pattern | Context Extracted |
|-----------|-------------|-------------------|
| `github-pr` | `github.com/*/pull/*` | PR title, author, base/head branch, changed files count, CI status |
| `chatgpt-conversation` | `chatgpt.com/*` | Conversation title, message count, visible message preview |

**Future plugins (not MVP, documented for planning):**

| Plugin ID | URL Pattern | Context Extracted |
|-----------|-------------|-------------------|
| `github-issue` | `github.com/*/issues/*` | Issue title, author, labels, assignees, status |
| `vercel-deployment` | `vercel.com/*` | Deployment ID, status, build log summary |
| `linear-issue` | `linear.app/*` | Issue ID, title, description, assignee, status |
| `feishu-doc` | `*.feishu.cn/*` | Document title, content summary |

### What plugins are NOT

- Plugins are NOT Chrome Web Store extensions. No Chrome extension API
  compatibility is provided in MVP.
- Plugins are NOT browser automation tools. They do not click, type, or
  navigate. They only extract read-only context.
- Plugins are NOT user-installable in MVP. They are bundled with Hermes
  Desktop.

### Plugin lifecycle

1. On `page.loaded` event, the plugin registry evaluates all registered
   plugins against the current URL.
2. First matching plugin's `match(url, title)` returns true → emit
   `plugin.matched` event → call `extract()`.
3. Plugin output replaces the generic DOM summary as the primary context
   in the snapshot. The DOM summary is still available as a fallback field.
4. If no plugin matches, `pageType` is `null`, `pluginContext` is `null`,
   and the generic DOM summary is used.

### Fallback

If a plugin fails to extract (throws, times out, returns null), the system
falls back to the generic DOM summary. The failure is logged but not surfaced
to the user as an error. This prevents plugin breakage from blocking browser
context entirely.

### Implementation notes

- Plugins run as static TypeScript modules registered at build time in the
  Electron host. No dynamic loading in MVP.
- Each plugin is a single file exporting a `BrowserPlugin` interface object.
- Plugin extraction uses `webContents.executeJavaScript()` with built-in
  static scripts. No user/Agent-provided JS.
- Plugin output is clipped to a per-plugin `maxOutputChars` limit (default
  5 KB).

### Validation

- Open a GitHub PR page. Plugin matches. Snapshot shows `pageType:
  "github-pr"` and `pluginContext` contains PR title, author, branches.
- Open a ChatGPT conversation. Plugin matches. Snapshot shows `pageType:
  "chatgpt-conversation"` and `pluginContext` contains conversation title
  and message preview.
- Open a page with no plugin match. Snapshot shows `pageType: null` and
  `pluginContext: null`. Generic DOM summary is still populated.
- A plugin that throws does not crash the browser or block context
  extraction. Fallback to generic DOM summary works.

### Rollback

Remove plugin registration from the plugin registry. All pages fall back
to generic DOM summary. Plugin code files can be deleted or left as dead
code. Reversible without affecting provider or browser functionality.

---

## 10. Phase 6: Agent Workbench Integration

### Goal

Wire browser context into the Agent Workbench so that browser state is a
first-class context source alongside files, diffs, and logs. The Agent can
reference browser snapshots in run metadata, and browser events appear in
the timeline — without granting the Agent any browser action capability.

### Scope

- **Run metadata.** Each Agent run that consumes browser context includes a
  `browserContextSnapshotId` and a list of included fields in the run
  metadata:
  ```json
  {
    "browserContext": {
      "snapshotId": "snap_20260606_120000",
      "url": "https://github.com/gu87/trendradar",
      "pageType": "github-repo",
      "includedFields": ["url", "title", "pageType", "selection", "clipboard"]
    }
  }
  ```
- **Timeline.** Browser events appear as timeline entries in Agent runs:
  ```
  12:00:00  [Browser]  Navigated to github.com/gu87/trendradar
  12:00:05  [Browser]  Plugin matched: github-repo
  12:00:10  [Browser]  User selected text (142 chars)
  12:00:12  [Browser]  Context inserted into prompt
  ```
- **Task Thread.** A task or session thread can reference one or more
  browser snapshots. This allows the Agent to say "see the PR at the time
  of this snapshot" rather than assuming the current page state.
- **Prompt insertion.** Must be user-explicitly triggered. The "Insert into
  prompt" button from Phase 4 is the only insertion path.
- **No hidden context injection.** The Agent does not receive browser
  context unless the user explicitly opted to include it for that run.
- **No Agent browser actions.** The Agent cannot request navigation, click,
  type, or submit through any workbench channel.

### Implementation notes

- Run metadata fields are appended by the run orchestrator when the user
  selects browser context before starting a run. The provider is called to
  get the current snapshot at insertion time.
- Timeline entries are created from `subscribeToBrowserEvents()` (Phase 3).
  Only events relevant to the current active run are shown.
- Task Thread references use snapshot IDs, not live browser state. Snapshots
  are ephemeral (in-memory) by default; they are not persisted to disk unless
  the user explicitly saves them.
- The prompt injection block includes a timestamp and snapshot ID so the
  Agent knows when the context was captured.

### Validation

- Starting a run with browser context selected shows `browserContext` in
  run metadata.
- Browser events appear in the Agent run timeline in real time.
- Task Thread can reference a saved snapshot ID.
- Prompt injection only occurs via explicit user action.
- No hidden context injection path exists.
- No Agent browser action method is callable from the workbench.
- Existing runs without browser context work identically (no regression).

### Rollback

Remove the `browserContext` field from run metadata schema. Remove timeline
entry type for browser events. Remove snapshot ID references from Task Thread.
Browser context remains available via the provider API (Phase 3) but has no
integration with the Agent Workbench. Reversible without affecting provider
or browser functionality.

---

## 11. Phase 7: Hardening / Rollout Guardrails

### Goal

Add the safety rails, error states, and configurability needed before any
user sees Browser Workspace. This phase makes the feature safe to ship as
an opt-in beta, not a silently-enabled capability.

### Scope

- **Feature flag.** `BROWSER_WORKSPACE_ENABLED` flag (config or env). Off by
  default. All browser workspace code paths gate on this flag. When off,
  the Browser tab does not appear, no Electron child process is spawned, and
  no IPC handlers are registered.
- **Browser profile reset.** User-facing option to "Reset Browser Profile"
  (clears cookies, localStorage, IndexedDB, cache). Does not clear
  screenshots or Hermes data. Requires confirmation dialog.
- **Screenshot retention policy.** Max 10 screenshots per workspace.
  Oldest is evicted when limit is reached. Screenshots stored under
  `~/.hermes/browser/screenshots/`. Eviction is logged.
- **Proxy mode UI.** System / Direct / Custom selector in the right rail.
  Custom mode accepts a single proxy URL (e.g. `http://127.0.0.1:7890`).
  Changing proxy mode requires browser restart (confirmation dialog).
- **Memory limits.** If the Electron child process exceeds a configurable
  memory threshold (default: 1 GB), show a warning in the right rail.
  Do not auto-kill the process. User can restart manually.
- **Browser crash isolation.** If the Electron child process crashes, the
  right rail shows an error state with a "Restart Browser" button. No crash
  propagates to the Hermes main process. No Agent run is affected.
- **Read-only boundary static check.** A lint rule or CI check verifies that
  no forbidden method names (`click`, `type`, `submit`, `navigateAsAgent`,
  `executeJavaScript`, `sendInputEvent`) appear in the BrowserContextProvider
  interface or IPC handler registration.
- **Privacy warning.** First time the user enables Browser Workspace, show a
  one-time privacy notice:
  ```
  Browser Workspace stores login cookies and site data in your Hermes
  profile. It does not share this data with external services.
  You can reset the browser profile at any time.
  Clipboard sharing is OFF by default. Enable it in settings.
  ```
- **Error states.** Distinct error states for:
  - Electron child process failed to start.
  - Browser page failed to load.
  - Provider API call timed out.
  - Plugin extraction failed (silent fallback, but logged).
  - Proxy connection refused.
  - Screenshot capture failed.

### Implementation notes

- Feature flag is read at Hermes CLI startup. No dynamic toggling in MVP
  (avoids mid-session state inconsistency).
- Browser profile reset deletes `~/.hermes/browser/Default/` subdirectories
  (Cookies, Local Storage, IndexedDB, Cache, Code Cache). It preserves
  `Preferences` and `Secure Preferences` (site permission settings).
- Screenshot retention is enforced at capture time, not by a background
  job. Simple: count files in `screenshots/`, if ≥10, delete oldest before
  writing new.
- Memory monitoring uses `process.memoryUsage()` in the Electron main
  process, polled every 30 seconds. Warning threshold is configurable.
- Browser crash is detected when the Electron child process exits with a
  non-zero code. Hermes CLI already has subprocess lifecycle management
  from `ui-tui/` pattern.
- Read-only boundary check is a grep-based script (not a full AST parser).
  It searches for forbidden method names in the provider module and IPC
  handler registration file. Simple, effective, no false negatives.

### Validation

- Feature flag OFF: Browser tab hidden, no Electron process, no IPC
  handlers.
- Feature flag ON: Browser tab visible, Electron launches on `hermes browser
  start`.
- Profile reset clears cookies and login state. Re-login works after reset.
- Screenshot retention: capturing 11 screenshots keeps only 10 newest.
- Proxy mode change shows restart dialog. After restart, new proxy rules are
  in effect.
- Memory warning appears when Electron process RSS exceeds threshold.
- Electron crash shows error state in right rail. "Restart Browser" button
  works. Main Hermes process unaffected.
- Read-only boundary check passes: no forbidden methods in production code.
- Privacy warning appears once on first enable, never again.
- All error states render correctly.

### Rollback

Set feature flag to OFF. All browser workspace code paths are gated. No
Electron process spawns. No IPC handlers register. The code remains in the
codebase but is inert. A future release can remove the gated code entirely.

---

## 12. File Touch Matrix

| Phase | Files Likely Touched | Risk Level | Validation | Rollback |
|-------|---------------------|------------|------------|----------|
| **0** | Runtime codebase (read-only audit) | None | Document answers to 6 host questions | N/A (read-only) |
| **1** | `web/src/App.tsx`, `web/src/components/RightRail/`, `web/src/components/BrowserTab/` | Low | Browser tab visible, placeholder content, no regressions | Remove tab entry + component |
| **2 (Option A)** | `hermes_cli/browser.py`, `browser-host/` (new Electron app dir), `package.json`, `src/main/`, `src/preload/`, `src/renderer/` | Medium | Electron window launches, URL navigation works, profile persists | Remove `browser.py` + `browser-host/` dir |
| **2 (Option B/C)** | Additional: `web/` electron wrapper, `main.ts` integration | High | Full Electron desktop shell with embedded browser | Revert to React SPA served by FastAPI |
| **3** | `browser-host/src/main/` (IPC handlers), `src/preload/` (contextBridge), Python provider client | Medium | Agent reads snapshot/text/screenshot, forbidden methods absent | Disable IPC handlers, remove provider client |
| **4** | `web/src/components/RightRail/BrowserContextPanel/`, prompt composition pipeline | Medium | Context panel displays, insert button works, no auto-injection | Remove context panel, remove insertion handler |
| **5** | `browser-host/src/plugins/` (new dir), plugin registry, `github-pr.ts`, `chatgpt-conversation.ts` | Medium | Plugin matches and extracts, fallback on failure, no crash | Remove plugin registration |
| **6** | Run orchestrator, run metadata schema, timeline component, Task Thread schema | Medium | Run metadata includes browserContext, timeline shows events, no hidden injection | Remove browserContext from metadata/timeline/thread schemas |
| **7** | `config.yaml` (feature flag), `hermes_cli/browser.py` (lifecycle), right rail settings UI, CI lint script | Medium | Flag gates everything, profile reset works, crash isolation works, boundary check passes | Set flag to OFF |

### Note on Option A vs Option B/C

Phase 2 currently assumes **Option A** (independent Electron child process)
as the lowest-risk starting point. If the Phase 0 audit discovers that a
production Electron host already exists, or if the decision is made to
migrate to Option B/C, the Phase 2 row in this matrix should be updated
accordingly. The remaining phases (3–7) are host-agnostic — they depend on
the BrowserContextProvider interface, not the host architecture.

---

## 13. Rollback Plan

Each phase is independently reversible. In addition, a global rollback
path exists via the feature flag.

### Per-phase rollback

| Phase | Rollback action | Residual state |
|-------|----------------|----------------|
| 0 | N/A (read-only) | None |
| 1 | Remove Browser tab from right rail tab bar; delete BrowserTab placeholder component | None |
| 2 (Option A) | Delete `hermes_cli/browser.py`; delete `browser-host/` directory | `~/.hermes/browser/` profile directory remains. Deletion optional — removing it clears login state |
| 2 (Option B/C) | Revert to pre-Electron app shell; restore FastAPI + React SPA boot | `~/.hermes/browser/` profile remains. Electron binaries may remain in `node_modules/` |
| 3 | Disable IPC handlers in Electron main process; remove Python provider client | Electron window still functional (Phase 2). Agent can no longer read context |
| 4 | Remove context panel component; remove prompt insertion handler | Provider API still functional (Phase 3). No UI path to prompt |
| 5 | Remove plugin registrations from registry | All pages fall back to generic DOM summary |
| 6 | Remove browserContext from run metadata, timeline, and Task Thread schemas | Provider API still functional (Phase 3). No workbench integration |
| 7 | Set `BROWSER_WORKSPACE_ENABLED` to `false` | All browser workspace code paths inert. Code remains in codebase |

### Global rollback

Set the feature flag `BROWSER_WORKSPACE_ENABLED: false` in `config.yaml`.
This gates all browser workspace code paths. The Browser tab does not appear.
No Electron child process spawns. No IPC handlers register.

### Profile/data cleanup

If the user wants to remove all browser workspace data:

1. Delete `~/.hermes/browser/` — removes cookies, localStorage, IndexedDB,
   cache, screenshots, and plugin state.
2. Delete `browser-host/` directory — removes the Electron host code.
3. Delete `hermes_cli/browser.py` — removes the CLI launcher.
4. Set feature flag to OFF — prevents any future accidental activation.

This returns Hermes to its pre-Browser-Workspace state with no residual
data.

---

## 14. Testing Strategy

### Phase 0: Implementation surface audit

- Manual inspection of the runtime codebase.
- Document answers to the 6 host questions in §4.
- Validation: all questions answered before Phase 1 begins.

### Provider contract tests (automated)

- `getCurrentSnapshot()` returns a valid `BrowserContextSnapshot` schema.
- `getTabs()` returns an array (may have length 1 in MVP).
- `getActiveTab()` returns a single TabInfo object.
- `captureScreenshot()` returns a valid PNG reference.
- `getReadableText()` returns a string ≤ 20 KB.
- `getSelectedText()` returns a string ≤ 10 KB.
- `getClipboardPreview()` returns a string ≤ 2 KB.
- `getRecentEvents(5)` returns an array of length ≤ 5.
- `subscribeToBrowserEvents()` returns an unsubscribe function.
- All size limits are enforced (clipping, not truncation).

### Manual Electron smoke tests

- **Screenshot nonblank test.** Navigate to `httpbin.org/ip`. Capture
  screenshot. Verify the PNG is non-empty and shows identifiable page
  content.
- **DOM text test.** Navigate to a page with known text. Call
  `getReadableText()`. Verify the text contains the expected content.
- **Selected text test.** Manually select text on the page. Call
  `getSelectedText()`. Verify the returned text matches the selection.
- **Clipboard test.** Manually copy text to clipboard. Enable clipboard
  sharing. Call `getClipboardPreview()`. Verify match. Disable clipboard
  sharing. Verify return is empty string.

### Proxy tests

- **System mode.** Navigate to `httpbin.org/ip`. Verify the origin IP
  matches the system browser's origin IP.
- **Direct mode.** Switch to Direct mode. Navigate to an internal-only URL
  (if available). Verify direct connection behavior.
- **Custom mode.** Set proxy to `http://127.0.0.1:7890`. Navigate to
  `httpbin.org/ip`. Verify page loads successfully.

### Login persistence tests

- Log into ChatGPT in the embedded browser.
- Close the Electron process.
- Restart the Electron process.
- Navigate to `https://chatgpt.com`. Verify still logged in.
- Repeat for GitHub.

### Read-only boundary check (automated)

- Grep or static analysis script scans the provider interface and IPC
  handler registration for forbidden method names:
  `click`, `type`, `submit`, `navigateAsAgent`, `executeJavaScript`,
  `sendInputEvent`, `dispatchInputEvent`.
- Must run in CI on every commit that touches the provider module.
- Must fail the build if any forbidden method name is found.

### Existing Workbench regression check

- All existing Agent Workbench features (Chat, Agent Run, Timeline,
  Changed Files, Review, Kanban) must continue to function when the
  feature flag is OFF.
- When the feature flag is ON but no browser context is inserted, all
  existing features must continue to function.
- Browser Workspace must not increase startup time by more than 500ms
  when feature flag is OFF (feature flag check only; no Electron spawn).

---

## 15. Risks And Open Decisions

| # | Risk / Decision | Impact | Mitigation |
|---|-----------------|--------|------------|
| 1 | **No current Electron host.** Hermes runtime has no Electron process. Phase 0 must confirm whether one exists or must be created. | Blocks Phase 2. | Phase 0 audit. Option A (independent child process) is the low-risk fallback. |
| 2 | **Option A child process lifecycle.** Launching and killing an Electron child process from the CLI adds complexity to process management. | Electron crash or zombie process could leave windows or ports open. | Reuse existing `ui-tui/` subprocess pattern. Implement health check and cleanup on CLI exit. |
| 3 | **IPC/API boundary between dashboard and Electron child.** The Python backend (FastAPI) and the Electron main process need a communication channel for context queries. | Without a clean channel, the Agent cannot read browser context. | Local HTTP endpoint in Electron main process (localhost-only, random port). Or Unix domain socket. |
| 4 | **Profile privacy.** `~/.hermes/browser/` stores cookies, localStorage, IndexedDB for all sites visited. This is sensitive user data. | Unauthorized access could leak login tokens. | File permissions (0600 for sensitive files). Clear documentation of what is stored. Profile reset feature. |
| 5 | **ChatGPT DOM changes.** ChatGPT frequently changes its page structure. The plugin extraction script may break. | Plugin returns null; falls back to generic DOM summary. User loses structured conversation context. | Plugin health monitoring. Versioned plugin scripts. Fallback is graceful, not a crash. |
| 6 | **GitHub DOM changes.** GitHub also changes its DOM, though less frequently than ChatGPT. | Same as #5. | Same mitigation. |
| 7 | **Proxy mode complexity.** Three proxy modes (System/Direct/Custom) add configuration surface. Custom mode requires user to know their proxy URL. | Misconfiguration leads to "page not loading" errors with no clear user feedback. | Clear error states in Phase 7. Default to System mode. |
| 8 | **Memory pressure.** An Electron child process with a WebContentsView for a heavy SPA (ChatGPT, GitHub) can consume significant RAM. | Could impact system performance, especially on lower-RAM machines. | Phase 7 memory monitoring. Configurable threshold. Warning, not auto-kill. |
| 9 | **Screenshot retention.** Screenshots can contain sensitive page content. Retention policy must balance usefulness with privacy. | Stale screenshots could leak private information if the profile directory is accessed. | Max 10 screenshots. Stored in Hermes profile directory with appropriate permissions. Users can clear manually. |
| 10 | **Future approval-gated actions.** Design documents reference future click/type/navigate capabilities. These are explicitly excluded from MVP. | Scope creep. Implementing actions prematurely breaks the read-only boundary. | All action methods are forbidden in MVP. Approval gate design is documented but not implemented. Separate ActionProvider interface (not part of BrowserContextProvider). |
| 11 | **External browser adapter as fallback.** Spec says external adapters are fallback. Should they share the BrowserContextProvider interface? | If external adapter integration uses a different API shape, the Agent needs to handle two context formats. | Defer to post-MVP. BrowserContextProvider is designed for embedded browser. External adapters may use a separate provider type or an adapter shim. |
| 12 | **Phase 0 audit may reveal a different host architecture.** If the runtime already has a desktop shell we are unaware of, the entire Phase 2 plan changes. | Rewrites Phase 2–7 implementation strategy. | Phase 0 is intentionally first. All subsequent phases are contingent on Phase 0 findings. |

---

## 16. Recommended Immediate Next Step

**Do not implement Phase 1–7 yet.**

### Immediate action

**Perform Phase 0: Implementation Surface Audit.**

The audit must answer one question before any code is written:

> Where does the embedded Chromium host live relative to the current Hermes
  runtime?

### Specific steps

1. Locate the Hermes runtime codebase (not this docs repository). It may be
   at `~/.hermes/hermes-agent/` or a separate repository path.
2. Inspect `hermes_cli/main.py`, `cli.py`, `dashboard/main.py`, and
   `web/src/` to identify the current app shell.
3. Confirm whether any Electron main/preload/renderer files exist.
4. Answer the 6 questions in Phase 0 §4.
5. Document the findings in a Phase 0 audit output.

### Recommendation

Based on current evidence (no Electron host found in the visible surface),
**Option A — independent Electron child process** is the lowest-risk starting
point. It mirrors the existing `ui-tui/` subprocess pattern and does not
require modifying the Python backend or React SPA shell.

### After Phase 0

Once the audit confirms (or revises) the host architecture:

1. Write a narrow Phase 1 implementation task list (Browser tab placeholder
   in the right rail). This is UI-only and carries no host dependency risk.
2. Write a narrow Phase 2/Option A implementation task list (Electron child
   process with URL bar and persistent profile). This is the first phase
   that requires host confirmation.
3. Do not plan Phase 3–7 tasks in detail until Phase 0–2 are complete and
   validated. The host decision and initial integration experience will
   inform the later phases.

### What not to do

- Do not start writing Electron host code without Phase 0 audit results.
- Do not assume the current React SPA can host a Chromium surface.
- Do not plan the full plugin layer before proving Phase 2 works.
- Do not design Agent action integration before the read-only MVP is
  validated.
