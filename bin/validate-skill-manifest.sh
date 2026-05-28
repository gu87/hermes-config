#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/skills/.hub/hermes-skill-manifest.json"
REGISTRY="$ROOT/config/agent-registry.json"

python3 - "$ROOT" "$MANIFEST" "$REGISTRY" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
registry_path = Path(sys.argv[3])

manifest = json.loads(manifest_path.read_text())
registry = json.loads(registry_path.read_text())
known_agents = set(registry.get("agents", {}).keys())

errors = []
seen = set()

for item in manifest.get("skills", []):
    skill_id = item.get("id")
    rel_path = item.get("path")
    if not skill_id:
        errors.append("skill item missing id")
        continue
    if skill_id in seen:
        errors.append(f"duplicate skill id: {skill_id}")
    seen.add(skill_id)

    if not rel_path:
        errors.append(f"{skill_id}: missing path")
        continue
    skill_path = root / rel_path
    if not skill_path.exists():
        errors.append(f"{skill_id}: path does not exist: {rel_path}")
        continue

    text = skill_path.read_text()
    match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        errors.append(f"{skill_id}: missing frontmatter")
    else:
        name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", match.group(1), re.M)
        if not name_match:
            errors.append(f"{skill_id}: frontmatter missing name")
        elif name_match.group(1).strip() != skill_id:
            errors.append(
                f"{skill_id}: frontmatter name is {name_match.group(1).strip()!r}"
            )

    for agent in item.get("agents", []):
        if agent not in known_agents:
            errors.append(f"{skill_id}: unknown agent {agent}")

if errors:
    print("Skill manifest validation failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print(f"Skill manifest OK: {len(manifest.get('skills', []))} skills")
PY

