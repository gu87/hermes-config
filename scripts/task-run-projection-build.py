#!/usr/bin/env python3
"""
Hermes Unified Task/Run Contract — Phase 1B

Full-rebuild shadow projection tool for the Task Card Pipeline.

Reads Pipeline original data, calls Phase 1A pure mapping functions,
and writes a deterministic, atomic, deletable shadow projection JSONL.

Usage:
  python3 scripts/task-run-projection-build.py --project staam
  python3 scripts/task-run-projection-build.py --project staam --team-dir /custom/path
  python3 scripts/task-run-projection-build.py --project staam --output /custom/output.jsonl

Data sources consumed:
  - inbox/*.json          → map_task_card
  - review/*.json         → map_gate_record
  - runs/ledger.jsonl     → map_ledger_record
  - outbox/*.json         → map_outbox_record
  - events.jsonl          → map_events_jsonl_record (ledger-deduplicated fallback)

Permanently excluded:
  - tasks/index.jsonl     → derived read model, not an authoritative input

Design invariants:
  - Atomic write: temp file → flush+fsync → os.replace.
  - Deterministic: same input always produces byte-identical output.
  - No input files are ever modified.
  - MappingError and UnsupportedRecord are written, never silently dropped.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Load Phase 1A module
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
_spec = importlib.util.spec_from_file_location(
    "task_run_projection", str(_SCRIPTS / "task-run-projection.py")
)
_proj = importlib.util.module_from_spec(_spec)
sys.modules["task_run_projection"] = _proj
assert _spec.loader is not None
_spec.loader.exec_module(_proj)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_team_dir(project: str) -> Path:
    """Return ~/.claude/teams/{project}."""
    return Path.home() / ".claude" / "teams" / project


def _default_output(project: str) -> Path:
    """Return ~/.hermes/projections/task-card-pipeline/{project}/events.jsonl."""
    return Path.home() / ".hermes" / "projections" / "task-card-pipeline" / project / "events.jsonl"


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read and parse a JSON file.  Returns (parsed, error_message)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, None  # missing is not an error for optional sources
    except json.JSONDecodeError as exc:
        return None, f"JSON decode error: {exc}"
    except OSError as exc:
        return None, f"OS error: {exc}"


def _read_jsonl(path: Path) -> List[Tuple[int, Dict[str, Any], Optional[str]]]:
    """Read a JSONL file.  Returns list of (line_number, parsed_record, error_message).
    line_number is 1-based.
    """
    rows: List[Tuple[int, Dict[str, Any], Optional[str]]] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rows.append((lineno, json.loads(stripped), None))
                except json.JSONDecodeError as exc:
                    rows.append((lineno, {}, f"JSONL decode error line {lineno}: {exc}"))
    except FileNotFoundError:
        pass  # missing ledger is optional
    except OSError as exc:
        rows.append((0, {}, f"OS error reading {path}: {exc}"))
    return rows


def _projection_to_dict(obj: Any) -> Dict[str, Any]:
    """Serialize a dataclass instance to a dict with projection_type metadata."""
    if not dataclasses.is_dataclass(obj):
        return {"projection_type": type(obj).__name__, "value": str(obj)}
    d = dataclasses.asdict(obj)
    d["projection_type"] = type(obj).__name__
    return d


def _collect_inbox(
    team_dir: Path, project_id: str
) -> List[Dict[str, Any]]:
    """Read all inbox/*.json files, sorted for deterministic output.

    Each record carries source_location for traceability.
    """
    records: List[Dict[str, Any]] = []
    inbox_dir = team_dir / "inbox"
    if not inbox_dir.is_dir():
        return records

    for fpath in sorted(inbox_dir.glob("*.json")):
        parsed, err = _read_json(fpath)
        if err is not None:
            records.append({
                "_source_location": f"{fpath}",
                "_parse_error": err,
            })
            continue
        if isinstance(parsed, dict):
            parsed["_source_location"] = str(fpath)
            records.append(parsed)
        else:
            records.append({
                "_source_location": str(fpath),
                "_parse_error": f"not a JSON object: {type(parsed).__name__}",
            })
    return records


def _collect_review(
    team_dir: Path, project_id: str
) -> List[Dict[str, Any]]:
    """Read all review/*.json files, sorted for deterministic output."""
    records: List[Dict[str, Any]] = []
    review_dir = team_dir / "review"
    if not review_dir.is_dir():
        return records

    for fpath in sorted(review_dir.glob("*.json")):
        parsed, err = _read_json(fpath)
        if err is not None:
            records.append({
                "_source_location": f"{fpath}",
                "_parse_error": err,
            })
            continue
        if isinstance(parsed, dict):
            parsed["_source_location"] = str(fpath)
            records.append(parsed)
        else:
            records.append({
                "_source_location": str(fpath),
                "_parse_error": f"not a JSON object: {type(parsed).__name__}",
            })
    return records


def _collect_events_jsonl(
    team_dir: Path, project_id: str
) -> List[Dict[str, Any]]:
    """Read events.jsonl, preserving line order. Non-object lines are parse errors."""
    records: List[Dict[str, Any]] = []
    events_path = team_dir / "events.jsonl"
    rows = _read_jsonl(events_path)
    for lineno, parsed, err in rows:
        loc = f"{events_path}:{lineno}"
        if err is not None:
            records.append({"_source_location": loc, "_parse_error": err})
            continue
        if not isinstance(parsed, dict):
            records.append({
                "_source_location": loc,
                "_parse_error": (
                    f"JSONL line is not an object: {type(parsed).__name__}"
                ),
            })
            continue
        parsed["_source_location"] = loc
        records.append(parsed)
    return records


def _collect_outbox(
    team_dir: Path, project_id: str
) -> List[Dict[str, Any]]:
    """Read all outbox/*.json files, sorted for deterministic output."""
    records: List[Dict[str, Any]] = []
    outbox_dir = team_dir / "outbox"
    if not outbox_dir.is_dir():
        return records

    for fpath in sorted(outbox_dir.glob("*.json")):
        parsed, err = _read_json(fpath)
        loc = str(fpath)
        if err is not None:
            records.append({"_source_location": loc, "_parse_error": err})
            continue
        if isinstance(parsed, dict):
            parsed["_source_location"] = loc
            records.append(parsed)
        else:
            records.append({
                "_source_location": loc,
                "_parse_error": f"not a JSON object: {type(parsed).__name__}",
            })
    return records


def _collect_ledger(
    team_dir: Path, project_id: str
) -> List[Dict[str, Any]]:
    """Read runs/ledger.jsonl, preserving line order (deterministic per file).

    Each record gets source_location including line number.
    Non-object JSONL values (arrays, strings, numbers, null) are recorded
    as parse errors — never passed to mappers and never cause a crash.
    """
    records: List[Dict[str, Any]] = []
    ledger_path = team_dir / "runs" / "ledger.jsonl"
    rows = _read_jsonl(ledger_path)
    for lineno, parsed, err in rows:
        loc = f"{ledger_path}:{lineno}"
        if err is not None:
            records.append({"_source_location": loc, "_parse_error": err})
            continue
        if not isinstance(parsed, dict):
            records.append({
                "_source_location": loc,
                "_parse_error": (
                    f"JSONL line is not an object: {type(parsed).__name__}"
                    f" (value={json.dumps(parsed, ensure_ascii=False, default=str)[:120]})"
                ),
            })
            continue
        parsed["_source_location"] = loc
        records.append(parsed)
    return records


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _sort_key(record: Dict[str, Any]) -> Tuple[int, str, str, str]:
    """Deterministic sort key for a projection record.

    Order: source type → source_location → projection_type → stable identity.

    Source type: inbox=0, review=1, ledger=2.
    Unknown source_location → "".
    """
    loc = str(record.get("source_location") or "")
    ptype = str(record.get("projection_type") or "")

    # Source type order: inbox=0, review=1, ledger=2, outbox=3, events=4, unknown=5
    if "/inbox/" in loc.replace("\\", "/"):
        src_order = 0
    elif "/review/" in loc.replace("\\", "/"):
        src_order = 1
    elif "/ledger.jsonl" in loc.replace("\\", "/") or "/runs/" in loc.replace("\\", "/"):
        src_order = 2
    elif "/outbox/" in loc.replace("\\", "/"):
        src_order = 3
    elif "/events.jsonl" in loc.replace("\\", "/"):
        src_order = 4
    else:
        src_order = 5  # unknown — still deterministic

    # Stable identity: prefer id field, fall back to JSON dump
    identity = record.get("id") or record.get("event_id") or ""
    if not identity:
        identity = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)

    return (src_order, loc, ptype, identity)


def build_projection(
    project_id: str,
    team_dir: Path,
) -> List[Dict[str, Any]]:
    """Full rebuild: read all supported sources, apply Phase 1A mappers,
    return sorted list of projection dicts ready for JSONL serialisation.

    Deterministic ordering is enforced via _sort_key AFTER collecting all
    records — does not rely on mapper return order.
    """
    unsorted: List[Dict[str, Any]] = []

    def _emit(*items: Any) -> None:
        for item in items:
            unsorted.append(_projection_to_dict(item))

    # --- Pre-collect ledger lifecycle keys for events.jsonl dedup ---
    ledger_keys: set = set()
    for record in _collect_ledger(team_dir, project_id):
        key = _proj.ledger_lifecycle_key(record)
        if key is not None:
            ledger_keys.add(key)

    # --- inbox ---
    for record in _collect_inbox(team_dir, project_id):
        loc = record.pop("_source_location", None)
        parse_err = record.pop("_parse_error", None)
        if parse_err is not None:
            _emit(_proj.MappingError(error=parse_err, source_location=loc,
                                     raw_record_summary=""))
            continue
        _emit(*_proj.map_task_card(project_id, record, source_location=loc))

    # --- review ---
    for record in _collect_review(team_dir, project_id):
        loc = record.pop("_source_location", None)
        parse_err = record.pop("_parse_error", None)
        if parse_err is not None:
            _emit(_proj.MappingError(error=parse_err, source_location=loc,
                                     raw_record_summary=""))
            continue
        _emit(*_proj.map_gate_record(project_id, record, source_location=loc))

    # --- ledger ---
    for record in _collect_ledger(team_dir, project_id):
        loc = record.pop("_source_location", None)
        parse_err = record.pop("_parse_error", None)
        if parse_err is not None:
            _emit(_proj.MappingError(error=parse_err, source_location=loc,
                                     raw_record_summary=""))
            continue
        _emit(*_proj.map_ledger_record(project_id, record, source_location=loc))

    # --- outbox ---
    for record in _collect_outbox(team_dir, project_id):
        loc = record.pop("_source_location", None)
        parse_err = record.pop("_parse_error", None)
        if parse_err is not None:
            _emit(_proj.MappingError(error=parse_err, source_location=loc,
                                     raw_record_summary=""))
            continue
        _emit(*_proj.map_outbox_record(project_id, record, source_location=loc))

    # --- events.jsonl (fallback: skip records that duplicate ledger lifecycle) ---
    for record in _collect_events_jsonl(team_dir, project_id):
        loc = record.pop("_source_location", None)
        parse_err = record.pop("_parse_error", None)
        if parse_err is not None:
            _emit(_proj.MappingError(error=parse_err, source_location=loc,
                                     raw_record_summary=""))
            continue
        # Dedup: skip if a semantically identical ledger lifecycle_event exists
        ev_key = _proj._events_jsonl_lifecycle_key(record)
        if ev_key in ledger_keys:
            continue  # contract-mandated skip, not an error
        _emit(*_proj.map_events_jsonl_record(project_id, record, source_location=loc))

    unsorted.sort(key=_sort_key)
    return unsorted


def write_projection(records: List[Dict[str, Any]], output_path: Path) -> None:
    """Atomically write projection records to output_path as JSONL.

    1. Write to <output_path>.tmp.<pid> in the same directory.
    2. flush + fsync.
    3. os.replace() to atomically swap in the new file.

    If anything fails, the temp file is cleaned up and the existing
    output file is never touched.
    """
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Unique temp file: pid + random token to prevent collisions between
    # sequential or concurrent builds in the same process.
    token = secrets.token_hex(8)
    tmp_path = output_path.parent / f"{output_path.name}.tmp.{os.getpid()}.{token}"

    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, output_path)
    except Exception:
        # Clean up temp file on failure; leave existing output untouched.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hermes Task Card Pipeline — shadow projection builder (Phase 1B)"
    )
    parser.add_argument(
        "--project", required=True,
        help="Project identifier (maps to ~/.claude/teams/<project>)"
    )
    parser.add_argument(
        "--team-dir", default=None,
        help="Override team directory (default: ~/.claude/teams/<project>)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Override output path (default: ~/.hermes/projections/task-card-pipeline/<project>/events.jsonl)"
    )
    args = parser.parse_args(argv)

    project_id = args.project.strip()
    if not project_id:
        print("error: --project must be non-empty", file=sys.stderr)
        return 2

    team_dir = Path(args.team_dir).expanduser() if args.team_dir else _default_team_dir(project_id)
    output_path = Path(args.output).expanduser() if args.output else _default_output(project_id)

    if not team_dir.is_dir():
        print(f"error: team directory not found: {team_dir}", file=sys.stderr)
        return 1

    records = build_projection(project_id, team_dir)
    write_projection(records, output_path)

    print(f"Projection written: {output_path}  ({len(records)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
