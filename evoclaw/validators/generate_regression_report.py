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
RULES_FILE = CONTRACTS / "regression_rules.yaml"


def _validate(schema: Path, payload: dict) -> bool:
    import jsonschema  # type: ignore

    try:
        jsonschema.validate(payload, json.loads(schema.read_text(encoding="utf-8")))
        return True
    except Exception:
        return False


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rules() -> dict:
    # keep parser dependency-free: file content is JSON-compatible YAML
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def _overall(summary: dict, total: int, rules: dict) -> tuple[str, str]:
    gate = rules.get("release_gate", {})
    min_pass_rate = float(gate.get("min_pass_rate", 0.7))
    max_warning = int(gate.get("max_warning_count", 3))
    max_fail = int(gate.get("max_fail_count", 0))

    pass_rate = (summary.get("pass", 0) / total) if total else 0.0
    fail_count = int(summary.get("fail", 0))
    warning_count = int(summary.get("warning", 0))

    if fail_count > max_fail:
        return "fail", rules.get("labels", {}).get("fail", "publish_blocked")
    if pass_rate >= min_pass_rate and warning_count <= max_warning:
        if warning_count == 0:
            return "pass", rules.get("labels", {}).get("pass", "allow_publish")
        return "warning", rules.get("labels", {}).get("warning", "manual_review_required")
    if fail_count == 0:
        return "warning", rules.get("labels", {}).get("warning", "manual_review_required")
    return "fail", rules.get("labels", {}).get("fail", "publish_blocked")


def main() -> int:
    try:
        import jsonschema  # noqa: F401
    except Exception:
        print("jsonschema required")
        return 2

    task_schema = CONTRACTS / "task_subtask.schema.json"
    skill_schema = CONTRACTS / "skill_registry.schema.json"
    proposal_schema = CONTRACTS / "proposal_pipeline.schema.json"
    rules = _load_rules()

    report = {
        "meta": {
            "environment": "staging",
            "baseline_windows": ["rolling_7d", "rolling_30d"],
            "sample_scope": [
                "golden_runtime_regression",
                "dirty_input_regression",
                "real_sample_package",
                "staging_trial",
            ],
            "regression_policy_version": rules.get("policy_version", "regression_rules_v1"),
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

    # real sample + staging trial files existence as minimal validation signals
    real_sample = EXAMPLES / "decision_trace.real_sample.json"
    if real_sample.exists():
        report["summary"]["pass"] += 1
        report["results"].append({"id": "real_sample_package", "suite": "real_sample", "status": "pass"})
    else:
        report["summary"]["fail"] += 1
        report["results"].append({"id": "real_sample_package", "suite": "real_sample", "status": "fail"})

    staging_report = EXAMPLES / "staging_trial_report.json"
    if staging_report.exists():
        report["summary"]["pass"] += 1
        report["results"].append({"id": "staging_trial", "suite": "staging", "status": "pass"})
    else:
        report["summary"]["warning"] += 1
        report["results"].append({"id": "staging_trial", "suite": "staging", "status": "warning"})

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

    total = sum(report["summary"].values())
    gate_status, gate_action = _overall(report["summary"], total, rules)
    report["release_gate"] = {
        "status": gate_status,
        "action": gate_action,
        "policy_version": rules.get("policy_version", "regression_rules_v1"),
        "total_cases": total,
    }

    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"OK: regression report generated at {OUT} (gate={gate_status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
