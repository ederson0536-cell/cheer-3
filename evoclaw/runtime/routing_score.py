"""Routing score reference implementation with decision trace output.

Usage:
  python3 evoclaw/runtime/routing_score.py <skill_registry.json> [weights.json] [trace_out.json]
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass

TRACE_VERSION = "1.0.0"
SCHEMA_VERSION = "decision-trace@1"
ROUTER_VERSION = "router@0.2.0"
POLICY_VERSION = "policy@2026-03-06"

TRUST_MAP = {
    "unverified": 0.25,
    "low": 0.4,
    "medium": 0.7,
    "high": 1.0,
}
DEFAULT_FEATURES = {
    "rule_alignment": 0.5,
    "success_rate": 0.5,
    "rework_rate": 0.5,
    "latency_penalty": 0.5,
    "scenario_match": 0.5,
}


@dataclass
class Weights:
    w1: float = 0.20
    w2: float = 0.25
    w3: float = 0.15
    w4: float = 0.10
    w5: float = 0.15
    w6: float = 0.15


def load_weights(path: str | None) -> Weights:
    if not path:
        return Weights()
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return Weights(**{k: payload.get(k, getattr(Weights(), k)) for k in asdict(Weights()).keys()})


def score_skill(skill: dict, hard_constraint_pass: int = 1, w: Weights = Weights()) -> tuple[float, dict]:
    feature_payload = skill.get("routing_features", {})
    f = {k: feature_payload.get(k, v) for k, v in DEFAULT_FEATURES.items()}
    trust_level = TRUST_MAP.get(skill.get("trust_level", "unverified"), TRUST_MAP["unverified"])

    score = hard_constraint_pass * (
        w.w1 * f["rule_alignment"]
        + w.w2 * f["success_rate"]
        - w.w3 * f["rework_rate"]
        - w.w4 * f["latency_penalty"]
        + w.w5 * trust_level
        + w.w6 * f["scenario_match"]
    )

    bounded = max(0.0, min(1.0, round(score, 4)))
    breakdown = {
        "rule_alignment": f["rule_alignment"],
        "success_rate": f["success_rate"],
        "rework_rate": f["rework_rate"],
        "latency_penalty": f["latency_penalty"],
        "trust_level": trust_level,
        "scenario_match": f["scenario_match"],
    }
    return bounded, breakdown


def band(score: float) -> str:
    if score > 0.75:
        return "auto_execute"
    if score >= 0.60:
        return "cautious_review_or_canary"
    return "reject_auto"


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage: python3 routing_score.py <skill_registry.json> [weights.json] [trace_out.json]")
        return 1

    weights = load_weights(sys.argv[2] if len(sys.argv) >= 3 else None)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        payload = json.load(f)

    rows = []
    traces = []
    for skill in payload.get("skills", []):
        s, breakdown = score_skill(skill, w=weights)
        decision = band(s)
        rows.append((skill["skill_id"], s, decision))
        traces.append(
            {
                "trace_version": TRACE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "router_version": ROUTER_VERSION,
                "policy_version": POLICY_VERSION,
                "object_id": skill["skill_id"],
                "decision_type": "subtask_routing",
                "selected": skill["skill_id"],
                "candidates": [x["skill_id"] for x in payload.get("skills", [])],
                "score_breakdown": breakdown,
                "final_score": s,
                "decision": decision,
            }
        )

    rows.sort(key=lambda x: x[1], reverse=True)
    for skill_id, s, b in rows:
        print(f"{skill_id}\t{s}\t{b}")

    if len(sys.argv) == 4:
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(traces, f, indent=2)
            f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
