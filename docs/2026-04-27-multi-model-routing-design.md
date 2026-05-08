# Multi-Model Routing Design

**Date:** 2026-04-27  
**Status:** Draft — pending user approval

## Goal

Route different task types to the best-fit model automatically, without manual `/model` switching. Specifically: heavy coding tasks → Claude Sonnet/Opus; cheap/fast tasks → MiniMax; research/analysis → DeepSeek; long-context tasks → Kimi.

## Approach: SOUL.md Prompt Routing (Method A)

Add a routing decision block to `~/.hermes/SOUL.md` that instructs Hermes to pick the right model based on task type.

## Constraints Found During Testing

Testing revealed two key constraints:

1. **`delegate_task` has no `model` parameter.** The tool schema exposes no way to dynamically specify the model for a subtask. Subagent model is always read from `delegation.model` in `config.yaml` (static).

2. **`model.default` does not resolve aliases.** `_resolve_gateway_model()` in `gateway/run.py` returns the raw string without alias lookup. Writing an alias name like `df` to `model.default` sends that literal string to the API and causes an error.

3. **`/model <alias>` works correctly.** It uses `model_switch.py` with full alias resolution and persists the resolved full model name (not the alias) to `config.yaml`.

## What Is Actually Feasible

### Tier 1: Hermes main agent — session-level switch via `/model`

At the start of each conversation, Hermes can assess the task type and issue `/model <alias>` to switch itself to the appropriate model for the session. This is a coarse switch (per session, not per turn), but it covers the most impactful case: when a user arrives with a clearly heavy coding request, Hermes switches to Claude; when the request is simple Q&A, it stays on MiniMax.

### Tier 2: Coding subtasks → Claude Code via `acp_command`

For coding subtasks delegated via `delegate_task`, Hermes can route to Claude Code specifically using:
```json
{
  "goal": "...",
  "acp_command": "claude",
  "acp_args": ["--model", "claude-sonnet-4-6", "--acp", "--stdio"]
}
```
This is already partially documented in the existing `agent-routing-guide` skill at `~/.hermes/skills/autonomous-ai-agents/agent-routing-guide/SKILL.md`.

### Tier 3: DeepSeek/Kimi subtasks — NOT dynamically routable

There is no mechanism to send a subtask to a different Hermes-model variant dynamically. The `delegation.model` in config.yaml is static. This tier is out of scope for the SOUL.md approach.

## SOUL.md Routing Block Design

The following block will be appended to `~/.hermes/SOUL.md`:

```markdown
## Model Routing

At the start of each conversation, assess the task and switch to the appropriate model before responding:

| Task type | Model alias | When to use |
|-----------|-------------|-------------|
| Heavy coding, debugging, code review | `cs` (Claude Sonnet) | Writing/fixing/reviewing non-trivial code |
| Complex coding, architecture | `co` (Claude Opus) | Architecture design, hard bugs |
| Research, analysis, long documents | `dp` (DeepSeek Pro) | Web research, document analysis |
| Long-context tasks (>100k tokens) | `k26` (Kimi K2.6) | Very long files, massive codebases |
| Simple Q&A, quick tasks, translation | (stay on MiniMax) | Default — fast and cheap |

**How to switch:** Issue `/model <alias>` as your first action before any other response.

**For coding subtasks via delegate_task:** Use `acp_command: "claude"` (no extra acp_args needed) to route the subtask to Claude Code. Claude Code runs in ACP mode automatically.

**Do not switch mid-conversation** unless the task type changes significantly. One switch per session is the norm.
```

## Files Changed

| File | Change |
|------|--------|
| `~/.hermes/SOUL.md` | Append routing block |

No code changes. No config changes. No new files beyond this spec.

## What This Does NOT Cover

- Dynamic per-turn model switching (not feasible with current Hermes API)
- Routing non-coding subtasks to DeepSeek/Kimi via delegate_task (no model param in tool schema)
- Automatic model switching without LLM judgment (would require gateway code changes)

## Testing Plan

1. Open Hermes, send a clear coding request → verify Hermes issues `/model cs` before responding
2. Open Hermes, send a simple Q&A → verify Hermes stays on MiniMax (no switch)
3. Ask Hermes to delegate a coding task → verify `acp_command: "claude"` is used in the delegate_task call
