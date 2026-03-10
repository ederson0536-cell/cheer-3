#!/usr/bin/env python3
"""Validate memory/evoclaw-state.json integrity."""

from __future__ import annotations

import json
import os
import sys
from datetime import date


def _count_pending(proposals_dir: str) -> int:
    pending = os.path.join(proposals_dir, "pending.jsonl")
    if not os.path.exists(pending):
        return 0
    count = 0
    with open(pending, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def validate(state_file: str, memory_dir: str | None = None, proposals_dir: str | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    if not os.path.exists(state_file):
        return {
            "status": "FAIL",
            "file": state_file,
            "errors": [{"field": "file", "message": f"State file not found: {state_file}"}],
            "warnings": [],
            "stats": {},
        }

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as exc:
        return {
            "status": "FAIL",
            "file": state_file,
            "errors": [{"field": "json", "message": f"Invalid JSON: {exc}"}],
            "warnings": [],
            "stats": {},
        }

    today = date.today().isoformat()
    experience_count = state.get("experience_count_today")
    if experience_count is None:
        warnings.append({"field": "experience_count_today", "message": "experience_count_today missing"})
    elif not isinstance(experience_count, int) or experience_count < 0:
        errors.append({"field": "experience_count_today", "message": "experience_count_today must be non-negative int"})

    state_today = state.get("today")
    if state_today and state_today != today:
        warnings.append({"field": "today", "message": f"state.today={state_today} differs from current date {today}"})

    if proposals_dir:
        pending_expected = _count_pending(proposals_dir)
        pending_recorded = state.get("pending_proposals")
        if pending_recorded is not None and pending_recorded != pending_expected:
            warnings.append(
                {
                    "field": "pending_proposals",
                    "message": f"pending_proposals={pending_recorded} but pending.jsonl has {pending_expected} entries",
                }
            )

    status = "FAIL" if errors else "PASS"
    return {
        "status": status,
        "file": state_file,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "today": state_today,
            "experience_count_today": experience_count,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_state.py <state_file> [--memory-dir memory] [--proposals-dir memory/proposals]", file=sys.stderr)
        sys.exit(2)

    state_file = sys.argv[1]
    memory_dir = None
    proposals_dir = None
    if "--memory-dir" in sys.argv:
        idx = sys.argv.index("--memory-dir")
        if idx + 1 < len(sys.argv):
            memory_dir = sys.argv[idx + 1]
    if "--proposals-dir" in sys.argv:
        idx = sys.argv.index("--proposals-dir")
        if idx + 1 < len(sys.argv):
            proposals_dir = sys.argv[idx + 1]

    result = validate(state_file, memory_dir, proposals_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)
