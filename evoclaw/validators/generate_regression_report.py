#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "runtime" / "contracts"
EXAMPLES = ROOT / "runtime" / "examples"
GOLDEN = EXAMPLES / "golden" / "golden_manifest.json"
DIRTY = EXAMPLES / "dirty" / "dirty_manifest.json"
OUT = EXAMPLES / "regression_report.json"


def _validate(schema: Path, payload: dict) -> bool:
    import jsonschema  # type: ignore

    try:
        jsonschema.validate(payload, json.loads(schema.read_text(encoding="utf-8")))
        return True
    except Exception:
        return False


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        import jsonschema  # noqa: F401
    except Exception:
        print("jsonschema required")
        return 2

    task_schema = CONTRACTS / "task_subtask.schema.json"
    skill_schema = CONTRACTS / "skill_registry.schema.json"
    proposal_schema = CONTRACTS / "proposal_pipeline.schema.json"

    report = {
        "meta": {
            "environment": "staging",
            "baseline_windows": ["rolling_7d", "rolling_30d"],
            "sample_scope": ["golden_runtime_regression", "dirty_input_regression"],
        },
        "results": [],
        "summary": {"pass": 0, "warning": 0, "fail": 0},
    }

    g = _load(GOLDEN)
    for sample in g["samples"]:
        payload = _load(ROOT.parent / sample["path"])
        ok = _validate(task_schema, payload)
        status = "pass" if ok else "fail"
        report["summary"][status] += 1
        report["results"].append({"id": sample["id"], "suite": "golden", "status": status})

    d = _load(DIRTY)
    for sample in d["samples"]:
        payload = _load(ROOT.parent / sample["path"])
        sid = sample["id"]
        if "near_threshold" in sid:
            ok = _validate(skill_schema, payload)
            status = "warning" if ok else "fail"
        elif "weak_proposal" in sid:
            ok = _validate(proposal_schema, payload)
            status = "warning" if ok else "fail"
        else:
            ok = _validate(task_schema, payload)
            if sample["expected"] == "fail":
                status = "pass" if not ok else "warning"
            else:
                status = "warning" if ok else "fail"
        report["summary"][status] += 1
        report["results"].append({"id": sid, "suite": "dirty", "status": status, "expected": sample["expected"]})

    # baseline compare snapshot
    dashboard = _load(EXAMPLES / "baseline.layered_dashboard.json") if (EXAMPLES / "baseline.layered_dashboard.json").exists() else {}
    report["baseline_compare"] = {
        "rolling_7d": {
            "task_success_rate": dashboard.get("execution_layer", {}).get("task_success_rate", 0.0),
            "rollback_rate": dashboard.get("evolution_layer", {}).get("rollback_rate", 0.0),
        },
        "rolling_30d": {
            "task_success_rate": dashboard.get("execution_layer", {}).get("task_success_rate", 0.0),
            "rollback_rate": dashboard.get("evolution_layer", {}).get("rollback_rate", 0.0),
        },
    }

    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"OK: regression report generated at {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
