---
name: kanban-orchestrator
description: Decomposition playbook + specialist-roster conventions + anti-temptation rules for an orchestrator profile routing work through Kanban. The "don't do the work yourself" rule and the basic lifecycle are auto-injected into every kanban worker's system prompt; this skill is the deeper playbook when you're specifically playing the orchestrator role.
tags: [kanban, multi-agent, orchestration, routing]
category: devops
related_skills: [kanban-worker]
---

# Kanban Orchestrator — Decomposition Playbook

> The **core worker lifecycle** (including the `kanban_create` fan-out pattern and the "don't do the work yourself" rule) is auto-injected into every kanban process via the `KANBAN_GUIDANCE` system-prompt block. This skill is the deeper playbook when you're an orchestrator profile whose whole job is routing.

## First-time Setup

Before orchestrating work, ensure a board exists:

```bash
hermes kanban boards create <slug> --name "Display Name"
hermes kanban boards switch <slug>
```

Each board has its own SQLite DB under `~/.hermes/kanban/boards/<slug>/kanban.db` and isolated workspaces. The `default` board always exists.

After setup, verify in Web UI: http://127.0.0.1:8787/ → Kanban tab → select your board.

### Board management

```bash
# Create (slug must be lowercase alphanumeric + hyphens/underscores)
hermes kanban boards create dongqiudi --name "懂球帝营销中心"

# Rename display name (slug stays immutable)
hermes kanban boards rename <slug> "新名称"

# List all boards
hermes kanban boards list

# Switch active board
hermes kanban boards switch <slug>

# Board slugs are permanent once created. To change the displayed name,
# use `rename` — the slug remains the system identifier.
```

## When to use the board (vs. just doing the work)

Create Kanban tasks when any of these are true:

1. **Multiple specialists are needed.** Research + analysis + writing is three profiles.
2. **The work should survive a crash or restart.** Long-running, recurring, or important.
3. **The user might want to interject.** Human-in-the-loop at any step.
4. **Multiple subtasks can run in parallel.** Fan-out for speed.
5. **Review / iteration is expected.** A reviewer profile loops on drafter output.
6. **The audit trail matters.** Board rows persist in SQLite forever.

If *none* of those apply — it's a small one-shot reasoning task — use `delegate_task` instead or answer the user directly.

## The anti-temptation rules

Your job description says "route, don't execute." The rules that enforce that:

- **Do not execute the work yourself.** Your restricted toolset usually doesn't even include terminal/file/code/web for implementation. If you find yourself "just fixing this quickly" — stop and create a task for the right specialist.
- **For any concrete task, create a Kanban task and assign it.** Every single time.
- **If no specialist fits, ask the user which profile to create.** Do not default to doing it yourself under "close enough."
- **Decompose, route, and summarize — that's the whole job.**

## The standard specialist roster (convention)

Unless the user's setup has customized profiles, assume these exist. Adjust to whatever the user actually has — ask if you're unsure.

| Profile | Does | Typical workspace |
|---|---|---|
| `researcher` | Reads sources, gathers facts, writes findings | `scratch` |
| `analyst` | Synthesizes, ranks, de-dupes. Consumes multiple `researcher` outputs | `scratch` |
| `writer` | Drafts prose in the user's voice | `scratch` or `dir:` into their Obsidian vault |
| `reviewer` | Reads output, leaves findings, gates approval | `scratch` |
| `backend-eng` | Writes server-side code | `worktree` |
| `frontend-eng` | Writes client-side code | `worktree` |
| `ops` | Runs scripts, manages services, handles deployments | `dir:` into ops scripts repo |
| `pm` | Writes specs, acceptance criteria | `scratch` |

## Decomposition playbook

### Step 0 — Verify profile kanban readiness

Before creating any tasks, confirm each intended assignee profile can load the `kanban-worker` skill:

```bash
hermes -p <profile> --skills kanban-worker -z "hello"
```

If it fails with `Error: Unknown skill(s): kanban-worker`, symlink the `devops` category (which contains kanban-worker) into the profile:

```bash
ln -s /path/to/global/skills/devops /path/to/profile/skills/devops
```

Retest until it works. A profile that can't load `kanban-worker` will crash immediately on dispatch, wasting retry attempts and blocking the entire dependency chain.

### Step 1 — Understand the goal

Ask clarifying questions if the goal is ambiguous. Cheap to ask; expensive to spawn the wrong fleet.

### Step 2 — Sketch the task graph

Before creating anything, draft the graph out loud (in your response to the user). Example for "Analyze whether we should migrate to Postgres":

```
T1  researcher        research: Postgres cost vs current
T2  researcher        research: Postgres performance vs current
T3  analyst           synthesize migration recommendation       parents: T1, T2
T4  writer            draft decision memo                       parents: T3
```

Show this to the user. Let them correct it before you create anything.

### Step 3 — Create tasks and link

Use the `kanban create` CLI or `kanban_create` tool. **The flag is `--parent` (singular, repeatable), NOT `--parents`:**

```bash
# CLI approach
hermes kanban create "research: Postgres cost" --assignee researcher
hermes kanban create "synthesize recommendation" --assignee analyst --parent t_abc123
```

```python
# Tool approach
t1 = kanban_create(
    title="research: Postgres cost vs current",
    assignee="researcher",
    body="Compare estimated infrastructure costs, migration costs, and ongoing ops costs over a 3-year window.",
    tenant=os.environ.get("HERMES_TENANT"),
)["task_id"]

t2 = kanban_create(
    title="research: Postgres performance vs current",
    assignee="researcher",
    body="Compare query latency, throughput, and scaling characteristics.",
)["task_id"]

t3 = kanban_create(
    title="synthesize migration recommendation",
    assignee="analyst",
    body="Read findings from T1 and T2. Produce a 1-page recommendation.",
    parents=[t1, t2],
)["task_id"]
```

`parents=[...]` gates promotion — children stay in `todo` until every parent reaches `done`, then auto-promote to `ready`. No manual coordination needed.

### Step 4 — Complete your own task

If you were spawned as a task yourself, mark it done with a summary:

```python
kanban_complete(
    summary="decomposed into T1-T4: 2 researchers parallel, 1 analyst on their outputs, 1 writer on the recommendation",
    metadata={
        "task_graph": {
            "T1": {"assignee": "researcher", "parents": []},
            "T2": {"assignee": "researcher", "parents": []},
            "T3": {"assignee": "analyst", "parents": ["T1", "T2"]},
            "T4": {"assignee": "writer", "parents": ["T3"]},
        },
    },
)
```

### Step 5 — Report back to the user

> I've queued 4 tasks:
> - **T1** (researcher): cost comparison
> - **T2** (researcher): performance comparison, in parallel with T1
> - **T3** (analyst): synthesizes T1 + T2 into a recommendation
> - **T4** (writer): turns T3 into a CTO memo
>
> The dispatcher will pick up T1 and T2 now. T3 starts when both finish. Use the dashboard or `hermes kanban tail <id>` to follow along.

## Common patterns

**Fan-out + fan-in (research → synthesize):** N `researcher` tasks with no parents, one `analyst` task with all of them as parents.

**Pipeline with gates:** `pm → backend-eng → reviewer`. Each stage's `parents=[previous_task]`. Reviewer blocks or completes; if reviewer blocks, the operator unblocks with feedback and respawns.

**Same-profile queue:** 50 tasks, all assigned to `translator`, no dependencies between them. Dispatcher serializes.

**Human-in-the-loop:** Any task can `kanban_block()` to wait for input. Dispatcher respawns after `/unblock`.

## Common pitfalls

### Reassignment vs. new task
If a reviewer blocks with "needs changes", create a NEW task linked from the reviewer's task — don't re-run the same task.

### Argument order for links
`kanban_link(parent_id=..., child_id=...)` — parent first. Mixing them up demotes the wrong task to `todo`.

### --parent flag is singular
`hermes kanban create ... --parent T1 --parent T2`, NOT `--parents T1 T2`.

### Dependency shape
Don't pre-create the whole graph if the shape depends on intermediate findings. Let T3 exist as a "synthesize findings" task whose own first step is to read parent handoffs and plan the rest.

### Tenant inheritance
If `HERMES_TENANT` is set, pass `tenant=os.environ.get("HERMES_TENANT")` on every `kanban_create` call.

## Dispatcher crash recovery

When a kanban worker crashes during dispatch, you'll see:

```
Error: Unknown skill(s): kanban-worker
```

The task stays in `blocked` state.

### Diagnostic — is the kanban-worker skill available for this profile?

The most common root cause: the **profile's skills directory lacks the `devops` category** (where `kanban-worker` lives). The dispatcher loads skills from `~/.hermes/profiles/<profile>/skills/`, and if `devops/` isn't there, the worker crashes immediately.

```bash
# Check if kanban-worker is available for the profile
hermes -p <profile> skills list | grep kanban-worker
# Expected output: │ kanban-worker │ devops │ builtin │ builtin │ enabled │
# Empty output = skill not available

# Check if the profile has the devops skills directory
ls ~/.hermes/profiles/<profile>/skills/devops/ 2>/dev/null
```

**Fix:** Symlink the global devops skills into the profile:

```bash
ln -s /Users/gu/.hermes/skills/devops /Users/gu/.hermes/profiles/<profile>/skills/devops
```

Then re-dispatch the blocked task:

```bash
hermes kanban unblock <task_id>
hermes kanban dispatch
```

If `hermes -p <profile> skills list` returns empty entirely (no skills listed), the profile may have been cloned and trimmed — check `ls ~/.hermes/profiles/<profile>/skills/` for the full picture.

### Other crash causes

1. `kanban-worker` skill isn't installed at the system level — check `hermes skills list | grep kanban-worker` (should show as builtin)
2. DeepSeek API model inference times out during initial load — test with `hermes -p <profile> -z "hello"`
3. The profile's gateway is stopped or misconfigured
4. Disk space or workspace permissions

### Manual recovery procedure

```bash
# 1. Check what happened
hermes kanban log <task_id>

# 2. If skill issue: check and fix per-profile skill availability (see above)
# 3. Unblock the task
hermes kanban unblock <task_id>

# 4. Try dispatching again, or complete the work manually:
#    - Use delegate_task to have the agent do the work
#    - Then mark the kanban task complete
hermes kanban complete <task_id> --summary "description of work done"

# 5. Downstream tasks auto-promote when their parent completes
```

If the same profile keeps crashing after fixing skills:
- Reassign to a different profile: `hermes kanban reassign <task_id> <new-profile>`
- Rename the profile: `hermes profile rename <old-name> <new-name>` (note: this does NOT update agent-registry.json — do that separately)
- Test connectivity: `hermes -p <profile> -z "hello"`

## Profile rename for kanban workers

Kanban boards display **profile names** (from the filesystem), not display names from agent-registry.json. To change how a profile appears in the Web UI Kanban tab:

```bash
hermes profile rename <old-name> <new-name>
```

This renames the profile directory under `~/.hermes/profiles/` and updates the profile registry. After renaming, new tasks created with `--assignee <new-name>` will display correctly.

**Side effects:**
- Existing kanban tasks assigned to the old name still show the old name
- The agent-registry.json key is NOT automatically updated — if the profile also serves as an agent_id for `delegate_task`, update agent-registry.json separately
- The profile's config.yaml and SOUL.md remain intact

## Web UI verification

After setting up boards and tasks, verify everything is visible:

1. Open http://127.0.0.1:8787/ in browser
2. Click the **Kanban** tab in the left sidebar
3. Select your board from the dropdown (e.g. "懂球帝运营")
4. Verify:
   - Tasks grouped by assignee (per-agent columns)
   - Each task shows id, title, body preview, assignee, comment count
   - "完成" and "归档" buttons are clickable
   - Assignee filter shows all active profiles
5. Run the dispatcher manually from the board UI or CLI: `hermes kanban dispatch`

## Reference documents

- `references/dongqiudi-kanban-setup-2026-05-13.md` — 完整看板创建 + 任务链 + 调度演示实录
- `references/kanban-dispatcher-crash-debug.md` — Dispatcher 崩溃诊断与修复参考
- `references/profile-skill-trimming-ambrosini-2026-05-13.md` — 质量审核角色 skill 裁剪实录（保留 19/155）

## Recovering stuck workers

When a worker profile keeps crashing, hallucinating, or getting blocked by its own mistakes, the kanban dashboard flags the task with a ⚠ badge and opens a **Recovery** section.

Three primary actions from the dashboard drawer:

1. **Reclaim** (`hermes kanban reclaim <task_id>`) — abort the running worker, reset to `ready`
2. **Reassign** (`hermes kanban reassign <task_id> <new-profile> --reclaim`) — switch profile
3. **Change profile model** — dashboard prints a copy-paste hint; edit in a terminal, then Reclaim

Hallucination warnings appear on tasks where a worker's `kanban_complete(created_cards=[...])` claim includes card ids that don't exist or weren't created by the worker's profile. These produce audit events that persist even after recovery.
