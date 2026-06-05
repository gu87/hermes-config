# Hermes Browser Workspace — Phase 0: Implementation Surface Audit

Date: 2026-06-06
Status: Read-only audit (no code changes)
Based on:
- [Browser Workspace MVP Implementation Plan](../architecture/browser-workspace-mvp-implementation-plan.md)
- [BrowserContextProvider Adapter Design](../architecture/browser-context-provider-design.md)
- [Embedded Browser Workspace PoC Results](./browser-workspace-embedded-poc-results.md)
- [Embedded Browser Workspace v0.1 Spec](./browser-workspace-embedded-mvp-spec.md)

Audit target: `/Users/gu/.hermes/hermes-agent/` (runtime codebase)
Audit scope: Read-only inspection. No code changes, no `npm install`, no
service starts.

---

## 1. Executive Summary

**Finding: There is no production Electron host in the Hermes runtime.**

The Hermes runtime has three surfaces — a React SPA dashboard (`web/`), an
Ink-based terminal TUI (`ui-tui/`), and a Python prompt_toolkit REPL
(`cli.py`). None of them are Electron apps. No `electron` dependency exists
in any `package.json`. No `main.js`, `preload.js`, or `renderer.js` files
exist outside `node_modules`.

**Recommendation: Option A — Independent Electron child process — remains
the recommended path for Phase 2 (embedded browser host).**

The existing architecture already uses child processes for the TUI gateway
(`subprocess.Popen` from `hermes_cli/main.py` to launch the Node.js TUI, with
JSON-RPC over stdio). The Electron host for Browser Workspace would follow
the same pattern: Hermes CLI launches an Electron child process, communicates
over a local HTTP endpoint or Unix socket.

**Phase 1 (Browser tab shell) can proceed immediately** using the existing
dashboard plugin system (`plugins/*/dashboard/manifest.json` → tab
registration in the React SPA sidebar). This is UI-only and carries zero host
dependency risk.

---

## 2. Evidence

| Path | Finding | Implication |
|------|---------|-------------|
| `hermes-agent/package.json` | No `electron` dependency. Only `agent-browser` (cloud browser proxy). | No Electron runtime. Cannot embed Chromium directly. |
| `hermes-agent/web/package.json` | Vite + React SPA. No electron. | Web dashboard is a browser-served app, not an Electron renderer. |
| `hermes-agent/ui-tui/package.json` | Ink + React terminal TUI. No electron. | Terminal app, not a desktop window host. |
| `hermes-agent/website/package.json` | Docusaurus documentation site. | Not a runtime surface at all. |
| `hermes-agent/hermes_cli/web_server.py` | FastAPI server (8,401 LOC). Serves Vite-built React SPA on `localhost:9119`. | This is the dashboard backend. It already has a plugin system that discovers and serves dashboard tab plugins. |
| `hermes-agent/hermes_cli/main.py` | Main CLI entry (12K+ LOC). Uses `subprocess.Popen` extensively for TUI gateway launch. | Proven child-process pattern exists. Elective Electron host would follow same pattern. |
| `hermes-agent/tui_gateway/server.py` | JSON-RPC gateway between Python backend and Node.js TUI via stdio transport. | Structured IPC between Python and Node.js already exists. Can be referenced for Electron IPC. |
| `hermes-agent/plugins/browser/` | Contains Firecrawl, BrowserBase, and BrowserUse cloud providers. | These are Agent browser-automation tools, NOT an embedded browser workspace. Different concern. |
| `hermes-agent/plugins/example-dashboard/dashboard/manifest.json` | Dashboard plugin manifest: `{name, label, tab: {path, position}}` | Existing plugin tab pattern. Browser Workspace can register as a dashboard plugin tab for Phase 1. |
| `hermes-agent/plugins/kanban/dashboard/manifest.json` | Kanban dashboard plugin: same manifest pattern with `entry: dist/index.js` | Production example of a self-contained dashboard plugin tab. |
| `hermes-agent/web/src/plugins/` | Plugin registry: `registerPlugin(name, Component)`, `PluginPage`, `PluginSlot` | The web dashboard already has a plugin system for adding custom tabs. Phase 1 fits here. |
| `hermes-agent/web/src/App.tsx` | React SPA with sidebar nav (Chat, Operations, Sessions, ..., Skills, Plugins, Profiles). No right rail. Layout is sidebar + main content. | "Right rail" in the spec maps to "sidebar tab" in the current dashboard. Terminology adjustment needed. |
| `hermes-agent/providers/` | `base.py` + `__init__.py` abstract provider pattern. | Existing provider abstraction. A future `BrowserContextProvider` could follow this pattern. |
| `hermes-agent/web/src/components/ChatSidebar.tsx` | Chat session sidebar component (modified, unstaged). | Evidence of active UI development. Chat is the primary work surface, not a browser. |
| Electron main/preload/renderer search | Zero results outside `node_modules`. | Confirmed: no Electron host exists anywhere in the runtime. |
| `hermes-agent/node_modules/electron-to-chromium/` | Only found in dev dependency tree (browserslist data). | Not an Electron installation — just version mapping data for autoprefixer. |

---

## 3. Current Workbench Surface

### Production surface: React SPA served by FastAPI

The primary user-facing surface is the React web dashboard, served by
`hermes_cli/web_server.py` on `http://127.0.0.1:9119`.

**Launch command:** `hermes dashboard` (from CLI) or `hermes dashboard --tui`
(for embedded chat).

**Layout:** Sidebar navigation on the left + main content area.

**Sidebar entries (built-in):**
- Chat (when `--tui` flag enabled)
- Operations
- Sessions
- Analytics
- Models
- Agents
- Delegations
- Runs
- Logs
- Cron
- Skills
- Plugins
- Profiles
- Config
- Env
- Documentation

**Plugin tabs (registered via `plugins/*/dashboard/manifest.json`):**
- Kanban (`/kanban`, positioned `after:skills`)
- Example (`/example`, positioned `after:skills`)

**No right rail exists.** The spec's "right rail" concept maps to the
existing **sidebar + tabs** pattern. A Browser Workspace tab would appear
as a sidebar nav item, and its content would render in the main content area.
This is a terminological difference, not an architectural blocker.

### Secondary surface: Terminal TUI

`ui-tui/` provides an Ink-based terminal UI, launched as a child process by
the Python CLI. It communicates via JSON-RPC with the `tui_gateway`.

### Tertiary surface: Python REPL

`cli.py` provides an interactive prompt_toolkit REPL with slash commands.
This is a developer/admin tool, not the primary end-user surface.

### Key takeaway

All three surfaces are served/routed by the Python backend. The web dashboard
is the richest surface and the natural place for Browser Workspace UI
integration. The existing plugin system already supports dashboard tabs.

---

## 4. Electron / Desktop Surface Search

### Package.json audit

| `package.json` | Has `electron`? | Notes |
|----------------|:---:|-------|
| `hermes-agent/package.json` | No | Only `agent-browser` |
| `web/package.json` | No | Vite + React |
| `ui-tui/package.json` | No | Ink + React |
| `website/package.json` | No | Docusaurus |

### File pattern search

Searched for: `main.js`, `preload.js`, `renderer.js`, `main.ts`, `preload.ts`,
`electron-builder*`, `forge.config*` across the entire `hermes-agent/`
directory tree (excluding `node_modules/`).

**Result: Zero matches.**

### Doctree search

Searched for: `electron` in all source files (excluding `node_modules/`).
Only hits were in `electron-to-chromium` (browserslist data) and xterm
WebGL addon (platform detection). None are Electron runtime.

### Existing `plugins/browser/` directory

This directory contains cloud browser providers (Firecrawl, BrowserBase,
BrowserUse) for **Agent-driven browser automation**. These are tools the
Agent invokes to navigate and click on pages — the opposite of the read-only
Browser Workspace model. They cannot be reused as an embedded browser host.

### Conclusion

No Electron host exists. No Electron config exists. No desktop application
bundle exists. The Hermes runtime is a Python backend + React web frontend
+ terminal TUI, all launched from the CLI.

---

## 5. Host Options Evaluation

| Option | Description | Feasibility Now | Risk | Pros | Cons | Recommendation |
|--------|-------------|:---:|------|------|------|:---:|
| **A: Independent Electron child process** | Hermes CLI launches a separate Electron app (like it launches `ui-tui/`). Browser window is a separate OS window. Communicates via localhost HTTP. | High | Low–Medium | Proven PoC works. Matches existing subprocess pattern. No changes to existing surfaces. Minimal blast radius. | Separate OS window feels disconnected. Two-window UX may confuse users. | **Recommended for Phase 2.** |
| **B: Electron wrapper for the React SPA** | Hermes Desktop becomes an Electron app that loads the existing React SPA as its renderer. Same Electron process hosts the embedded browser. | Low | High | Integrated single-window experience. Browser and dashboard share an Electron host. | Requires major rewrite of app startup. Breaks `hermes dashboard` served-via-browser workflow. Touches every surface. | **Defer to post-MVP.** |
| **C: Wait for full Electron Desktop** | Do nothing until a full Hermes Desktop Electron app is built. Then embedded browser is native. | None | Low (but blocking) | Cleanest long-term architecture. | Blocks Browser Workspace indefinitely. PoC results go unused. Misses the MVP window. | **Rejected.** |
| **D: External browser adapter** | Use mcp-chrome, BrowserMCP, or Playwright to connect to the user's existing Chrome. | Medium | Medium–High | No Electron host needed. User keeps their Chrome. | Connection fragility. Profile conflicts. Cannot enforce read-only boundary at the provider level. Already rejected as primary path. | **Fallback only.** |

### Detailed evaluation

#### Option A: Independent Electron child process

This is the closest analogue to the proven PoC. The PoC
(`/tmp/hermes-browser-poc`) ran as a standalone `electron-vite dev` process.
Option A wraps this same Electron app but launches it from the Hermes CLI
and adds a local HTTP API for the dashboard to query context.

**Technical similarity to existing patterns:**
- `hermes_cli/main.py` already launches `tsx src/entry.tsx` as a subprocess
  for the TUI gateway.
- `tui_gateway/server.py` already implements a JSON-RPC transport for IPC
  between Python and Node.js.
- The Electron host would expose a localhost HTTP endpoint (e.g.
  `http://127.0.0.1:9223`) for the dashboard to call.

**Launch flow:**
```
hermes browser start
  → Python CLI spawns: npx electron vite
  → Electron window opens (separate OS window)
  → Electron main process starts localhost HTTP server on random port
  → Port written to a file or stdout for the dashboard to discover
  → Dashboard queries: GET http://127.0.0.1:<port>/api/snapshot
```

#### Option B: Electron wrapper

This would require converting the entire Hermes web dashboard from a
browser-served React SPA to an Electron-window-hosted React app. The
`web_server.py` FastAPI server would either run as a sidecar or be replaced
by Electron IPC. This is a significant architectural change that affects
every existing surface.

#### Why Option B is deferred, not rejected

Option B may become the correct choice once Hermes has a full Electron
Desktop shell. But building that shell is a separate project — not a Browser
Workspace dependency. The Browser Workspace MVP should not be blocked on a
desktop shell decision.

---

## 6. Recommended Path

### Phase 1: Browser tab shell in existing dashboard

**Can start immediately.** No host dependency.

Add a Browser tab to the existing dashboard sidebar using the plugin system:

1. Create `plugins/browser-workspace/dashboard/` with a `manifest.json`:
   ```json
   {
     "name": "browser-workspace",
     "label": "Browser",
     "description": "Shared browser workspace",
     "icon": "Globe",
     "version": "0.1.0",
     "tab": {
       "path": "/browser",
       "position": "after:skills"
     },
     "entry": "dist/index.js",
     "api": "plugin_api.py"
   }
   ```
2. The entry component shows placeholder/planned state:
   ```
   Browser Workspace
   Coming soon. Start the browser with: hermes browser start
   ```
3. This requires no Electron host, no new dependencies, no backend changes
   beyond adding the plugin directory.

### Phase 2: Embedded browser via Option A

**Requires Phase 0 confirmation (this audit confirms).**

1. Create `browser-host/` directory adjacent to `hermes-agent/` (or inside
   it as a sibling of `web/` and `ui-tui/`).
2. Implement minimal Electron app with:
   - BrowserWindow + WebContentsView
   - Persistent profile at `~/.hermes/browser/`
   - User-controlled URL bar
   - Back/Forward buttons
   - Localhost HTTP API for context queries
3. Add `hermes browser start` CLI command in `hermes_cli/main.py` that
   spawns the Electron child process.
4. Dashboard Browser tab detects the running Electron host and displays
   context (Phase 4).

### What not to do

- Do not try to embed Chromium inside the React SPA served by FastAPI.
- Do not wait for a full Electron Desktop shell before starting Phase 1.
- Do not repurpose the existing `plugins/browser/` cloud providers.
- Do not start Phase 2 code until the `browser-host/` structure and CLI
  integration are planned.

---

## 7. Communication Boundary (Option A)

### How dashboard and Electron child communicate

```text
┌─ Hermes Python Backend ─────────────────────────────────────────────┐
│                                                                      │
│  hermes_cli/web_server.py (FastAPI, port 9119)                       │
│    │                                                                 │
│    │  Serves React SPA to browser                                    │
│    │                                                                 │
│    │  /api/browser/snapshot  ──────────►  localhost HTTP call        │
│    │  /api/browser/screenshot                to Electron host        │
│    │  /api/browser/readable-text             (port from discovery)   │
│    │                                                                 │
│    ▼                                                                 │
│  hermes_cli/main.py                                                  │
│    │                                                                 │
│    │  hermes browser start                                           │
│    │    → subprocess.Popen(["npx", "electron", "."])                 │
│    │    → reads port from child stdout                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ Electron Child Process ────────────────────────────────────────────┐
│                                                                      │
│  main process                                                        │
│    ├─ BrowserWindow (URL bar, toolbar)                               │
│    ├─ WebContentsView (embedded Chromium)                            │
│    └─ Localhost HTTP server (random port)                            │
│         GET /api/snapshot      → BrowserContextSnapshot              │
│         GET /api/tabs           → TabInfo[]                          │
│         GET /api/screenshot     → PNG (base64 or file ref)           │
│         GET /api/readable-text  → string                             │
│         GET /api/selected-text  → string                             │
│         GET /api/clipboard      → string                             │
│         GET /api/events          → BrowserEvent[]                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Where BrowserContextProvider lives

The BrowserContextProvider interface is implemented in the Electron main
process as IPC handlers (internal) and localhost HTTP endpoints (external
to the dashboard). The Python backend has a thin client that calls the
Electron host's HTTP API.

### Read-only boundary

- **Internal (Electron renderer ↔ main):** The preload script exposes
  `navigateHuman`, `goBack`, `goForward` ONLY. No Agent-facing APIs.
- **External (Python backend ↔ Electron host):** The backend only calls
  GET endpoints for context queries. No POST/PUT for navigation or actions.
- **Agent (prompt injection):** The Agent receives only the context snapshot
  that the user explicitly opted to include. No direct access to the browser.

### Discovery mechanism

When the Electron child process starts, it:
1. Binds a localhost HTTP server on a random available port.
2. Writes the port to stdout: `BROWSER_PORT=52341`.
3. The Python CLI parent process reads this line and stores the port.
4. The dashboard queries `/api/browser/info` to get the current port.
5. All subsequent context queries use this port.

If the Electron process exits, the dashboard shows "Browser not running"
and offers a restart button.

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Child process lifecycle.** Electron child process could crash, become a zombie, or leave ports open. | Medium | Reuse existing subprocess pattern from `tui_gateway`. Add health check. Clean up on CLI exit (`atexit` handler). |
| **Port/API security.** The localhost HTTP endpoint is accessible to any local process. | Medium | Bind to `127.0.0.1` only. Use random port. Add a simple shared-secret token passed via CLI env to prevent unauthorized local processes from calling the API. |
| **Profile ownership.** `~/.hermes/browser/` stores sensitive cookies and session data. | Medium | Set restrictive file permissions (`600`). Clear documentation on what is stored. Profile reset feature. |
| **Two-window UX.** The Electron browser window is separate from the dashboard browser window. Users may find this disjointed. | Low | This is the UX cost of Option A. Mitigated by keeping the browser context panel in the dashboard (Phase 4). The Electron window is just the "engine"; the dashboard is where context is consumed. |
| **Eventual migration to integrated desktop.** If Hermes later adopts a full Electron Desktop (Option B/C), the standalone Electron child process becomes redundant. | Low | The BrowserContextProvider interface is host-agnostic. When the host changes, the provider implementation changes but the Agent-facing contract does not. Option A is designed to be swappable. |
| **Dashboard and Electron child state sync.** If the Electron process restarts while the dashboard is open, the dashboard must re-discover the port. | Low | Health check on each API call. If unreachable, show "restart" state. Discovery is re-done on restart. |

---

## 9. Decision

**Decision: Option A confirmed as recommended path.**

### Rationale

1. No production Electron host exists. Option A requires creating one — but
   as an independent child process, not by modifying existing surfaces.
2. Option A follows the proven subprocess pattern already used by `ui-tui/`.
3. The dashboard plugin system already supports adding a Browser tab for
   Phase 1. No new infrastructure needed.
4. Option A keeps the blast radius minimal. If the Electron child fails,
   no other Hermes subsystem is affected.
5. Option B/C can be adopted later without changing the
   BrowserContextProvider contract. The interface is host-agnostic.

### What this decision does NOT mean

- It does not mean we start writing Electron host code today.
- It does not mean we abandon the React SPA dashboard.
- It does not mean the Electron child process is the permanent architecture.
- It does not mean Browser Workspace is production-ready.

---

## 10. Next Step

### Immediate

Phase 1 can begin: **Browser tab shell in existing dashboard.**

1. Create `plugins/browser-workspace/dashboard/` with `manifest.json`.
2. Entry component shows "Coming soon" placeholder.
3. Validate that the Browser tab appears in the sidebar, navigates to
   `/browser`, and shows the placeholder.
4. No Electron host. No backend changes. No new dependencies.

### After Phase 1

Write a narrow Phase 2 / Option A implementation task list:

1. Define `browser-host/` project structure.
2. Implement Electron main process with WebContentsView.
3. Implement localhost HTTP API for context queries.
4. Add `hermes browser start` CLI command with subprocess management.
5. Implement port discovery and health check.

---

## Appendix

### Files inspected

```
/Users/gu/.hermes/hermes-agent/package.json
/Users/gu/.hermes/hermes-agent/web/package.json
/Users/gu/.hermes/hermes-agent/ui-tui/package.json
/Users/gu/.hermes/hermes-agent/website/package.json
/Users/gu/.hermes/hermes-agent/hermes_cli/main.py
/Users/gu/.hermes/hermes-agent/hermes_cli/web_server.py
/Users/gu/.hermes/hermes-agent/tui_gateway/server.py
/Users/gu/.hermes/hermes-agent/web/src/App.tsx
/Users/gu/.hermes/hermes-agent/web/src/plugins/types.ts
/Users/gu/.hermes/hermes-agent/web/src/plugins/registry.ts
/Users/gu/.hermes/hermes-agent/plugins/browser/ (directory listing)
/Users/gu/.hermes/hermes-agent/plugins/example-dashboard/dashboard/manifest.json
/Users/gu/.hermes/hermes-agent/plugins/kanban/dashboard/manifest.json
/Users/gu/.hermes/hermes-agent/providers/ (directory listing)
/Users/gu/.hermes/hermes-agent/web/src/components/ (directory listing)
/Users/gu/.hermes/hermes-agent/web/src/pages/ (directory listing)
```

### Commands used

```
find /Users/gu/.hermes/hermes-agent -maxdepth 3 -name "package.json"
find /Users/gu/.hermes/hermes-agent -maxdepth 3 \( -name "main.js" -o -name "preload.js" -o -name "renderer.js" -o -name "main.ts" -o -name "preload.ts" -o -name "electron-builder*" -o -name "forge.config*" \) ! -path "*/node_modules/*"
grep -rl "electron" /Users/gu/.hermes/hermes-agent/package.json /Users/gu/.hermes/hermes-agent/web/ /Users/gu/.hermes/hermes-agent/ui-tui/ /Users/gu/.hermes/hermes-agent/website/
grep -r "browser\|electron\|chromium\|webview\|webcontents" /Users/gu/.hermes/hermes-agent/plugins/browser/
grep -n "hermes.*browser\|browser.*command\|subprocess\|spawn\|Popen" /Users/gu/.hermes/hermes-agent/hermes_cli/main.py
grep -n "web\|dashboard\|static\|vite" /Users/gu/.hermes/hermes-agent/hermes_cli/web_server.py
grep -n "plugin\|tab\|sidebar\|nav\|route" /Users/gu/.hermes/hermes-agent/hermes_cli/web_server.py
grep -A 30 "def _cmd_web\|web_server\|dashboard.*plugin" /Users/gu/.hermes/hermes-agent/hermes_cli/main.py
ls /Users/gu/.hermes/hermes-agent/web/src/pages/
ls /Users/gu/.hermes/hermes-agent/web/src/components/
ls /Users/gu/.hermes/hermes-agent/plugins/
find /Users/gu/.hermes/hermes-agent/plugins/browser/ -type f
find /Users/gu/.hermes/hermes-agent/plugins/kanban/dashboard/ -type f
```

### Git status summary

**`/Users/gu/.hermes` (docs repo):**
- Several modified SKILL.md files (unrelated).
- New untracked docs under `docs/architecture/`, `docs/product/`,
  `docs/research/`, `docs/review/`, `docs/roadmap/`.

**`/Users/gu/.hermes/hermes-agent` (runtime repo):**
- Modified: `hermes_cli/kanban.py`, `web_server.py`, `web/src/App.tsx`,
  `ChatSidebar.tsx`, `ToolCall.tsx`, `ChatPage.tsx`, `ConfigPage.tsx`.
- New untracked: `executors/`, `hermes_cli/kanban_feedback.py`,
  `web/src/components/ChatSessionSidebar.tsx`.

No Electron-related files staged, modified, or untracked.
