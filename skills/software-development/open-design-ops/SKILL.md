---
name: open-design-ops
description: Install, configure, debug, and operate Open Design (nexu-io/open-design)
  — the open-source Claude Design alternative for generating HTML PPT/decks via local
  AI agents.
triggers:
- open design
- opendesign
- od
- guizang-ppt
- magazine-web-ppt
- claude design alternative
- html ppt generation
- html deck generation
agents:
- deepseek-tui
- claude
- codex
- hermes-internal
---

# Open Design Ops

> Repository: [nexu-io/open-design](https://github.com/nexu-io/open-design)
> Architecture: Next.js 16 web + Node/Express daemon + local agent CLI (Claude Code / Codex / etc.)
> Output: HTML slides (not .pptx) — rendered in browser, can be exported as PDF
> Last updated: 2026-05-05 — Write bug fixed, ports corrected

---

## Installation

### Prerequisites
- Node.js ~24
- pnpm 10.33.x (corepack enabled: `corepack enable`)
- macOS / Linux / WSL2

### Step-by-step

```bash
git clone https://github.com/nexu-io/open-design.git --depth=1
cd open-design
pnpm install
```

**Critical:** If using `pnpm install --ignore-scripts` (e.g., due to Electron download failure from China), `better-sqlite3` native binding won't compile. Fix:

```bash
cd node_modules/.pnpm/better-sqlite3@12.9.0/node_modules/better-sqlite3
npx prebuild-install
```

Then build packages:

```bash
# Build daemon (two-pass: main + sidecar)
cd apps/daemon
npx tsc -p tsconfig.json
npx tsc -p tsconfig.sidecar.json

# Or build all at once:
pnpm --filter @open-design/daemon build
pnpm --filter @open-design/web build
```

> **Note:** `npm run build -w apps/daemon` doesn't work with npm workspaces. Use `cd apps/daemon && npx tsc -p tsconfig.json` or `pnpm --filter @open-design/daemon build`.

### Start (separate terminals)

```bash
# Terminal 1 — Daemon (API server)
cd apps/daemon
OD_WEB_PORT=3000 node dist/cli.js --no-open
# Default port: 7456 (not 17456!)

# Terminal 2 — Web UI (Next.js)
cd apps/web
npx next dev
# Default port: 3000 (not 5173!)
```

Access at http://localhost:3000

### Start (one command — via tools-dev)
```bash
pnpm tools-dev run web --daemon-port 7456 --web-port 3000
```

### Stop
```bash
pnpm tools-dev stop
```

### CORS Configuration
When daemon and web run on **different ports** (7456 vs 3000), the daemon's CORS middleware blocks web requests. Fix:

```bash
OD_WEB_PORT=3000 node dist/cli.js --no-open
```

The daemon reads `OD_WEB_PORT` to add `http://localhost:3000` (and https variant) to its allowed origins list. See `buildAllowedOrigins()` in `server.ts`.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Daemon (Express, :7456)  ←→  Web (Next.js, :3000)  │
│       ↓                                          │
│  spawns agent CLI (Claude Code / Codex)           │
│  with cwd = .od/projects/<id>/                    │
│  hands it a composed prompt:                      │
│    # Instructions                                 │
│      [daemonSystemPrompt → design instructions]   │
│    ---                                            │
│      [daemonEnvPrompt → OD_BIN + connectors]      │
│    ---                                            │
│      [cwdHint → write files relative to cwd]      │
│    ---                                            │
│    # User request                                 │
└─────────────────────────────────────────────┘
```

### Prompt Composition (key — source of the Write bug)
The daemon's `startChatRun` (server.ts:~3427) joins three parts with `---` separators:

```typescript
const instructionPrompt = [
  daemonSystemPrompt,  // design system + skill instructions, says "use Write"
  runtimeToolPrompt,   // says "prefer OD_BIN wrapper commands"
  systemPrompt         // general system context
].join('\n\n---\n\n');
```

This is where the original conflict lived (see Fixes section).

Key components:
- **Daemon**: Express server at port **7456** (default), handles chat SSE, agent spawning, artifact management
- **Web**: Next.js 16 frontend at port **3000** (default)
- **Agent**: Claude Code / Codex spawned as child process with `cwd` pinned to project dir
- **Projects**: Stored at `.od/projects/<id>/`, SQLite at `.od/app.sqlite`
- **Skills**: `skills/` directory, e.g. `magazine-web-ppt` (guizang-ppt) for magazine-style decks
- **Design Systems**: `design-systems/` directory, 72 built-in

---

## Generating a PPT

### Via Web UI (standard flow)
1. Open http://localhost:3000
2. Create project → Select tab "Slide deck" → Enter project name
3. Ensure agent is selected (sidebar: "Local CLI · Claude Code · 2.1.126 (Claude Code)")
4. Write prompt in chat input → Click Send
5. Agent reads skill assets → plans → writes HTML file → live preview
6. Results appear in "Design Files" tab with iframe preview, slide navigation

### Tips
- Agent selection: click the sidebar agent button to open settings → Execution mode → pick Claude Code or Codex
- Design system: "None — freeform" works fine; click to expand for options
- After generating, use Preview tab to see the live deck, Present for full-screen

---

## Known Agent Write Bug — FIXED ✅

> **Status: Fixed** (2026-05-05)
> Fix PR: not upstreamed — custom patch in local clone

### Root Cause (see references/agent-write-bug-analysis.md for detailed analysis)
The daemon's `createAgentRuntimeToolPrompt` told the agent to "prefer OD_BIN wrapper commands over raw HTTP" — but this was ambiguous: Claude Code interpreted "Write is a tool, should I route it through OD_BIN?" → passed empty params `{}` → `InputValidationError: file_path missing`.

### Fix Applied
Two changes in `apps/daemon/src/`:

**1. Prompt conflict resolution** (`server.ts:474-496` — `createAgentRuntimeToolPrompt`):
- Renamed `## Runtime tool environment` → `## Daemon environment — connectors & live-artifacts only`
- Added explicit disclaimer: "This section does NOT affect file operations. Your native Read/Write/Edit/Bash tools work exactly as before."
- Called out Write parameters by name: `file_path` and `content` are unchanged
- Changed `"tools ..."` examples to specific `"tools connectors ..."` / `"tools live-artifacts ..."`
- Changed "Prefer project wrapper commands" → "Use OD_BIN wrapper only for connector tools and live-artifact tools"

**2. Stronger permissions bypass** (`agents.ts:136-186` — `AGENT_DEFS` config):
- Added `--dangerously-skip-permissions` flag detection to capability map
- When Claude Code 2.1+ advertises this flag, use it instead of the weaker `--permission-mode bypassPermissions`
- Fallback to legacy mode for older Claude Code versions

### Verification
```
Web UI → Claude Code → Write test-deck.html → 81 lines, 2260 bytes → done ✅
File written to: .od/projects/<uuid>/test-deck.html
No (unnamed) error. Zero errors.
Agent processing time: ~27s
```

### Rebuilding After Fix
```bash
cd apps/daemon
# Force rebuild (tsc uses incremental caching)
rm -f dist/server.js dist/agents.js
npx tsc -p tsconfig.json
npx tsc -p tsconfig.sidecar.json
kill <daemon-pid>
OD_WEB_PORT=3000 node dist/cli.js --no-open
```

---

## CORS Pitfall

| Symptom | Cause | Fix |
|---------|-------|-----|
| `daemon 403: {"error":"Cross-origin requests are not allowed"}` | Web UI on :3000, daemon on :7456 — daemon doesn't trust the web origin | Pass `OD_WEB_PORT=3000` when starting daemon |

The daemon's `buildAllowedOrigins()` (server.ts:1014) only trusts loopback addresses + the bind host + `OD_WEB_PORT`. Without the env var, the Web UI's origin is not in the allowed set.

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| better-sqlite3 not compiled | Daemon fails: `Could not locate the bindings file` | `npx prebuild-install` in better-sqlite3 dir |
| Electron download timeout | `pnpm install` fails on electron postinstall | Use `--ignore-scripts`, skip Electron |
| Daemon spawns but agent fails | No Claude Code process, "AGENT_UNAVAILABLE" | Check `ps aux | grep claude` — daemon strips `ANTHROPIC_API_KEY` but Claude Code uses `ANTHROPIC_AUTH_TOKEN` from settings.json, so auth should still work |
| **CORS 403** | `Cross-origin requests are not allowed` | `OD_WEB_PORT=3000` on daemon start |
| **Write tool returns empty params** (pre-fix) | `InputValidationError: file_path missing` | Apply the prompt conflict fix in server.ts (see above) |
| Daemon restart doesn't pick up code changes | Old behavior persists | `pnpm tools-dev stop` → rebuild → restart |
| Web UI stuck on "Loading workspace…" | Next.js dev server not fully booted or daemon not responding | Wait for Next.js "Ready" log, check daemon:7446/api/skills |
| Agents not detected | "no agent selected" in sidebar | Click the button → opens settings → check agents are detected, click "↻ Rescan" |

---

## Debugging Commands

```bash
# Check daemon responds
curl -s http://127.0.0.1:7456/api/skills | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Skills: {len(d[\"skills\"])}')"

# List available agents
curl -s http://127.0.0.1:7456/api/agents | python3 -m json.tool

# Check daemon process
lsof -i :7456

# Check web is listening
lsof -i :3000

# Check agent process
ps aux | grep claude | grep -v grep | grep -v staam

# Find project directories and files
ls ~/open-design/.od/projects/
find ~/open-design/.od/projects -type f -not -path "*/.od-skills/*"

# Check daemon process (background mode)
ps aux | grep "node dist/cli" | grep -v grep

# Run daemon tests
cd apps/daemon && npx vitest run -c vitest.config.ts
```

---

## Related Skills / References

- `references/agent-write-bug-analysis.md` — Full bug analysis with SSE trace, error payloads, and fix details
- `references/ppt-master-mac-workaround.md` — PPT Master on Mac compatibility (alternative toolchain)

---

## User-Facing PPT Generation Guide

> Absorbed from `open-design-ppt` (archived). This section covers the **user's workflow** when daemon + web are already running.

### Quick Start

1. Open `http://localhost:3000`
2. Select **"Slide deck"** tab
3. Ensure agent is selected: sidebar shows `"Local CLI · Claude Code · 2.1.126 (Claude Code)"`
4. Enter project name → Click **Create**
5. In chat input, type a detailed prompt → Click **Send** (⌘+Enter)
6. Agent reads skill assets → plans → **writes** HTML file → live preview
7. Deck appears in "Design Files" tab with iframe, slide navigation, Present mode

### PPT-Relevant Built-in Skills

| Skill ID | Style | Best For |
|----------|-------|----------|
| `magazine-web-ppt` (default) | Magazine editorial, WebGL fluid background, serif titles | Brand decks, creative proposals |
| `html-ppt` + variants | 36+ templates (pitch-deck, tech-sharing, xhs-post, etc.) | Structured presentations |
| `kami-deck` | Print-grade, parchment paper, ink-blue accent | White papers, editorial |
| `simple-deck` | Minimal, text-focused | Internal reports |
| `replit-deck` | Tech, code-mixed | Product demos |

### Prompt Template

```markdown
Create a [N]-slide magazine-style deck for "[Campaign Name]".

**Brand:** [Brand] — [Role]
**Partner:** [Partner] — [Role]
**Theme:** #[Tagline]#
**Core Message:** [One-line positioning]

**Emotional Lines:**
1. [Name] — [Description]
...

**Slide Structure (30 slides):**
01 Cover: [Title]
02 Table of Contents
03–04 [Section A]
...
**Visual:** Magazine editorial, Chinese typography, brand accent (#HEX)
```

### File Output Convention

- Output: self-contained HTML (all CSS/JS embedded, Google Fonts CDN)
- Default location: `.od/projects/<uuid>/` (within OD project dir)
- For desktop access: copy to `~/Desktop/<Project-Name>.html`
- Typical size: ~100KB for 30 slides

### Common User Questions

| Q | A |
|---|----|
| Can I bypass OD and use Claude Code directly? | Write bug is now fixed — use the Web UI as the primary path. |
| Where is the generated HTML file? | `.od/projects/<uuid>/<filename>.html` — use the Download button or copy from project dir. |
| Why daemon on 7456 instead of 17456? | Old docs were incorrect. Default is 7456 (from `startServer` in `server.ts`). |
| Feishu can't send HTML via MEDIA | Feishu limitation — share file path, upload to Feishu Drive, or screenshot. |
