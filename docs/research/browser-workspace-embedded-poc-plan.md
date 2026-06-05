# Hermes Embedded Browser Workspace — PoC Plan

Date: 2026-06-06
Status: Read-only plan (no implementation commitment)
Based on:
- [Browser Workspace MVP Evaluation](./browser-workspace-mvp-evaluation.md)
- [Embedded Browser Workspace v0.1 Spec](./browser-workspace-embedded-mvp-spec.md)

---

## 1. Purpose

This PoC exists to answer one question:

> Can Hermes host an embedded Chromium surface that persists login state,
> inherits system proxy, supports multiple tabs, and exposes read-only
> page context — without crashing, leaking credentials, or breaking the
> Electron process?

The PoC is:

- **Disposable.** It will not become production code. If it passes, a
  separate adapter design phase follows.
- **Isolated.** It does not connect to Hermes runtime, the Agent execution
  loop, kanban, review/QA, or the desktop IPC layer.
- **Read-only.** The embedded browser surface is a normal user-facing web
  view. The PoC only reads context from it; no Agent-side action is wired.
- **Low-risk.** It runs as a standalone Electron app (or minimal
  `electron-vite` scaffold). If it breaks, it does not affect any Hermes
  subsystem.

---

## 2. Success Criteria

The PoC is successful only if **all** of the following are verified on a
real macOS machine with typical network conditions (corporate proxy or home
WiFi).

| # | Criterion | How to verify | Priority |
|---|---|---|---|
| 1 | Embedded browser opens a real web page | Navigate to `https://example.com`; page renders | Must |
| 2 | Login state persists across app restart | Log into ChatGPT, quit, relaunch, confirm still logged in | Must |
| 3 | ChatGPT login persists | See #2; repeat after 1-hour idle to rule out short-lived session issues | Must |
| 4 | Claude login persists | Same procedure as ChatGPT | Must |
| 5 | GitHub login persists | Log into github.com, navigate to a private repo PR, quit, relaunch | Must |
| 6 | Vercel login persists | Log into vercel.com, navigate to a deployment log, quit, relaunch | Must |
| 7 | System proxy is used | Set system proxy (or verify in corporate network); confirm the page loads through the proxy | Must |
| 8 | Multiple tabs work | Open 3 tabs (GitHub PR, ChatGPT, Vercel); switch between them; each keeps own navigation state | Must |
| 9 | Active tab URL and title are readable | Dump active tab URL/title to debug panel; compare with what the user sees | Must |
| 10 | Screenshot is generated | Call `capturePage()` on active tab; save as PNG; visually inspect | Must |
| 11 | DOM / readable text is extracted | Call `document.body.innerText` on active tab; output first 500 chars to debug panel | Must |
| 12 | Selected text is captured | Select text on page; call `window.getSelection().toString()`; output to debug panel | Must |
| 13 | Clipboard snippet is captured | Copy text (e.g., an error log); call `electron.clipboard.readText()`; output to debug panel | Must |
| 14 | Navigation and tab events are emitted | Log `page-load-committed`, `page-title-updated`, `tab-created`, `tab-closed` events to debug console | Must |
| 15 | Agent has no call path to `click`/`type`/`submit`/`navigate` | Code review: confirm the debug panel only reads; no IPC channel exposes write actions | Must |
| 16 | Open tabs survive app restart | Open 3 tabs, quit, relaunch, confirm URL/title/state are restored separately from login state | Should |

Fail condition: any "Must" criterion fails.

---

## 3. Non-goals

The following are **explicitly out of scope** for this PoC:

| Non-goal | Why excluded |
|---|---|
| Chrome Web Store extension compatibility | Hermes-native plugin layer is the target |
| Agent auto-click / auto-type / auto-submit | Read-only MVP boundary |
| Agent auto-navigate | Read-only MVP boundary |
| Full Hermes Desktop UI integration | PoC is standalone |
| Connection to production Hermes runtime | PoC is isolated |
| Long-term storage of sensitive content | PoC profile is disposable |
| External browser adapter (mcp-chrome etc.) | This PoC tests embedded-only |
| Multiple browser profiles | Single default profile only |
| Download / upload handling | Later |
| Plugin layer implementation | Later — PoC only validates raw context extraction |
| Prompt injection into Agent | No Agent in PoC |
| Mobile / narrow layout | Desktop only |
| Windows / Linux | macOS first |

---

## 4. PoC Shape

### Recommended form factor

A **standalone Electron app** with:

```
┌─────────────────────────────────────────────┐
│  Toolbar                                     │
│  [Tab 1] [Tab 2] [Tab 3] [+] [Debug Panel]  │
├─────────────────────────────────────────────┤
│                                              │
│  Embedded Browser Surface                    │
│  (WebContentsView)                           │
│                                              │
├─────────────────────────────────────────────┤
│  Debug Panel (toggleable)                    │
│  ┌─────────────────────────────────────────┐│
│  │ Snapshot JSON                            ││
│  │ Screenshot thumbnail                     ││
│  │ Selected text                            ││
│  │ Clipboard preview                        ││
│  │ DOM summary (first N chars)              ││
│  │ Event log                                ││
│  │ [Copy Snapshot] [Save Screenshot]        ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### What it contains

| Component | Description |
|---|---|
| Embedded browser | Single `WebContentsView` or `BrowserView` per tab |
| Tab bar | Simple tab strip: title, close button, "+" for new tab |
| Debug panel | Side or bottom panel showing live `BrowserContextSnapshot` |
| Profile directory | `~/.hermes-poc/browser/` — isolated from Hermes and system Chrome |
| Reset script | Shell command to delete `~/.hermes-poc/` for a clean start |

### Technology choices (tentative, not binding)

| Choice | Reasoning |
|---|---|
| Electron `WebContentsView` | Recommended over deprecated `BrowserView` in Electron 30+ |
| `electron-vite` scaffold | Fastest path to a working Electron app with React debug panel |
| Chromium default profile | Uses Electron's built-in `session.defaultSession` with a custom `userData` path |
| `webContents.capturePage()` | Built-in screenshot API, no extra dependency |
| `webContents.executeJavaScript()` | For DOM/selection/readable text extraction |
| `electron.clipboard.readText()` | Built-in clipboard API |
| `webContents.on('page-title-updated')` | Built-in event for title changes |

---

## 5. BrowserContextSnapshot

The PoC debug panel will render a snapshot in this shape:

```jsonc
{
  "captured_at": "2026-06-06T10:00:00+08:00",
  "profile_id": "default",
  "active_tab": {
    "id": "tab-1",
    "url": "https://github.com/nousresearch/hermes-agent/pull/1234",
    "title": "Fix memory leak in gateway dispatch",
    "page_type": "github_pull_request",     // from URL heuristic only (no plugin)
    "screenshot_ref": "snapshots/tab-1-20260606T100000.png",
    "dom_summary": "#1234 Fix memory leak...\n\nSummary:\n...\nFiles changed 3...",
    "selected_text": "useEffect cleanup is missing",
    "clipboard_text_preview": "Error: Cannot read properties of undefined (reading 'dispatch')",
    "is_loading": false,
    "can_go_back": true,
    "can_go_forward": false
  },
  "tabs": [
    {
      "id": "tab-1",
      "url": "https://github.com/nousresearch/hermes-agent/pull/1234",
      "title": "Fix memory leak in gateway dispatch",
      "active": true
    },
    {
      "id": "tab-2",
      "url": "https://chatgpt.com/c/abc123",
      "title": "Debugging React useEffect patterns",
      "active": false
    }
  ],
  "recent_events": [
    { "ts": "2026-06-06T09:59:58+08:00", "type": "tab-created", "tab_id": "tab-1" },
    { "ts": "2026-06-06T09:59:59+08:00", "type": "page-load-committed", "tab_id": "tab-1", "url": "https://github.com/..." },
    { "ts": "2026-06-06T10:00:00+08:00", "type": "page-title-updated", "tab_id": "tab-1", "title": "Fix memory leak..." }
  ],
  "permissions": {
    "clipboard": "granted_by_user",
    "screenshot": "granted_by_user"
  }
}
```

### Field notes

| Field | Source | Max size (PoC) |
|---|---|---|
| `url` | `webContents.getURL()` | Full |
| `title` | `webContents.getTitle()` | Full |
| `page_type` | URL-heuristic only: `github.com/*/pull/*` → `github_pull_request`, etc. | N/A |
| `screenshot_ref` | `webContents.capturePage()` → PNG file | 500 KB, max 1920px width |
| `dom_summary` | `document.body.innerText` via `executeJavaScript`, first 3000 chars | 3000 chars |
| `selected_text` | `window.getSelection().toString()` | 3000 chars |
| `clipboard_text_preview` | `electron.clipboard.readText()`, first 1000 chars | 1000 chars |
| `recent_events` | In-memory event buffer, last 50 events | N/A |
| `permissions` | Static map; PoC hardcodes `granted_by_user` | N/A |

### Read-only wrapper contract

The PoC must keep the browser control surface behind a wrapper that exposes
only read methods to the debug panel and any future Agent-facing boundary.

Allowed wrapper methods:

```text
getURL(tabId)
getTitle(tabId)
getTabs()
capturePage(tabId)
getReadableText(tabId)
getSelectedText(tabId)
getClipboardPreview()
getRecentEvents()
```

Internally, the PoC may use `webContents.executeJavaScript()` only for static,
read-only scripts such as `document.body.innerText` and
`window.getSelection().toString()`.

Forbidden wrapper methods:

```text
loadURL(tabId, url)
click(selector)
type(selector, text)
submit(selector)
dispatchInputEvent(...)
executeJavaScript(userOrAgentProvidedCode)
insertText(...)
sendInputEvent(...)
```

Pass condition:

```text
No IPC channel, debug panel action, menu item, keyboard shortcut, or exported
wrapper method can cause navigation, clicking, typing, form submission, or
user/Agent-provided script execution.
```

---

## 6. Test Pages

Pages selected based on the MVP evaluation document's user scenarios:

| # | Test page | URL pattern | Why this page |
|---|---|---|---|
| 1 | GitHub PR | `github.com/*/pull/*` | Core dev workflow; verifies GitHub login persistence |
| 2 | Vercel deployment/build log | `vercel.com/*` | Deployment workflow; tests dynamic content extraction |
| 3 | Linear issue | `linear.app/*` | Issue tracking; tests SPA login persistence |
| 4 | ChatGPT conversation | `chatgpt.com/*` or `chat.openai.com/*` | AI workflow; tests complex SPA DOM extraction |
| 5 | Claude conversation | `claude.ai/*` | AI workflow; tests second SPA with different auth model |

For each page, the PoC will:

1. Navigate to the page.
2. Log in if needed.
3. Wait for page to fully render.
4. Capture snapshot.
5. Select some text and capture again.
6. Copy something and capture again.

The PoC will repeat steps 1-6 after restart to validate login persistence.

---

## 7. Validation Procedure

### Phase A: Setup

1. Scaffold standalone Electron app with `electron-vite`.
2. Configure `userData` path to `~/.hermes-poc/browser/`.
3. Set up `WebContentsView` for the main browser surface.
4. Build a minimal React debug panel showing snapshot JSON.
5. Run `rm -rf ~/.hermes-poc/` before first launch to start clean.

### Phase B: Basic rendering

1. Launch the PoC.
2. Observe: a blank browser surface + debug panel.
3. Enter `https://example.com` in a URL bar (manual input, no Agent).
4. Observe: page renders. Debug panel shows URL and title.
5. Click "Capture Snapshot" in debug panel.
6. Observe: snapshot JSON populated with `url`, `title`, `is_loading: false`.
7. Save the snapshot JSON as `evidence/01-example-snapshot.json`.

### Phase C: Login persistence (for each test page)

1. Navigate to test page (e.g., `https://chatgpt.com`).
2. Log in manually.
3. Confirm login is successful (page shows user content).
4. Click "Capture Snapshot". Save as `evidence/02-chatgpt-logged-in.json`.
5. Quit the PoC.
6. Relaunch the PoC.
7. Navigate to same test page.
8. Confirm login persists without re-entering credentials.
9. Click "Capture Snapshot". Save as `evidence/03-chatgpt-after-restart.json`.
10. Repeat for Claude, GitHub, Vercel.

Record for each:

- Login persisted? (Yes / No / Partial — describe)
- Any re-authentication prompt?
- Any session-expired page?
- Evidence file paths.

Pass condition:

```text
After restart, each target service opens without re-entering credentials and
the debug snapshot still reports the correct URL/title. A partial pass is
allowed only when the site intentionally asks for second-factor confirmation
but still preserves the account session.
```

### Phase D: System proxy

1. If on a corporate network with proxy, the proxy is already active.
2. If on home WiFi, set a system proxy (System Preferences → Network → Proxies).
3. Launch PoC.
4. Navigate to `https://example.com`.
5. Confirm page loads.
6. In the terminal running the PoC, set `HTTP_PROXY`/`HTTPS_PROXY` to confirm.
7. Navigate to `https://httpbin.org/ip` and capture snapshot.
8. Verify the IP in the snapshot matches the proxy's exit, not the local IP.
9. Save snapshot as `evidence/04-proxy-test.json`.

If in a corporate network, also verify internal sites (e.g., internal GitHub
Enterprise, internal Vercel) load through the proxy.

### Phase E: Multi-tab

1. Open Tab 1: GitHub PR page.
2. Open Tab 2: ChatGPT conversation.
3. Open Tab 3: Vercel deployment log.
4. Switch tabs and confirm each keeps its own state.
5. Capture snapshot — verify `tabs` array shows all 3 with correct `active` flag.
6. Close Tab 2.
7. Capture snapshot — verify `tabs` array shows 2 entries.
8. Quit the PoC.
9. Relaunch the PoC.
10. Confirm the remaining open tab URLs/titles are restored.
11. Capture snapshot — verify restored tabs are present and login state still works.
12. Save snapshots as `evidence/05-multi-tab.json`,
    `evidence/06-tab-close.json`, and `evidence/07-tab-restore.json`.

Pass condition:

```text
The tabs array has correct tab count, active tab, URL, and title before close,
after close, and after restart. Tab restoration is evaluated separately from
login persistence: restored tabs may be reloaded, but their URLs/titles must
survive restart.
```

### Phase F: Context extraction

On the GitHub PR tab:

1. Select a line of code in the PR diff.
2. Capture snapshot — verify `selected_text` matches.
3. Copy the PR title or an error from another tab.
4. Capture snapshot — verify `clipboard_text_preview` matches (first 1000 chars).
5. Save as `evidence/08-context-extraction.json`.

On the Vercel tab:

1. Select a build error line.
2. Copy the full error to clipboard.
3. Capture snapshot — verify both `selected_text` and `clipboard_text_preview`.

Pass condition:

```text
Selected text exactly matches the user's visible selection after whitespace
normalization. Clipboard preview matches the first 1000 characters of the
current clipboard text and is empty only when the OS clipboard is empty.
```

### Phase G: Screenshot

1. On the GitHub PR tab, click "Save Screenshot".
2. Inspect the saved PNG.
3. Confirm the screenshot matches what the user sees.
4. Measure file size — should be under 500 KB at reasonable resolution.
5. Repeat for ChatGPT and Vercel tabs.
6. Save screenshots as `evidence/09-screenshot-github.png`, etc.

Pass condition:

```text
Each screenshot is a non-empty PNG, visually matches the active tab, contains
no blank/black frame, and is under 500 KB at the PoC's configured capture
resolution.
```

### Phase H: DOM summary

1. On the GitHub PR tab, capture snapshot.
2. Inspect `dom_summary` field.
3. Confirm it contains readable text from the page (PR title, file names, diff
   content).
4. Confirm it does NOT contain raw HTML tags.
5. Confirm it is under 3000 characters.
6. Repeat for ChatGPT conversation page.
7. Save as `evidence/10-dom-summary.json`.

Pass condition:

```text
DOM summary contains human-readable page text, does not contain raw HTML tags,
and is under 3000 characters. If a page returns an empty summary, record it as
a page-specific failure and note whether an accessibility-tree fallback is
needed.
```

### Phase I: Events

1. Open the PoC with event logging enabled in the debug panel.
2. Perform actions: create tab, navigate to a page, switch tabs, close a tab.
3. Inspect the `recent_events` array in the snapshot.
4. Confirm events are ordered by timestamp.
5. Confirm event types match: `tab-created`, `page-load-committed`,
   `page-title-updated`, `tab-closed`.
6. Save as `evidence/11-events.json`.

Pass condition:

```text
Event timestamps are monotonic, event types match the expected enum, and the
active tab id in the snapshot matches the most recent tab-switch event.
```

### Phase J: Read-only boundary

1. Code review: search the PoC codebase for any IPC channel, menu item, or
   keyboard shortcut that could trigger `click`, `type`, `submit`, `navigate`,
   `executeJavaScript` with write semantics, or `eval`.
2. Confirm no such code path exists.
3. If using `executeJavaScript` for DOM selection or text extraction, confirm
   the scripts are static strings with no user/Agent-controlled input.
4. Confirm the Electron `webContents` wrapper exposes only read methods
   (`getURL`, `getTitle`, `capturePage`, static read-only
   `executeJavaScript`, etc.).
5. Confirm it does not expose `loadURL`, write-oriented
   `executeJavaScript`, `input.dispatchEvent`, `sendInputEvent`, click/type
   helpers, form submission helpers, or any user/Agent-provided script
   execution.
6. Document the review result in `evidence/12-read-only-review.txt`.

Pass condition:

```text
The PoC has no Agent-facing or debug-panel-facing path to click, type, submit,
navigate, dispatch input, or execute user/Agent-provided JavaScript. Any
manual URL entry by the human tester is explicitly out of the Agent boundary.
```

### Phase K: Phase-level pass/fail summary

At the end of the PoC, produce a summary table:

| Phase | Pass condition | Result | Evidence |
|---|---|---|---|
| A Setup | PoC launches with isolated profile | TBD | TBD |
| B Basic rendering | Example page renders and snapshot has URL/title | TBD | TBD |
| C Login persistence | Target services preserve login after restart | TBD | TBD |
| D System proxy | Browser traffic uses expected proxy exit | TBD | TBD |
| E Multi-tab | Tabs switch, close, and restore after restart | TBD | TBD |
| F Context extraction | Selection and clipboard are captured correctly | TBD | TBD |
| G Screenshot | PNG is non-empty, correct, and within size limit | TBD | TBD |
| H DOM summary | Summary is readable, bounded, and not raw HTML | TBD | TBD |
| I Events | Event log is ordered and matches user actions | TBD | TBD |
| J Read-only boundary | No write/action method is exposed | TBD | TBD |

---

## 8. Evidence To Capture

Save all evidence under `poc-evidence/` (not in the repo; can be `.gitignored`):

```
poc-evidence/
  01-example-snapshot.json
  02-chatgpt-logged-in.json
  02-chatgpt-logged-in-notes.txt       // "Login persisted? Yes. No re-auth."
  03-chatgpt-after-restart.json
  03-chatgpt-after-restart-notes.txt
  04-proxy-test.json
  04-proxy-test-notes.txt
  05-multi-tab.json
  06-tab-close.json
  07-tab-restore.json
  08-context-extraction.json
  09-screenshot-github.png
  09-screenshot-chatgpt.png
  09-screenshot-vercel.png
  10-dom-summary.json
  11-events.json
  12-read-only-review.txt
  13-phase-summary.md
  14-risks-observed.txt                // Any unexpected issues
  15-decision.txt                      // GO / PARTIAL / FALLBACK / STOP + rationale
```

For each evidence file, record:

- The command or action that produced it.
- Any relevant environment info (OS version, Electron version, network type).
- Whether the result matches the expected behavior.
- If not, what went wrong and whether there is a workaround.

---

## 9. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **ChatGPT / Claude block embedded Chromium.** Some services fingerprint browsers and may reject Electron's Chromium as "unsupported browser." | Medium | High | Test early in Phase C. If blocked, note in PARTIAL decision and limit supported pages. |
| R2 | **Login state not persisted.** Chromium may clear session cookies on quit if `userData` path is misconfigured. | Low | High | Verify cookie persistence with `session.defaultSession.cookies.get()` before and after restart. |
| R3 | **System proxy not inherited.** Electron may not pick up macOS system proxy if launched outside a Terminal with `HTTP_PROXY` set. | Medium | Medium | Explicitly configure proxy via `--proxy-server` flag if automatic inheritance fails. |
| R4 | **`capturePage()` blocked by CSP.** Some pages may prevent screenshots via Content Security Policy or `crossOriginIsolated` restrictions. | Low | Medium | Test on all 5 test pages in Phase G. Fall back to offscreen rendering if needed. |
| R5 | **`executeJavaScript` blocked by CSP.** Pages with strict CSP may block inline script execution for DOM extraction. | Low | Medium | Use `webContents.executeJavaScript()` which runs in the main world (bypasses CSP). If blocked, use accessibility tree instead. |
| R6 | **Clipboard access requires user gesture.** `electron.clipboard.readText()` may return empty if no recent clipboard write occurred. | Low | Low | Verify immediately after copying. If unreliable, note as limitation and require user to manually paste. |
| R7 | **Sensitive data leakage in debug panel.** DOM summary may contain tokens, private messages, or credentials. | Medium | High | Redact obvious patterns (bearer tokens, key= in URLs) in the debug panel output. Do not save snapshots without manual review. |
| R8 | **Electron API version mismatch.** `WebContentsView` API differs between Electron 30, 31, and 32. | Low | Medium | Pin Electron version in PoC. Document which version was tested. |
| R9 | **Memory pressure from multiple tabs.** Each active `WebContentsView`/renderer process adds ~100-200 MB. 5 tabs = ~500 MB-1 GB. | Medium | Medium | Monitor memory in Activity Monitor. If too high, limit PoC to 3 tabs. Note for production: lazy-load and tab discarding. |
| R10 | **Real Hermes integration complexity.** Even if PoC passes, wiring the embedded browser into Hermes Desktop's existing renderer, IPC, and right-rail UI is non-trivial. | High | Medium | Explicitly document integration assumptions in the post-PoC adapter design doc. This PoC does not attempt integration. |

---

## 10. Decision After PoC

After completing the validation procedure and reviewing all evidence, the
decision is one of four outcomes:

### GO

The embedded browser passes all 15 success criteria. All 5 test pages work
with persistent login. System proxy, screenshot, DOM, selected text, and
clipboard all function correctly. No read-only boundary violations found.

**Next step:** Begin Hermes Browser Workspace adapter design phase.
Integrate the embedded browser into Hermes Desktop's right rail, define the
`BrowserContextProvider` interface, and wire context into the Agent prompt
system.

### PARTIAL

The embedded browser is fundamentally functional, but one or more test pages
have issues (e.g., ChatGPT blocks embedded Chromium, or Vercel login does not
persist due to short session tokens). The core capabilities (proxy, tabs,
screenshot, DOM, selection, clipboard, read-only boundary) all pass.

**Next step:** Limit the initial supported page set to the pages that pass.
Begin Hermes adapter design for the passing pages. Add the failing pages to
a follow-up compatibility investigation. Consider adding a user-visible
"compatibility note" for unsupported pages.

### FALLBACK

The embedded browser fails on multiple critical criteria (e.g., login
persistence does not work, or system proxy cannot be inherited, or
screenshot/DOM extraction is blocked by CSP on all test pages). The embedded
approach is not viable for the current use cases.

**Next step:** Shift to the external browser adapter path. Validate
`mcp-chrome` as the primary fallback, followed by `BrowserMCP`. Update the
MVP evaluation document to reflect the decision.

### STOP

The embedded browser introduces a security, stability, or privacy risk that
cannot be mitigated at reasonable cost (e.g., credential leakage by design,
or unavoidable crash on common pages).

**Next step:** Do not proceed with Browser Workspace in any form. Document
the specific reasons in a "Browser Workspace Stop Decision" note. Revisit
only if the underlying technology (Electron, Chromium, or the target pages)
changes materially.

---

## 11. Open Questions

These are questions the PoC may help answer, or that may need to be resolved
before the adapter design phase:

| # | Question | Relevance |
|---|---|---|
| Q1 | **`WebContentsView` vs `BrowserView` vs `BrowserWindow`?** The PoC will test `WebContentsView` (Electron 30+ recommended API). If it has blocking issues, `BrowserView` or a separate `BrowserWindow` are fallbacks. The PoC should note which API was used and any issues encountered. | Architecture |
| Q2 | **Where should the profile live?** The PoC uses `~/.hermes-poc/browser/`. The production path would be `~/.hermes/browser/`. Is a single flat directory sufficient, or does Hermes need per-profile subdirectories (`~/.hermes/profiles/work/browser/`)? | Storage |
| Q3 | **Multiple browser profiles?** The PoC uses a single profile. Should Hermes support per-Hermes-profile browser profiles (e.g., work profile vs personal profile with different logins)? If yes, the storage layout needs to support it from day 1. | Product |
| Q4 | **Downloads and uploads?** The PoC does not handle downloads. Should the embedded browser support file downloads? If yes, where do they go (`~/.hermes/browser/Downloads/` or `~/Downloads/`)? Should file uploads (e.g., attaching a file to a GitHub issue) be supported? | Product |
| Q5 | **Should the user be able to edit the URL?** The PoC URL bar is manually editable (for testing convenience). In production, should the URL bar be read-only (Agent observes, user navigates via page links) or user-editable? | UX |
| Q6 | **Should popups be allowed?** Many sites (GitHub OAuth, Vercel deploy previews) open popups. Should the embedded browser allow `window.open()`? If yes, should popups open as new tabs or separate windows? | UX / Security |
| Q7 | **When should the plugin layer be introduced?** The PoC uses only URL heuristics for `page_type`. The Hermes-native plugin layer (GitHub PR plugin, Vercel log plugin, etc.) is part of the v0.1 spec but not tested in this PoC. Should plugin integration be part of the next PoC or deferred to the adapter phase? | Roadmap |
| Q8 | **Does the PoC need an Agent mock?** The PoC has no Agent integration. Should there be a mock Agent that reads the snapshot and responds, to validate that the snapshot shape is sufficient for real Agent use? Or is manual inspection of the snapshot JSON sufficient? | Validation |
| Q9 | **What Electron version should the PoC target?** Hermes Desktop currently uses Electron from the `electron-vite` scaffold. The PoC should match the same Electron major version to avoid migration surprises. | Dependency |
| Q10 | **Should the PoC be a standalone repo or a directory inside hermes-desktop?** Standalone repo is recommended for true isolation. Inside hermes-desktop as a `poc/` subdirectory would simplify later integration but risks accidental coupling. | Process |

---

*End of PoC Plan. No implementation commitment. No code. All decisions deferred to post-PoC evidence review.*
