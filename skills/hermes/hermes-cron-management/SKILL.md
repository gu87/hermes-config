---
name: hermes-cron-management
description: Hermes Agent cron job lifecycle — create, update, troubleshoot, and ensure scheduled tasks fire correctly. Covers the cronjob tool API, Gateway dependency, environment setup, and common failure modes.
tags: [hermes, cron, scheduler, automation]
---

# Hermes Cron Job Management

## Overview

Hermes has a built-in cron scheduler. Jobs are stored in `~/.hermes/cron/jobs.json` and fired by the **Gateway's tick mechanism** — meaning the Gateway must be running for cron jobs to execute automatically.

## The `cronjob` Tool — Critical Pitfalls

### ⚠️ PITFALL #1: `cronjob(action='update')` SILENTLY OVERWRITES `prompt`

The `cronjob` tool's `update` action requires **BOTH** `job_id` AND a new `prompt` string. If you call it without providing the original prompt, it will **overwrite it** with whatever you pass.

**Bad (will destroy the prompt):**
```
cronjob(action='update', job_id='16a6b3e04d52')
# → prompt becomes '' or whatever default
```

**Good — always read the full job before updating:**
```python
# 1. Read the jobs file directly
read_file(path='~/.hermes/cron/jobs.json')

# 2. Find the job by ID, extract its prompt

# 3. Update with prompt included
cronjob(action='update', job_id='16a6b3e04d52', prompt='<original prompt content>')
```

**SAFEST approach: Use `patch` on the JSON file directly, not the cronjob tool.**
```bash
# Read the file
read_file(path='~/.hermes/cron/jobs.json')

# Patch just the field you need to change
# (prompt stays untouched this way)
patch(old_string='old field value', new_string='new field value', path='~/.hermes/cron/jobs.json')
```

### Recovering an Overwritten Cron Prompt

If you accidentally overwrite a cron job's prompt (e.g., called `cronjob(action='update')` without the original prompt):

1. **Check the JSON file immediately** — if you're lucky, only the session's in-memory copy was modified, and the file still has the original (only applies if cronjob tool differs from direct file write):
   ```bash
   # Read the jobs file
   cat ~/.hermes/cron/jobs.json | python3 -c "import sys,json; jobs=json.load(sys.stdin)['jobs']; [print(f'{j[\"id\"]}: {j.get(\"prompt\",\"\")[:100]}') for j in jobs]"
   ```

2. **If already overwritten in the file**, reconstruct from session history:
   ```bash
   # Search session history by cron job name or related keywords
   session_search(query="zhipuai-coding-plan-grab cron 智谱")
   # Or search the raw SQLite database
   sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE content LIKE '%keyword%'"
   ```

3. **If unrecoverable from history**, reconstruct from context:
   - Check the standalone script (if any) at `~/<script_name>.py`
   - Check the cron job's `enabled_toolsets` to infer what tools it needs
   - Check `origin` field to know where to deliver output
   - Rebuild based on job name and schedule

4. **Safe update after recovery:**
   ```bash
   # Use patch on the JSON file directly (NOT the cronjob tool)
   # Replace the prompt field
   patch(new_string='"job_id": "xxx",\n  "prompt": "your recovered prompt",', old_string='"job_id": "xxx",\n  "prompt": "placeholder",', path='~/.hermes/cron/jobs.json')
   ```
   
   Or re-write the entire job entry in the JSON file with `write_file` or direct editing.

**Prevention: Never use `cronjob(action='update')` without explicitly preparing the full prompt first.** Always read `~/.hermes/cron/jobs.json`, extract the current prompt, and pass it back.

### ⚠️ PITFALL #2: `cronjob(action='update')` ALWAYS REQUIRES A `prompt` PARAMETER

Even if you just want to change the schedule or toolsets, you MUST pass the prompt. It's not an optional field — omitting it causes data loss. Always read the job first and re-pass the full prompt.

## Cron Jobs Don't Fire Without the Gateway

The cron scheduler runs inside Hermes Gateway. If the Gateway isn't running, **cron jobs will NOT fire**.

**Check Gateway status:**
```bash
hermes gateway status
```

**Start Gateway if needed:**
```bash
# Background process (preferred — bypasses launchd issues)
terminal(background=true): hermes gateway run --replace

# Or via launchd
hermes gateway start
```

**Verify gateway is alive:**
```bash
ps aux | grep hermes | grep -v grep
# Should show a hermes gateway process
```

## Environment Setup for Cron Jobs

### Python Dependencies

Hermes venv (`~/.hermes/hermes-agent/venv/`) uses **uv** for package management, NOT pip.

```bash
# Inside Hermes venv
uv pip install <package>
```

Note: `python3 -m pip` does NOT work in the Hermes venv (pip is not installed).

### Chrome CDP for Browser-Based Cron Tasks

If the cron job uses browser automation (e.g., a grab/purchase script), Chrome must be running with `--remote-debugging-port=9222`:

```bash
# Start regular Chrome with CDP
terminal(background=true): /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir="$HOME/.hermes/chrome-profile"

# Verify CDP is ready
curl -s http://localhost:9222/json/version
# → Should return Chrome version JSON
```

Note: Regular Google Chrome works fine — Chrome for Testing is NOT required.

## Job Storage & Direct Access

Jobs are stored as JSON:

**File:** `~/.hermes/cron/jobs.json`

```json
{
  "jobs": [
    {
      "id": "16a6b3e04d52",
      "name": "my-cron-job",
      "prompt": "...",
      "schedule": { "kind": "once", "run_at": "..." },
      "state": "scheduled",
      "enabled": true,
      "enabled_toolsets": ["browser", "web", "terminal"]
    }
  ]
}
```

For safe edits (avoiding the cronjob tool's update pitfalls), use `patch` directly on this file.

## Gateway Respawn Patterns

If cron jobs need to survive Mac sleep/wake cycles:
- `hermes gateway run --replace` as a background terminal process
- launchd plist (`~/Library/LaunchAgents/ai.hermes.gateway.plist`) for system-level persistence
- Note: launchd can kill the gateway if drain takes > 60s

## Cron Job States

| State | Meaning |
|-------|---------|
| `scheduled` | Waiting to fire |
| `running` | Currently executing |
| `completed` | Done (one-shot jobs) |
| `paused` | Manually paused |
| `failed` | Execution error |

## Common Failure Patterns

1. **Job not firing** → Gateway down. Start Gateway.
2. **Job fires but does nothing** → Prompt overwritten (see Pitfall #1). Restore from jobs.json backup or session history.
3. **Chrome CDP fails** → Chrome not started with `--remote-debugging-port`. Start it.
4. **Python import error** → Dependency not installed in Hermes venv. Use `uv pip install`.
5. **Output not delivered** → `deliver` field misconfigured. Set to `"origin"` to send output back to the Feishu/Telegram chat that created the job.

## One-Shot Job Design Pattern (e.g., Time-Sensitive Purchases)

For time-sensitive cron tasks (flash sales, limited-stock purchases):

1. Schedule the cron job **2 minutes before** the target time (e.g., 09:58 for a 10:00 sale)
2. The script should include a **wait loop** to the exact second
3. Use **dual strategy**: API first (fast), browser CDP second (reliable)
4. Always include a **fallback notification** so the user can manually act
4. The standalone script path can be referenced in the cron prompt: `python3 ~/grab_script.py`

### Polling Frequency for Sub-Second Timing

For flash sales where stock sells out in <500ms:

```python
# 100ms polling loop — NOT 500ms
import time
while time.time() < target_timestamp:
    time.sleep(0.001)  # busy-wait until exact second

# 100ms polling for button state
while True:
    btn = find_purchase_button()
    if btn and not btn.disabled:
        btn.click()
        break
    time.sleep(0.1)  # 100ms — fast enough to catch a 500ms window
```

**Why 500ms fails:** A stock that sells out in 300ms with a random 0-500ms offset between polls means you can miss it entirely.

### Non-Headless Chrome for Cron Browser Tasks

When headless Chrome gets rate-limited by the target site, start non-headless Chrome from the cron prompt:

```bash
terminal(background=true): /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
  --remote-debugging-port=9222 \\
  --remote-allow-origins=* \\
  --no-first-run --no-default-browser-check \\
  --user-data-dir="$HOME/.hermes/chrome-profile" \\
  "https://target-site.com/buy"
```

Then use `browser_navigate`/`browser_click` Hermes tools for interaction. The non-headless window appears on the user's screen — they may need to log in manually before automation can proceed.

**Key CDP flag that must be included:**
```bash
--remote-allow-origins=*
# Without this, WebSocket connections fail with HTTP 403:
# "Rejected an incoming WebSocket connection from the http://localhost:9222 origin."
```
