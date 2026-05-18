# Hermes Authority Map

Last updated: 2026-05-18

This document defines which file is authoritative for each kind of Hermes knowledge. Use it to prevent MEMORY.md, SOUL.md, skills, and Obsidian notes from drifting into overlapping records.

## Source Of Truth

| Area | Authoritative file | What belongs here | What does not belong here |
|------|--------------------|-------------------|---------------------------|
| Identity and operating boundaries | `/Users/gu/.hermes/SOUL.md` | Hermes identity, role boundaries, escalation rules, confirmed philosophy | Runtime ports, historical fixes, long tool notes |
| Always-on memory | `/Users/gu/.hermes/memories/MEMORY.md` | Stable facts needed in every turn, memory classification rules, pointers to authority docs | Detailed service status, one-off task progress, long configuration inventories |
| User preference memory | `/Users/gu/.hermes/memories/USER.md` | Stable user preferences and working style | Temporary opinions, inferred tool stacks not confirmed by Gu |
| Rich user profile | `/Users/gu/.hermes/memories/user-profile.md` | Longer profile notes when needed for external review or migration | Facts that must be injected every turn |
| Agent registry | `/Users/gu/.hermes/config/agent-registry.json` | Agent IDs, capabilities, toolsets, permissions, routing rules | Narrative role philosophy, troubleshooting history |
| Reusable procedures | `/Users/gu/.hermes/skills/**/SKILL.md` | Workflows, debugging playbooks, reusable checklists, tool operation methods | Always-on personal memory, current runtime status |
| Runtime operations | `/Users/gu/.hermes/docs/hermes-runtime-runbook.md` | Service labels, ports, health checks, restart and rollback commands | Philosophy, user preferences |
| Upgrade history | `/Users/gu/.hermes/docs/hermes-agent-upgrade-2026-05-18.md` | Upgrade facts, adopted upstream changes, rollback anchor | Day-to-day service runbook |
| Long-form knowledge | Obsidian / OpenChronicle | Long notes, history, low-frequency details, environment inventories | Facts Hermes must know before it can decide where to look |

## Memory Rules

- `MEMORY.md` should stay small and stable. It should say where to look, not copy every detail.
- `USER.md` should only contain preferences Gu has confirmed or repeatedly demonstrated.
- Do not write inferred tool stacks into memory unless Gu confirms them.
- Runtime facts are volatile. Check the service, config file, or runbook instead of trusting memory.
- Historical fixes go to docs or Obsidian; only the durable lesson becomes memory or skill.

## Agent Skill Scoping Status

As of 2026-05-18, Hermes Agent supports `subagent_profile.skills` in code, but the live `/Users/gu/.hermes/config/agent-registry.json` does not populate explicit `skills` arrays for each named agent.

Current effective scoping is:

1. Main Hermes prompt uses the hardcoded `HERMES_CORE_SKILLS` whitelist in `/Users/gu/.Hermes/hermes-agent/agent/prompt_builder.py`.
2. SKILL.md frontmatter `agents: [...]` tags describe intended agent visibility.
3. If a future registry entry adds `subagent_profile.skills`, delegate_task can inject the `skills` toolset for that child agent.

Do not describe the current system as fully registry-whitelisted until explicit `skills` arrays exist in `agent-registry.json`.

## Change Discipline

- For configuration changes: reread the target file after editing and run the smallest real validation.
- For core behavior changes: update the relevant skill or runbook in the same change.
- For broad reorganizations: commit only the files touched for that round; leave unrelated dirty files untouched.
