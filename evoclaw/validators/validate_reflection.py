#!/usr/bin/env python3
"""
EvoClaw Reflection Validator (SQLite-first).

Usage:
  python3 evoclaw/validators/validate_reflection.py <db_or_json> [--id REF-...]
"""

import json
import os
import re
import sqlite3
import sys

REF_ID_PATTERN = re.compile(r"^REF-")
VALID_TRIGGERS = {"gap", "drift", "contradiction", "growth", "refinement"}


def _is_db_path(path):
    return str(path).endswith(".db")


def _load_reflections_from_db(db_path, reflection_id=None):
    out = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM reflections"
        params = []
        if reflection_id:
            sql += " WHERE id = ?"
            params.append(reflection_id)
        sql += " ORDER BY created_at DESC LIMIT 2000"
        for row in conn.execute(sql, params).fetchall():
            analysis = {}
            proposals = []
            if row["analysis_json"]:
                try:
                    parsed = json.loads(row["analysis_json"])
                    if isinstance(parsed, dict):
                        analysis = parsed
                except Exception:
                    pass
            if row["proposals_json"]:
                try:
                    parsed = json.loads(row["proposals_json"])
                    if isinstance(parsed, list):
                        proposals = parsed
                except Exception:
                    pass
            out.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "trigger": row["trigger"],
                    "notable_count": row["notable_count"],
                    "analysis": analysis,
                    "proposals": proposals,
                }
            )
    return out


def _load_reflection_from_json(path):
    with open(path, encoding="utf-8") as f:
        parsed = json.load(f)
    return [parsed] if isinstance(parsed, dict) else []


def _validate_single(ref):
    errors = []
    warnings = []
    rid = str(ref.get("id") or "")
    if not rid:
        errors.append({"field": "id", "message": "Missing id"})
    elif not REF_ID_PATTERN.match(rid):
        warnings.append({"field": "id", "message": f"Unexpected reflection id format: {rid}"})

    ts = ref.get("timestamp")
    if not ts:
        errors.append({"field": "timestamp", "message": "Missing timestamp"})

    trigger = str(ref.get("trigger") or "")
    if not trigger:
        errors.append({"field": "trigger", "message": "Missing trigger"})

    notable_count = ref.get("notable_count")
    if not isinstance(notable_count, int) or notable_count < 0:
        errors.append({"field": "notable_count", "message": "notable_count must be non-negative integer"})

    analysis = ref.get("analysis")
    if not isinstance(analysis, dict):
        errors.append({"field": "analysis", "message": "analysis must be object"})
        analysis = {}

    insights = analysis.get("insights", [])
    if not isinstance(insights, list) or len(insights) == 0:
        errors.append({"field": "analysis.insights", "message": "insights must be a non-empty array"})

    summary = analysis.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        errors.append({"field": "analysis.summary", "message": "summary must be non-empty"})

    decision = analysis.get("proposal_decision")
    proposals = ref.get("proposals", [])
    if not isinstance(proposals, list):
        errors.append({"field": "proposals", "message": "proposals must be an array"})
        proposals = []

    if not isinstance(decision, dict):
        errors.append({"field": "analysis.proposal_decision", "message": "proposal_decision must be object"})
    else:
        should = decision.get("should_propose")
        triggers = decision.get("triggers_fired", [])
        reasoning = decision.get("reasoning", "")
        if not isinstance(should, bool):
            errors.append({"field": "analysis.proposal_decision.should_propose", "message": "must be boolean"})
        if not isinstance(triggers, list):
            errors.append({"field": "analysis.proposal_decision.triggers_fired", "message": "must be array"})
            triggers = []
        for t in triggers:
            if t not in VALID_TRIGGERS:
                errors.append({"field": "analysis.proposal_decision.triggers_fired", "message": f"invalid trigger: {t}"})
        if not isinstance(reasoning, str) or not reasoning.strip():
            errors.append({"field": "analysis.proposal_decision.reasoning", "message": "must be non-empty"})
        if isinstance(should, bool):
            if should and len(proposals) == 0:
                errors.append({"field": "proposals", "message": "should_propose=true but proposals is empty"})
            if (not should) and len(proposals) > 0:
                errors.append({"field": "proposals", "message": "should_propose=false but proposals has entries"})
            if should and len(triggers) == 0:
                errors.append({"field": "analysis.proposal_decision.triggers_fired", "message": "missing triggers when should_propose=true"})

    return errors, warnings


def validate(target, reflection_id=None):
    errors = []
    warnings = []
    if not os.path.exists(target):
        return {"status": "FAIL", "file": target, "errors": [{"field": None, "message": f"Input not found: {target}"}], "warnings": []}

    rows = _load_reflections_from_db(target, reflection_id) if _is_db_path(target) else _load_reflection_from_json(target)
    if not rows:
        warnings.append({"field": None, "message": "No reflections found"})

    for ref in rows:
        e, w = _validate_single(ref)
        errors.extend(e)
        warnings.extend(w)

    return {"status": "FAIL" if errors else "PASS", "file": target, "errors": errors, "warnings": warnings, "stats": {"validated": len(rows)}}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_reflection.py <db_or_json> [--id REF-...]", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]
    reflection_id = None
    if "--id" in sys.argv:
        idx = sys.argv.index("--id")
        if idx + 1 < len(sys.argv):
            reflection_id = sys.argv[idx + 1]
    result = validate(target, reflection_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] == "PASS" else 1)
