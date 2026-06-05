# Hermes Browser Host — Option A Implementation Plan

Date: 2026-06-06
Status: Implementation plan (read-only, no implementation commitment)
Based on:
- [Phase 0 Host Audit](../research/browser-workspace-phase-0-host-audit.md)
- [Browser Workspace MVP Implementation Plan](browser-workspace-mvp-implementation-plan.md)
- [BrowserContextProvider Adapter Design](browser-context-provider-design.md)
- [Embedded Browser Workspace PoC Results](../research/browser-workspace-embedded-poc-results.md)

---

## 1. Where browser-host Lives

### Candidates

| Path | Proximity to dashboard | Isolation | Use existing patterns |
|------|------------------------|-----------|----------------------|
| `hermes-agent/browser-host/` | Sibling of `web/`, `ui-tui/`, `plugins/` | Good — separate directory | Matches `ui-tui/` as a sibling Node.js project |
| `hermes-agent/apps/browser-host/` | One level deeper | Better — clearly a separate app | No existing `apps/` directory; would require creating a new top-level container |
| `hermes-agent/plugins/browser-workspace/browser-host/` | Colocated with Phase 1 plugin | Confusing — mixes dashboard plugin with Electron host | Plugin directory pattern is for dashboard extensions, not standalone apps |

### Recommendation: `hermes-agent/browser-host/`

**Rationale:**

1. **Matches existing sibling pattern.** `ui-tui/` is already a sibling of
   `web/`, `plugins/`, and `hermes_cli/`. An Electron host is the same class
   of artifact — a standalone Node.js process launched by the Python CLI.
   Placing it at the same level as `ui-tui/` reinforces this pattern.

2. **Not a dashboard plugin.** The Electron host is not a dashboard tab
   extension. The Phase 1 plugin (`plugins/browser-workspace/`) is the
   dashboard-side UI. The host is infrastructure. Keeping them separate
   avoids confusion about what runs where.

3. **No unnecessary nesting.** `apps/browser-host/` adds a directory that
   has no other members. If multiple standalone apps are created later,
   they can be grouped then — not prematurely.

### What lives where

```
hermes-agent/
  browser-host/                  ← NEW: Electron host (this plan)
    package.json
    src/main/index.ts
    src/preload/index.ts
    src/renderer/

  plugins/browser-workspace/     ← Phase 1 (exists)
    dashboard/                   ← Dashboard-side UI only

  ui-tui/                        ← Existing: Node.js TUI subprocess (same pattern)
  web/                           ← Existing: React SPA dashboard
```

---

## 2. How browser-host Starts and Stops

### MVP: manual start only

Phase 2A does not add any dashboard controls. The Electron host is started
manually from the CLI for development validation:

```bash
cd hermes-agent/browser-host
npm run dev
```

This mirrors how `/tmp/hermes-browser-poc` was run during PoC. No subprocess
management. No PID file. No auto-restart. No dashboard integration.

### Phase 2B: dashboard controls

After Phase 2A validates that the Electron host works independently, add
lightweight dashboard controls:

| Control | Implementation |
|---------|---------------|
| Start | `hermes_cli` spawns `npm run dev` or `npx electron .` as a subprocess. Writes PID to `~/.hermes/browser/browser-host.pid`. |
| Stop | Sends SIGTERM to the PID. Falls back to `pkill` on the Electron binary path. |
| Status | Read PID file, check process alive. Also call `GET /health` on the known port. |
| Restart | Stop then start. |

### Process lifecycle details

| Concern | MVP solution |
|---------|---------------|
| PID tracking | PID file at `~/.hermes/browser/browser-host.pid`. Simple, standard Unix pattern. |
| Stale PID detection | Check if the PID is alive (`os.kill(pid, 0)`). If not, remove stale file. |
| Port discovery | Electron host binds a random available port, writes it to `~/.hermes/browser/browser-host.port`. Dashboard reads this file. |
| Port conflict | If the recorded port is already in use by another process, treat as stale and restart. |
| Crash detection | Dashboard periodically calls `GET /health`. If unreachable for 3 consecutive polls, show "crashed" state. |
| Auto-restart | **No auto-restart in MVP.** User must click "Start" again. Auto-restart is a future concern. |
| Crash reporting | Electron host writes crash log to `~/.hermes/logs/browser-host-crash.log`. Dashboard shows last error line. |
| Log path | `~/.hermes/logs/browser-host.log` for stdout/stderr. Rotated by existing Hermes log infrastructure. |
| Cleanup on exit | Hermes CLI `atexit` handler sends SIGTERM. `pkill` fallback on the Electron binary path. |

### What happens at dashboard startup

1. Dashboard loads. Checks `~/.hermes/browser/browser-host.pid`.
2. If PID file exists and process is alive: show "Running" status.
3. If PID file exists but process is dead: show "Stopped (crashed?)".
4. If PID file does not exist: show "Stopped".
5. No Electron process is auto-started. User must explicitly start it.

---

## 3. How browser-host Communicates

### Recommended: read-only localhost HTTP API

The Electron main process starts a minimal HTTP server (Node.js built-in
`http` module or Express) on `127.0.0.1` with a random port.

### API endpoints (Phase 2C)

```
GET  /health                  → { ok: true, uptime: number, pid: number }
GET  /api/snapshot            → BrowserContextSnapshot
GET  /api/tabs                → TabInfo[]
POST /api/screenshot          → { ref: string, sizeBytes: number }   (triggers capture)
GET  /api/events?since=<ts>   → BrowserEvent[]
GET  /api/clipboard-preview   → { text: string }
```

### What is NOT exposed

```
POST /api/navigate            → NOT EXPOSED
POST /api/click               → NOT EXPOSED
POST /api/type                → NOT EXPOSED
POST /api/submit              → NOT EXPOSED
POST /api/execute-javascript  → NOT EXPOSED
```

User navigation happens only inside the Electron window (URL bar, Go button,
back/forward). The HTTP API is strictly read-only GET endpoints + a POST for
screenshot capture (which triggers `webContents.capturePage()` — no page
side-effects).

### Security constraints

| Constraint | Implementation |
|------------|---------------|
| Bind address | `127.0.0.1` only. Never `0.0.0.0`. |
| Port | Random available port. Written to `~/.hermes/browser/browser-host.port`. |
| Shared secret (optional future) | A random token generated at host startup, written alongside the port. Dashboard reads both. Passed as `X-Hermes-Browser-Token` header. **MVP may omit this** — the risk of localhost port scanning by another local process is accepted for Phase 2. |
| CORS | No CORS headers. Same-origin only via localhost. Dashboard fetches through the Python backend proxy, not directly from the browser. |
| Rate limiting | None in MVP. Future: configurable TPS per endpoint. |

### Discovery flow

```
Electron host starts
  → binds HTTP server on 127.0.0.1:<random_port>
  → writes port to ~/.hermes/browser/browser-host.port
  → writes PID to ~/.hermes/browser/browser-host.pid

Dashboard (via Python backend)
  → reads ~/.hermes/browser/browser-host.port
  → calls GET http://127.0.0.1:<port>/health
  → if 200: shows "Running"
  → if unreachable: shows "Stopped" or "Crashed"
```

### Why not a different transport

| Transport | Verdict | Reason |
|-----------|---------|--------|
| stdio JSON-RPC (like `ui-tui/`) | No | Electron is a GUI app, not a headless process. stdio is used for its own renderer-dev loop. |
| Unix domain socket | Maybe later | Cleaner than TCP for local IPC. But adds complexity. localhost TCP is simpler for Phase 2. |
| WebSocket | No | Overkill for request-response queries. May be added later for event streaming. |
| File-based (write snapshot to disk, dashboard reads) | No | Polling loop, race conditions, no real-time. HTTP is a cleaner contract. |

---

## 4. Where BrowserContextProvider Lives

### Three-layer architecture

```
┌─ Electron Host ─────────────────────────────────────────────────────┐
│                                                                      │
│  BrowserContextProvider (TypeScript, internal)                       │
│    ├─ getCurrentSnapshot()     → calls webContents.* API            │
│    ├─ getTabs()                                                      │
│    ├─ captureScreenshot()                                            │
│    ├─ getReadableText()        → static executeJavaScript script    │
│    ├─ getSelectedText()        → static executeJavaScript script    │
│    ├─ getClipboardPreview()    → clipboard.readText()               │
│    └─ getRecentEvents()                                             │
│                                                                      │
│  HTTP API layer (Express / Node http)                                │
│    ├─ GET /api/snapshot         → JSON response                     │
│    ├─ GET /api/tabs                                                  │
│    ├─ POST /api/screenshot      → triggers capture, returns ref      │
│    ├─ GET /api/events                                                │
│    └─ GET /api/clipboard-preview                                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ Hermes Python Backend ─────────────────────────────────────────────┐
│                                                                      │
│  BrowserContextClient (Python, thin wrapper)                         │
│    ├─ get_snapshot()            → GET http://127.0.0.1:<port>/api/snapshot
│    ├─ get_tabs()                                                      │
│    ├─ capture_screenshot()                                            │
│    ├─ get_events(since)                                               │
│    └─ get_clipboard_preview()                                         │
│                                                                      │
│  Exposed as:                                                         │
│    /api/browser/snapshot        → dashboard calls this              │
│    /api/browser/health          → dashboard calls this              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Recommendation

- **BrowserContextProvider lives in the Electron host** as TypeScript code.
  It has direct access to `webContents.*` APIs and `clipboard`. This is the
  same pattern proven in the PoC.
- **Python backend has a thin BrowserContextClient** that calls the Electron
  host's HTTP API and returns JSON to the dashboard. No browser logic in
  Python.
- **Dashboard calls the Python backend** (`/api/browser/*`), not the
  Electron host directly. This keeps CORS simple and allows the Python
  backend to enforce read-only access.

### MVP scope

Phase 2A–2B: only `/health` exists. No snapshot, no screenshot.
Phase 2C: snapshot + screenshot + clipboard added.

---

## 5. Profile Path

### Recommendation: `~/.hermes/browser/`

| Aspect | Decision |
|--------|----------|
| MVP path | `~/.hermes/browser/` |
| Rationale | PoC validated this path works for persistent cookies/localStorage. Simpler than per-profile isolation for initial implementation. |
| App code | `app.setPath("userData", hermesBrowserPath)` in Electron main process |
| Migration to per-profile | When Hermes supports multiple profiles, move to `~/.hermes/profiles/{profile_id}/browser/`. The `app.setPath()` call changes; the Electron API is identical. |
| What gets stored | Cookies, Local Storage, IndexedDB, Cache, Preferences. Same as Chromium default profile. |
| Screenshots | `~/.hermes/browser/screenshots/` (max 10, evict oldest). |
| What is NOT stored | Clipboard history, full-page HTML dumps, agent run data. |

### Why not per-profile in MVP

Hermes profiles are a future concern. The current runtime has a single
`~/.hermes/` data directory. Per-profile isolation adds complexity without
immediate user value. The migration path is trivial — move the directory
and change one `app.setPath()` call.

---

## 6. Proxy Mode

### MVP: hardcoded System mode

Phase 2A–2B: no proxy configuration. The embedded browser inherits the
system proxy by default (standard Chromium behavior).

Phase 2C: add support for custom proxy via environment variable or config
file. No UI.

| Mode | How configured | MVP | Future |
|------|---------------|-----|--------|
| System | Default (no config) | Yes | Remains default |
| Direct | `BROWSER_PROXY_MODE=direct` env var | Phase 2C | UI toggle in Phase 7 |
| Custom | `BROWSER_PROXY_MODE=custom` + `BROWSER_PROXY_URL=http://127.0.0.1:7890` | Phase 2C | UI input in Phase 7 |

### Config source (Phase 2C)

Read from `~/.hermes/browser/config.json`:

```json
{
  "proxy": {
    "mode": "system",
    "customUrl": null
  }
}
```

This file is created with defaults on first launch. The dashboard can write
to it later (Phase 7). The Electron host reads it at startup and applies
`session.setProxy()` before creating the WebContentsView.

### Not in MVP

- Per-site proxy rules.
- Proxy auto-detection (PAC).
- SOCKS5 support (can be added by changing the `proxyRules` string).
- UI for proxy configuration (Phase 7).

---

## 7. Dashboard Browser Tab Integration

### Phase 2B: host controls

The dashboard Browser tab (Phase 1 placeholder) gains status and controls:

```
┌─ Browser Workspace ─────────────────────────────────────────────────┐
│                                                                      │
│  Host Status: ● Running (pid 12345, port 56789)                      │
│                                                                      │
│  [Start Browser Host]  [Stop]  [Open Browser Window]                 │
│                                                                      │
│  ─────────────────────────────────────────────────────────           │
│                                                                      │
│  Phase 2 — embedded browser host active.                             │
│  No snapshot available yet (coming in Phase 2C).                     │
│                                                                      │
│  [Refresh Status]                                                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Phase 2C: snapshot summary

After snapshot API is added, the tab shows:

```
┌─ Browser Workspace ─────────────────────────────────────────────────┐
│                                                                      │
│  Host Status: ● Running                                              │
│                                                                      │
│  Current Page                                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ URL:    https://github.com/gu87                           │       │
│  │ Title:  gu87                                              │       │
│  │ Type:   generic-web                                       │       │
│  │                                                           │       │
│  │ [Screenshot thumbnail]  [Refresh snapshot]                 │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Selected: (none)                                                    │
│  Clipboard: (disabled — enable in settings)                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### What is still NOT in the dashboard

- No click/type/submit buttons for the browser.
- No Agent context injection (Phase 4).
- No plugin indicators (Phase 5).
- No timeline entries (Phase 6).

---

## 8. Security Boundary

| Constraint | Implementation | Verified by |
|------------|---------------|-------------|
| Bind localhost only | HTTP server listens on `127.0.0.1` | Code review: grep for `0.0.0.0` |
| No remote access | No port forwarding, no SSH tunnel config | Code review |
| Optional random token | `X-Hermes-Browser-Token` header checked by middleware | Future: automated test |
| No write/action API | Router only has GET + POST /screenshot (capture-only) | Static grep for `POST.*navigate\|POST.*click\|POST.*type\|POST.*submit` |
| No user/Agent JS | `executeJavaScript()` only called with module-level const strings | Static grep for `executeJavaScript` in non-const context |
| Screenshot size limit | Max 1920px width, max 500 KB. Enforced at capture. | Automated test: capture large page, verify size ≤500 KB |
| Snapshot text limit | 100 KB total text per snapshot. Enforced at serialization. | Automated test |
| Clipboard preview limit | 2 KB max. Enforced at read. | Automated test |
| Dashboard proxy | Dashboard does not call Electron host directly. Calls go through Python backend which validates the request. | Architecture review |

### What this boundary does NOT protect against

- Another process on the same machine calling the localhost API (accepted risk for MVP, mitigable with token in future).
- User copying sensitive data to clipboard (clipboard reading requires user opt-in toggle in dashboard, default OFF).
- User navigating to malicious sites in the embedded browser (same risk as any browser).

---

## 9. Process Lifecycle

### Start

```bash
# Phase 2A (manual)
cd hermes-agent/browser-host && npm run dev

# Phase 2B (dashboard-initiated)
hermes browser start
  → hermes_cli checks if already running (PID file + health check)
  → if not: spawns subprocess
  → waits for health endpoint to respond (timeout 10s)
  → writes PID + port to ~/.hermes/browser/
  → returns success/error to caller
```

### Stop

```bash
# Phase 2A (manual)
Ctrl+C in terminal

# Phase 2B (dashboard-initiated)
hermes browser stop
  → reads PID from ~/.hermes/browser/browser-host.pid
  → sends SIGTERM
  → waits up to 5s for process to exit
  → if still alive: SIGKILL
  → removes PID file, port file
  → returns success/error
```

### Health check

```
Dashboard (via Python backend) polls GET /health every 30 seconds.

If 3 consecutive polls fail (90 seconds):
  → status changes to "unreachable" in dashboard
  → no auto-restart

If process PID is not alive:
  → status changes to "stopped" in dashboard
  → stale PID file is cleaned up
```

### Port conflict

If the port file exists but the port is in use by a non-Hermes process:
  → log warning, do not start
  → dashboard shows "port conflict" error

If the port file exists and the port is free:
  → stale port file. Remove and start normally.

### Crash log

```
~/.hermes/logs/browser-host.log        ← stdout/stderr
~/.hermes/logs/browser-host-crash.log  ← crash stack traces only
```

### Cleanup

- Hermes CLI `atexit` handler sends SIGTERM to the browser host PID.
- Dashboard "Stop" button sends SIGTERM.
- Stale PID/port files are cleaned on next start attempt.
- Profile data (`~/.hermes/browser/Default/`) is never auto-deleted.

---

## 10. File Touch Plan

### Phase 2A: Skeleton + health (minimum viable)

**Goal:** Prove Electron child process starts, shows a window, serves
`/health`.

**New files:**

```
hermes-agent/browser-host/
  package.json                    ← electron + electron-vite deps
  electron-vite.config.ts
  src/main/index.ts               ← BrowserWindow + WebContentsView + HTTP server + /health
  src/preload/index.ts            ← Minimal: navigateHuman, goBack, goForward (no Agent APIs)
  src/renderer/index.html         ← Toolbar: URL bar, Go, Back, Forward
  src/renderer/src/App.tsx        ← Toolbar React component
  tsconfig.json
  .gitignore
```

**No changes to:**
- `hermes_cli/` (no subprocess launcher yet)
- `web/` (no dashboard controls yet)
- `plugins/browser-workspace/` (placeholder stays as-is)
- `hermes-agent/package.json` (browser-host has its own)

**Manual validation:**
```bash
cd browser-host && npm install && npm run dev
# → Electron window opens with URL bar
# → curl http://127.0.0.1:<port>/health returns 200
```

### Phase 2B: Dashboard controls

**Goal:** Dashboard Browser tab shows host status, can start/stop.

**Modified files:**
- `plugins/browser-workspace/dashboard/dist/index.js` — add status display + buttons
- `plugins/browser-workspace/dashboard/plugin_api.py` — NEW: backend API for host control
- `hermes_cli/browser.py` — NEW: CLI subprocess wrapper

**New API endpoints (via plugin_api.py):**
- `POST /api/plugins/browser-workspace/host/start`
- `POST /api/plugins/browser-workspace/host/stop`
- `GET /api/plugins/browser-workspace/host/status`

**No Agent access. No snapshot yet.**

### Phase 2C: Read-only snapshot API

**Goal:** Dashboard can read browser context via the Electron host API.

**Modified files:**
- `browser-host/src/main/index.ts` — add `/api/snapshot`, `/api/screenshot`, etc.
- `plugins/browser-workspace/dashboard/dist/index.js` — show snapshot summary
- `plugins/browser-workspace/dashboard/plugin_api.py` — proxy calls to Electron host

**New API endpoints (via plugin_api.py):**
- `GET /api/plugins/browser-workspace/snapshot`
- `POST /api/plugins/browser-workspace/screenshot`
- `GET /api/plugins/browser-workspace/clipboard`

---

## 11. Validation Plan

### Phase 2A

| # | Check | How |
|---|-------|-----|
| 1 | `npm install` succeeds | Run in `browser-host/` |
| 2 | `npm run dev` starts without errors | Manual |
| 3 | Electron window appears | Visual |
| 4 | URL bar accepts input, Go navigates | Manual |
| 5 | `/health` returns `{ ok: true }` | `curl http://127.0.0.1:<port>/health` |
| 6 | No Electron errors in console | Check terminal output |
| 7 | Back/Forward buttons work | Manual |
| 8 | Profile created at `~/.hermes/browser/` | `ls ~/.hermes/browser/` |

### Phase 2B

| # | Check | How |
|---|-------|-----|
| 9 | Dashboard Browser tab shows "Stopped" when host is off | Open dashboard |
| 10 | "Start Browser Host" button works | Click, verify Electron window opens |
| 11 | Dashboard shows "Running" with PID and port | Visual |
| 12 | "Stop" button works | Click, verify Electron window closes |
| 13 | Stale PID file does not break restart | Kill process manually, restart |
| 14 | Existing dashboard pages unaffected (Kanban, Operations) | Manual regression |

### Phase 2C

| # | Check | How |
|---|-------|-----|
| 15 | `GET /api/snapshot` returns valid JSON with URL and title | curl |
| 16 | Screenshot is non-empty PNG | `file` command on saved screenshot |
| 17 | Snapshot URL matches actual page | Manual comparison |
| 18 | Read-only boundary: no action methods in API | Static grep |
| 19 | `executeJavaScript` only with const strings | Static grep |
| 20 | Clipboard preview returns empty when disabled | curl |

### All phases

| # | Check | How |
|---|-------|-----|
| 21 | Kanban plugin still works | Open `/kanban` in dashboard |
| 22 | No regression in dashboard startup | Open dashboard home |
| 23 | No console errors | Browser dev tools |

---

## 12. Rollback Plan

### Phase 2A rollback

```bash
# Remove the browser-host directory
rm -rf hermes-agent/browser-host/

# Remove the profile directory (optional — user may want to keep login state)
rm -rf ~/.hermes/browser/
```

No other files were touched. Dashboard Browser tab remains as Phase 1
placeholder (unchanged).

### Phase 2B rollback

1. Revert `plugins/browser-workspace/dashboard/dist/index.js` to Phase 1
   version (placeholder only).
2. Remove `plugin_api.py` from the plugin directory.
3. Remove `hermes_cli/browser.py`.
4. Stop the Electron process if running.
5. Remove PID and port files from `~/.hermes/browser/`.
6. `browser-host/` directory can be kept or removed independently (Phase 2A
   still works without dashboard controls).

### Phase 2C rollback

1. Disable the snapshot endpoints in `plugin_api.py`.
2. Revert the dashboard tab to Phase 2B state (host controls only).
3. Keep the snapshot API in the Electron host but don't call it.

### Global rollback

Set `BROWSER_WORKSPACE_ENABLED: false` in Hermes config. The Browser tab
hides entirely (Phase 7 feature flag, gating all Browser Workspace code).

---

## 13. Risks / Open Questions

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **Electron dependency in hermes-agent repo.** Adding `electron` (≈200 MB download) to the dependency tree may affect CI, Docker builds, and developer setup time. | Medium | browser-host has its own `package.json`. Electron is only installed when explicitly working on the browser host. Not a transitive dependency of the Python backend. |
| 2 | **Packaging / distribution.** How does the Electron binary get distributed to end users? It won't be in the Python wheel. | Open | Not a Phase 2 concern. For MVP, assume the user has Node.js and can `npm install` in browser-host. Distribution is a future problem. |
| 3 | **Port collision.** The random port may conflict with another local service. | Low | Random port + collision detection. If port is taken, pick another. Write the actual port to the port file. |
| 4 | **Localhost API exposure.** Any process on the machine can call `GET /api/snapshot` and read the browser URL. | Low | The API only exposes what the dashboard already shows. No credentials are exposed. In a single-user machine, this is acceptable. Shared-secret token in future. |
| 5 | **Profile privacy.** `~/.hermes/browser/` stores cookies for all sites visited. | Medium | File permissions (0600). Profile reset feature in Phase 7. Clear documentation. |
| 6 | **Child process orphaning.** If the Python backend crashes, the Electron child may keep running. | Low | `atexit` handler + PID tracking. `hermes browser stop` as a manual fallback. |
| 7 | **Memory pressure.** Electron child process + WebContentsView for a heavy SPA may use 500 MB–1 GB RAM. | Medium | Phase 7 memory monitoring. Not auto-killed in MVP. User can manually stop. |
| 8 | **Multi-window UX.** The Electron browser window is separate from the dashboard browser window. | Low | This is the design. Users understand separate windows. Long-term: Option B/C migration to integrated desktop. |
| 9 | **Future migration to integrated Electron Desktop.** If Hermes adopts a full Electron Desktop later, this standalone browser-host becomes redundant. | Low | All code is in `browser-host/`. The BrowserContextProvider interface is host-agnostic. Migration means moving the provider into the integrated Electron main process, not rewriting it. |
| 10 | **Electron version drift vs system Chromium.** The embedded Chromium in Electron may differ from the user's system Chrome. Some sites may behave differently. | Low | Same risk as any Electron app. Electron tracks Chromium stable closely. |

---

## 14. Recommended Immediate Next Step

**Do not implement all of Phase 2 at once.**

### Immediate: Phase 2A only

1. Create `hermes-agent/browser-host/` directory.
2. Add minimal `package.json` with `electron` + `electron-vite` deps.
3. Create `src/main/index.ts`:
   - BrowserWindow with WebContentsView.
   - URL bar, Go, Back, Forward (user manual navigation only).
   - Persistent profile at `~/.hermes/browser/`.
   - HTTP server on `127.0.0.1:<random_port>` with `GET /health`.
4. Create `src/preload/index.ts`:
   - `navigateHuman`, `goBack`, `goForward` only.
   - No Agent APIs. No context bridge for snapshot/screenshot.
5. Create `src/renderer/` with minimal toolbar UI.
6. Manual validation: `npm install && npm run dev`. Verify `/health`.

### Phase 2A does NOT include

- Dashboard start/stop controls (Phase 2B).
- Snapshot/screenshot API (Phase 2C).
- Subprocess management from Python (Phase 2B).
- Any changes to `plugins/browser-workspace/` (Phase 1 stays as-is).
- Any changes to `hermes_cli/` or `web/`.

### Why this order

Phase 2A proves the Electron host works independently — just like the PoC
did, but inside the Hermes repo structure and with the persistent profile
path. Once `/health` responds, we know the host is alive and the integration
surface is real.

Phase 2B adds the dashboard↔host connection.
Phase 2C adds the first real context data flow.

Each phase is a working checkpoint. No phase blocks a later phase from
starting, but each validates assumptions before the next begins.
