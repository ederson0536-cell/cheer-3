#!/usr/bin/env python3
"""Run one realistic sample package through contracts + routing + proposal path."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "runtime" / "contracts"
EXAMPLES = ROOT / "runtime" / "examples"


def validate(schema_path: Path, payload: dict) -> None:
    import jsonschema  # type: ignore

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def main() -> int:
    try:
        import jsonschema  # noqa: F401
    except Exception:
        print("jsonschema is required")
        return 2

    package = json.loads((EXAMPLES / "real_sample.config_update.json").read_text(encoding="utf-8"))
    skills = json.loads((EXAMPLES / "skill_registry.example.json").read_text(encoding="utf-8"))

    validate(CONTRACTS / "task_subtask.schema.json", package)
    validate(CONTRACTS / "skill_registry.schema.json", skills)

    traces = []
    for st in package["subtasks"]:
        # tiny realistic heuristic, replace by runtime router later
        if st["subtask_type"] == "edit_file":
            selected, score = "coding_editor_v1", 0.81
        else:
            selected, score = "generic_helper_v1", 0.67
        traces.append(
            {
                "trace_version": "1.0.0",
                "schema_version": "decision-trace@1",
                "router_version": "router@0.2.0",
                "policy_version": "policy@2026-03-06",
                "object_id": st["subtask_id"],
                "decision_type": "subtask_routing",
                "selected": selected,
                "candidates": ["coding_editor_v1", "generic_helper_v1"],
                "score_breakdown": {"scenario_match": score},
                "final_score": score,
                "decision": "auto_execute" if score > 0.75 else "cautious_review_or_canary",
            }
        )

    proposal = {
        "proposal": {
            "proposal_id": "pp_real_001",
            "source": "after_task",
            "candidate_type": "routing_weight_update_candidate",
            "payload": {"target": "coding_editor_v1", "delta": {"w2": 0.01}},
            "status": "review_pending",
        },
        "review": {
            "review_id": "rv_real_001",
            "proposal_id": "pp_real_001",
            "decision": "canary_only",
            "reviewer": "governance_gate",
            "notes": "real sample canary",
        },
        "publish": {
            "publish_id": "pb_real_001",
            "proposal_id": "pp_real_001",
            "action": "canary",
            "status": "queued",
            "canary_report_id": None,
            "rollback_reason": None,
        },
    }
    validate(CONTRACTS / "proposal_pipeline.schema.json", proposal)

    out = {
        "package": "real_sample.config_update",
        "subtask_count": len(package["subtasks"]),
        "decision_traces": traces,
        "proposal_flow": proposal,
    }
    out_path = EXAMPLES / "decision_trace.real_sample.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"OK: real sample package passed, trace written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
