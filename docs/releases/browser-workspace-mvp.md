# Browser Workspace MVP

Date: 2026-06-05
Status: Docs freeze — MVP slice complete

## 1. Summary

Hermes Browser Workspace MVP establishes an embedded, read-only shared browser
context layer for Hermes Agent Workbench. It lets the user explicitly share
current page context with the Agent without automatic browser actions.

The MVP ships as a dashboard plugin (Browser tab) backed by an independent
Electron browser-host process. The user controls the browser; the Agent
observes context only when the user explicitly inserts it.

This is an MVP slice — not production-ready. Feature scope is deliberately
narrow. See [Known Limitations](#8-known-limitations).

## 2. What Shipped

- Browser tab shell in the dashboard plugin system, discovered at `/browser`
- Independent Electron browser-host skeleton with embedded WebContentsView
- Dashboard start/stop/status controls with PID, port, and health URL display
- Read-only HTTP API: `/health`, `/snapshot`, `/screenshot`, `/context`
- Stable `BrowserContextSnapshot` contract (Phase 5A schema) shared across all endpoints
- DOM summary extraction (max 3000 chars, static read-only script)
- Selected text extraction (max 3000 chars)
- Clipboard preview (max 1000 chars)
- Explicit "Insert Current Page Context" button — inserts a bounded prompt block into the chat composer, falls back to system clipboard if chat is unavailable, never auto-sends
- Lightweight `browserContextRef` (id, url, title, capturedAt) — full DOM/clipboard/screenshot are not stored in run metadata
- Hermes-native page-type detection plugins: GitHub Pull Request detector and ChatGPT conversation detector (URL parsing only, no API calls)
- Proxy support passes through the system/Clash/Surge/Mihomo state already configured on the machine

## 3. Verified

| Phase | Capability | Result |
|---|---|---|
| Phase 1 | Browser tab shell | PASS |
| Phase 2A | browser-host health endpoint | PASS |
| Phase 2B | Dashboard start/stop/status | PASS |
| Phase 2C | Snapshot + Screenshot API | PASS |
| Phase 3A | DOM / selected text / clipboard extraction | PASS |
| Phase 3B | BrowserContextSnapshot stable contract | PASS |
| Phase 4A | Explicit prompt insertion | PASS |
| Phase 4B | Lightweight browserContextRef | PASS |
| Phase 5A | GitHub PR detector plugin | PASS |
| Phase 5B | ChatGPT conversation detector plugin | PASS |
| Phase 6 | Final verification | PASS (with environment note) |

All automated checks (typecheck, build, contract validation, tsc, py_compile,
read-only boundary grep) pass with zero failures.

## 4. Environment Note

Phase 6 final verification was performed in a terminal/sandbox environment
where Electron cannot initialize its GPU process. Manual visual checks 2–5
(Start host, GitHub PR flow, ChatGPT flow, Screenshot) are blocked by macOS
GPU sandbox in headless/remote environments. This is not a code bug.

On a normal macOS display session, Electron starts, opens a window with
WebContentsView, and writes `~/.hermes/browser-host/state.json` as designed.

Manual visual checks 2–5 should be re-run on the next normal macOS display
session. See `docs/research/browser-workspace-mvp-final-verification.md` for
the full verification log.

## 5. What Did Not Ship

- **Agent click/type/submit/navigate** — no Agent browser actions of any kind
- **Automatic prompt sending** — context insertion requires explicit user button click
- **Automatic/hidden context injection** — no silent context attached to runs
- **Chrome Web Store extension compatibility** — not a browser extension; Electron-only
- **Full plugin layer** — only two detectors (GitHub PR, ChatGPT); no plugin SDK for third-party detectors
- **Vercel/Claude detection** — skipped because the author does not have active accounts on those services
- **Production packaging/signing/updater** — dev Electron build only
- **External browser adapter primary path** — this is an embedded workspace; external adapters are evaluated separately as a fallback option

## 6. Security / Privacy Boundary

- **User controls the browser, Agent observes.** The Agent cannot click, type, submit, or navigate.
- **Browser context is inserted only after explicit user action** (button click).
- **Full DOM, clipboard text, and screenshot are not silently stored** in run metadata.
- **browserContextRef is lightweight** — only id, url, title, capturedAt. No body content.
- **executeJavaScript is limited to static, compile-time read-only scripts.** No user or Agent input is ever passed to `executeJavaScript`.
- **All APIs bind localhost only** (`127.0.0.1`). Dashboard proxy routes use `httpx.get()` for passthrough.
- **Future Agent actions, if added, require an approval gate.** This is an explicit design constraint documented in `docs/research/browser-workspace-embedded-mvp-spec.md`.

## 7. Known Limitations

- Normal macOS display session needed for full browser-host visual validation (see [Environment Note](#4-environment-note))
- Electron host lifecycle is still MVP — no watchdog, no auto-restart, no crash recovery
- Screenshot retention policy needs hardening (no rotation, no TTL, no size cap)
- Profile path policy may need per-Hermes-profile migration (`browserProfile` currently uses `~/.hermes/browser`)
- ChatGPT and GitHub page DOM structure can change — detector may need updates
- Proxy behavior depends on external Clash/Surge/Mihomo state; no in-app proxy configuration
- Memory pressure from long-running browser sessions not fully characterized
- Only a single browser surface (one WebContentsView); multi-tab UX is not implemented

## 8. Files / Docs

| Document | Path |
|---|---|
| MVP evaluation (design rationale) | `docs/research/browser-workspace-mvp-evaluation.md` |
| Embedded MVP spec | `docs/research/browser-workspace-embedded-mvp-spec.md` |
| POC results | `docs/research/browser-workspace-embedded-poc-results.md` |
| Phase 0 host audit | `docs/research/browser-workspace-phase-0-host-audit.md` |
| Phase 6 final verification | `docs/research/browser-workspace-mvp-final-verification.md` |
| Context provider design | `docs/architecture/browser-context-provider-design.md` |
| MVP implementation plan | `docs/architecture/browser-workspace-mvp-implementation-plan.md` |
| Option A host plan | `docs/architecture/browser-host-option-a-implementation-plan.md` |

## 9. Decision

**Decision: Freeze Browser Workspace MVP docs and stop feature expansion.**

The MVP slice is complete. All planned phases (1–6) passed at the code level.
The read-only boundary is intact. The environment caveat is documented.

Next work should be stabilization and normal macOS display-session validation,
not new feature work. Do not expand scope before manual visual checks 2–5 are
re-run and confirmed on a native display session.
