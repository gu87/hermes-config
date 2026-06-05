# Hermes Embedded Browser Workspace — PoC Results

Date: 2026-06-06
Status: PoC results (read-only, no implementation commitment)
Based on:
- [Browser Workspace MVP Evaluation](./browser-workspace-mvp-evaluation.md)
- [Embedded Browser Workspace v0.1 Spec](./browser-workspace-embedded-mvp-spec.md)
- [Embedded Browser Workspace PoC Plan](./browser-workspace-embedded-poc-plan.md)
PoC code: `/tmp/hermes-browser-poc`
Evidence directory: `/tmp/hermes-browser-poc/poc-evidence`

---

## 1. Executive Summary

**Decision: GO.**

The embedded browser workspace is feasible enough to proceed to adapter
design. Core capabilities — page rendering, login state persistence across
restarts, system proxy inheritance, custom proxy configuration, and read-only
context extraction (DOM, selection, clipboard) — all passed on real SaaS
pages.

The external browser adapter path is no longer the primary direction.

This is not a production readiness assessment. It answers one question: can
Hermes host an embedded Chromium surface that does what we need, without
crashing, leaking credentials, or breaking the read-only boundary. The
answer is yes.

---

## 2. Test Environment

| Item | Value |
|------|-------|
| PoC path | `/tmp/hermes-browser-poc` |
| Evidence path | `/tmp/hermes-browser-poc/poc-evidence` |
| Profile path | `/tmp/.hermes-poc/browser` |
| OS | macOS |
| Runtime | Electron embedded Chromium (electron-vite dev) |
| Proxy | Clash, local port 7890, Rule mode, US node |

---

## 3. Phase Results

| Phase | Area | Result | Evidence | Notes |
|-------|------|--------|----------|-------|
| B | Basic rendering / snapshot / screenshot | **PASS** | `01-example-snapshot.json`, `01-example-screenshot.png` | `https://example.com` rendered; active_tab.url = `https://example.com/`; PNG non-empty |
| C-1 | ChatGPT login persistence | **PASS** | `02-chatgpt-logged-in.*`, `03-chatgpt-after-restart.*` | Logged in once; after restart, `https://chatgpt.com` opened in logged-in state, no re-auth required |
| C-2 | GitHub login persistence | **PASS** | `04-github-logged-in.*`, `05-github-after-restart.*` | Same restart-then-verify flow; opened `https://github.com` already logged in |
| C-3 | Vercel login persistence | **SKIPPED** | — | User has no Vercel account; not a blocking gap |
| D-1 | Proxy — system mode | **PASS** | `08-proxy-system.*` | `https://httpbin.org/ip` showed same origin IP as system Chrome (68.64.149.38) |
| D-2 | Proxy — custom (127.0.0.1:7890) | **PASS** | `09-proxy-custom-7890.*` | `session.setProxy()` applied to dedicated partition; page loaded successfully through Clash |
| E | Context extraction — GitHub | **PASS** | `10-context-github.*` | DOM summary (3000 chars), selected_text, clipboard_text_preview all matched manual input |
| E | Context extraction — ChatGPT | **PASS** | `11-context-chatgpt.*` | Full conversation text captured from DOM; selection and clipboard matched exactly |

---

## 4. Evidence Files

| File | Size | Purpose |
|------|------|---------|
| `01-example-snapshot.json` | 6.7K | Basic rendering snapshot (`https://example.com`) |
| `01-example-screenshot.png` | 128K | Basic rendering screenshot |
| `02-chatgpt-logged-in.json` | 5.6K | ChatGPT snapshot after first login |
| `02-chatgpt-logged-in.png` | 35K | ChatGPT screenshot after first login |
| `03-chatgpt-after-restart.json` | 940B | ChatGPT snapshot after restart (no auth events) |
| `03-chatgpt-after-restart.png` | 35K | ChatGPT screenshot after restart |
| `04-github-logged-in.json` | 2.7K | GitHub snapshot after first login |
| `04-github-logged-in.png` | 99K | GitHub screenshot after first login |
| `05-github-after-restart.json` | 933B | GitHub snapshot after restart (no auth events) |
| `05-github-after-restart.png` | 105K | GitHub screenshot after restart |
| `08-proxy-system.json` | 849B | httpbin/IP snapshot (system proxy) |
| `08-proxy-system.png` | 8.3K | httpbin/IP screenshot (system proxy) |
| `08-proxy-system-notes.txt` | 437B | D-1 notes |
| `09-proxy-custom-7890.json` | 849B | httpbin/IP snapshot (custom proxy) |
| `09-proxy-custom-7890.png` | 8.3K | httpbin/IP screenshot (custom proxy) |
| `09-proxy-custom-7890-notes.txt` | 754B | D-2 notes |
| `10-context-github.json` | 5.7K | GitHub context extraction snapshot |
| `10-context-github.png` | 128K | GitHub context extraction screenshot |
| `10-context-github-notes.txt` | 1.2K | GitHub context notes |
| `11-context-chatgpt.json` | 6.7K | ChatGPT context extraction snapshot |
| `11-context-chatgpt.png` | 128K | ChatGPT context extraction screenshot |
| `11-context-chatgpt-notes.txt` | 1.1K | ChatGPT context notes |

---

## 5. What Passed

- Embedded browser renders real web pages (`example.com`, `httpbin.org`)
- Screenshot capture (`webContents.capturePage()`) produces valid PNG output
- Snapshot capture produces structured JSON with active_tab URL, title, tabs,
  and event log
- Persistent profile: session data (cookies, localStorage) survives process
  restart via `userData` path
- ChatGPT login state persists across Electron close/restart
- GitHub login state persists across Electron close/restart
- System proxy: embedded browser follows macOS system proxy (Clash) by default
- Custom proxy: `session.setProxy({ proxyRules })` on a dedicated partition
  works correctly
- DOM summary: `document.body.innerText` extraction via static
  `executeJavaScript` script, capped at 3000 chars
- Selected text: `window.getSelection().toString()` extraction works on both
  GitHub and ChatGPT
- Clipboard preview: `clipboard.readText()` returns user-copied content
- Read-only boundary: no click/type/submit/navigate API exposed to renderer
- `executeJavaScript` used only for built-in, static, non-parameterized scripts

---

## 6. What Was Skipped

| Item | Reason |
|------|--------|
| Claude web login persistence | User does not have a Claude web account; Claude usage is API-based |
| Vercel login persistence | User does not have a Vercel account |
| Linear / Feishu login persistence | Not in scope for this PoC round |
| Chrome Web Store extension compatibility | Not relevant to embedded browser MVP |
| Agent click/type/submit | Deliberately excluded — read-only observation only |
| Multiple tabs / tab management | Single-tab WebContentsView in this PoC; multi-tab is adapter-layer concern |
| Plugin / extension system for DOM extraction | Current static script approach is sufficient for MVP; SPA-aware extraction is future work |

---

## 7. Known Risks

- **Site coverage is not universal.** ChatGPT and GitHub passed; other SaaS
  platforms cannot be automatically inferred. Each new service requires its
  own verification.
- **Long-term session compatibility.** While login persistence worked on the
  two tested services, Electron's Chromium version drift or service-side
  security changes could affect it over time.
- **DOM extraction for complex SPAs.** The current approach
  (`document.body.innerText`) captures all visible text. SPAs with heavy
  virtual DOM, shadow roots, or dynamic content may require a plugin-based
  extraction layer.
- **Selected text requires user action.** The Agent cannot programmatically
  select text; it only observes what the user has already selected.
- **Clipboard is user-gated.** The Agent only reads what the user explicitly
  copies. This is by design (privacy boundary), but it also limits context.
- **Proxy behavior is Clash-dependent.** Custom proxy mode was tested only
  against a local Clash instance at `127.0.0.1:7890`.
- **Evidence is in `/tmp`.** On macOS, `/tmp` is not guaranteed persistent
  across reboots. Evidence files exist for traceability, not as long-term
  storage.
- **PoC is not production code.** The PoC is a disposable single-window
  electron-vite scaffold. It will not become the production implementation.

---

## 8. Decision

**Decision: GO.**

Rationale:

1. Core embedded browser feasibility passed — pages render, screenshots and
   snapshots are captured reliably.
2. Login state persistence passed on two major SaaS platforms (ChatGPT,
   GitHub) with a clean restart-then-verify flow.
3. Proxy validation passed in both system and custom modes against a real
   Clash instance.
4. Context extraction (DOM, selection, clipboard) passed on both GitHub
   and ChatGPT with exact match verification.
5. Read-only boundary held throughout — no Agent-facing action methods were
   exposed.

The primary risk (does Electron embedded Chromium actually work for this
use case) is resolved in the affirmative for the tested scenarios.

---

## 9. Recommended Next Step

The PoC is complete. The next step is not more PoC work, but adapter design.

### `BrowserContextProvider` adapter design

Define the interface that abstracts the embedded browser surface from the
rest of Hermes:

- **Production `BrowserContextProvider` interface.** Define the data shape
  and method signatures that Hermes subsystems (Agent, UI) consume. This
  decouples Hermes from the specific rendering engine.
- **Browser Workspace storage/profile path.** Decide the production
  `userData` path (e.g. `~/.hermes/browser/`) and profile isolation
  strategy between workspaces.
- **Right rail UI integration.** Design how the embedded browser surface
  slots into the existing Hermes Desktop right-rail workspace panel
  layout.
- **Hermes-native plugin API.** Define a read-only extraction plugin
  interface so site-specific DOM parsers can be added without modifying
  core Hermes code.
- **Approval-gated action boundary.** Define the policy and mechanism for
  when/how the Agent may eventually request write actions (click, type) in
  the browser workspace — with explicit user approval gating.
