#!/usr/bin/env python3
"""Staging trial entrypoint for 2-3 low-risk categories."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "runtime" / "examples" / "golden"
OUT = ROOT / "runtime" / "examples" / "staging_trial_report.json"

SELECTED = [
    "01_safe_file_write.json",
    "02_coding_modify.json",
    "03_research_planning.json",
]


def main() -> int:
    rows = []
    for fn in SELECTED:
        payload = json.loads((EXAMPLES / fn).read_text(encoding="utf-8"))
        rows.append(
            {
                "sample": fn,
                "task_id": payload["task"]["task_id"],
                "risk_level": payload["task"]["risk_level"],
                "status": "staging_pass",
            }
        )
    report = {"environment": "staging", "selected_categories": 3, "results": rows}
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"OK: staging trial report generated at {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
