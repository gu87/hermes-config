---
name: context-skill-audit
description: "Audit Hermes Agent, model, skill, and runtime config drift."
version: 1.0.0
author: Hermes Agent (adapted from withkynam/vibecode-pro-max-kit vc-audit-context)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [audit, context, skills, agents, config, drift, doctor]
    related_skills: [hermes-system-diagnostics, hermes-agent-skill-authoring, codebase-scout]
agents:
- hermes-internal
- codex
- ambrosini
- deepseek-tui
---

# Context Skill Audit

Use this skill to find drift between Hermes' Agent roster, runtime registry, model pool, skill metadata, and self-check assumptions.

This is a Hermes-native adaptation of `vc-audit-context`. It intentionally does not assume `.claude/`, `.codex/`, or `process/` directories.

## Authority Map

Use these sources unless the user explicitly overrides them:

- Engineering source for managed Agents: `/Users/gu/.hermes/hermes-agent/configs/managed_agents/agents.yaml`
- Runtime mirror: `/Users/gu/.hermes/config/agent-registry.json`
- Model pool: `/Users/gu/.hermes/config/models.yaml`
- Subscription metadata: `/Users/gu/.hermes/config/model-subscriptions.yaml`
- Active Hermes skills: `/Users/gu/.hermes/skills/**/SKILL.md`

Treat `/Users/gu/.hermes/config/managed-agents.yaml` as suspect unless code proves it is still read.

## Audit Checklist

1. Compare Agent IDs in `agents.yaml` and `agent-registry.json`.
2. Verify every `model_ref` and every fallback-chain model exists in `models.yaml`.
3. Verify external CLI Agents (`claude`, `codex`) are not marked editable by internal model switching.
4. Verify each Agent has a non-empty `skills` list, except service-only pseudo agents.
5. Check skill frontmatter:
   - YAML parses.
   - `agents:` references canonical Agent IDs.
   - retired IDs such as `nesta` and `openclaw` do not appear in active skills.
6. Check skill/tool compatibility:
   - Browser skills require browser or equivalent MCP.
   - Terminal-heavy skills require terminal access.
   - Image generation skills require `image_gen` or an explicit external service.
7. Flag stale docs or tests that expect an old model assignment.

## Minimal Commands

```bash
cd /Users/gu/.hermes/hermes-agent
python scripts/sync_agent_registry.py --source configs/managed_agents/agents.yaml --output /tmp/agent-registry.check.json
python -m pytest -o addopts='' tests/managed_agents/test_config_files.py tests/managed_agents/test_router.py -q
```

For a fast local scan:

```bash
rg "nesta|openclaw" /Users/gu/.hermes/skills -g 'SKILL.md'
rg "model_ref|model_strategy|skills:" configs/managed_agents/agents.yaml
```

## Report Format

```markdown
## Drift Findings
- [severity] source A differs from source B: exact path and key

## Compatibility Findings
- [severity] Agent skill requires tool not present: agent, skill, missing tool

## Recommended Fix Order
1. Runtime-breaking config drift
2. External CLI boundary violations
3. Skill/tool mismatch
4. Stale docs/tests
```
