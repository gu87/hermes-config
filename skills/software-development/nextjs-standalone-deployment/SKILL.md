---
name: nextjs-standalone-deployment
description: Deploy and debug Next.js apps built with output:standalone on macOS — standalone server pattern, health checks, crash debugging.
tags: [nextjs, deployment, node, macos, debugging]
version: 1.0.0
---

# Next.js Standalone Deployment

Deploy and debug Next.js apps built with `output: 'standalone'` on macOS/Linux.

## When to Use
- Next.js app with `next build` + standalone output mode
- Deploying without Docker on a Mac
- Debugging "page stuck loading" issues on a deployed Next.js app

## Deployment Pattern

```bash
cd /path/to/app
pnpm build                    # produces .next/standalone/
MC_DATA_DIR=/path/to/data node .next/standalone/server.js
```

**CRITICAL:** Use `node .next/standalone/server.js` — NOT `pnpm start` (requires full node_modules).

### Key env vars
| Var | Purpose |
|-----|---------|
| `MC_DATA_DIR` | Data directory (SQLite DB, logs). Defaults to `.data/` |
| `PORT` | Server port (default 3000) |
| `OPENCLAW_HOME` | OpenClaw config dir |

### Standalone mode requirements
- Native addons (e.g., `better-sqlite3`) must be rebuilt for the target Node version: `pnpm rebuild <addon>`
- All env vars prefixed `NEXT_PUBLIC_*` are baked into the **client bundle** at build time — change requires rebuild
- Server-side vars (AUTH_*, OPENCLAW_*, MC_*) are read at runtime — no rebuild needed

## Health Check Probe

```bash
# Always check API health endpoint first when debugging stuck pages
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/setup
# 200 = server responding normally
# 000 = connection refused / server down
```

Common endpoints to probe:
- `/api/setup` — setup status
- `/api/health` or `/` — server alive

## Server Crash Debugging Flow

When user reports "page stuck / not loading":

1. **Poll background process** (IMMEDIATELY, before anything else)
   ```
   process_poll(session_id)
   ```
   If status = "exited", server crashed → restart and recheck.

2. **Check logs**
   ```
   cat /tmp/mc-server.log   # wherever you redirected stderr/stdout
   ```

3. **Port conflict check**
   ```
   lsof -i -P -n | grep LISTEN | grep :3000
   ```

4. **Curl health endpoint**
   ```
   curl -s http://localhost:3000/api/setup
   ```

**Do NOT read source files before checking process status.** Gu's preference: check if server is alive first, then investigate.

## Mission Control Specifics

builderz-labs/mission-control uses this pattern exactly:

```bash
cd /tmp/mission-control
pnpm install
pnpm build
MC_DATA_DIR=/tmp/mc-data node .next/standalone/server.js
```

- Default port: 3000
- Health check: `GET /api/setup` → `{"needsSetup": true|false}`
- Setup page: `/setup`
- Known crash: server process can exit silently (no log output) — always poll first
- Credentials: generated on first run at `http://localhost:3000/setup`

## Pitfalls
- Missing native addon rebuild after Node upgrade → `better-sqlite3` error
- Forgetting `NEXT_PUBLIC_*` vars require rebuild
- Using `pnpm start` instead of standalone server in production
- Server crashes silently — poll before investigating

## See Also
- `spike` — throwaway validation experiments
- `node-inspect-debugger` — debugging running Node code
