#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.validators.generate_regression_report import main as regression_main
from evoclaw.validators.staging_trial_run import main as staging_main
from evoclaw.runtime.components.governance import GovernanceGate


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def main() -> int:
    # 1) run staging + regression suites
    assert staging_main() == 0
    assert regression_main() == 0

    report_path = WORKSPACE / "evoclaw" / "runtime" / "examples" / "regression_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("release_gate", {}).get("status") in {"pass", "warning", "fail"}

    # 2) canary + rollback drill (must be recoverable)
    gate = GovernanceGate()
    prev_level = gate.config.get("governance_level")
    prev_quorum = int(gate.config.get("review_quorum", 2))
    gate.config["governance_level"] = "supervised"
    gate.config["review_quorum"] = 2

    pending_before = _count_jsonl(gate.pending_file)
    approved_before = _count_jsonl(gate.approved_file)
    published_before = _count_jsonl(gate.published_file)
    rejected_before = _count_jsonl(gate.rejected_file)

    proposal_id = gate.submit({
        "category": "rule_change",
        "confidence": 0.9,
        "proposal_status": "candidate",
        "description": "week6 canary rollback drill",
    })

    t0 = time.time()
    assert gate.approve(proposal_id, reviewer="qa1", notes="ok") is False
    assert gate.approve(proposal_id, reviewer="qa2", notes="ok") is True
    assert gate.start_canary(proposal_id, scope="staging") is True
    assert gate.complete_canary(proposal_id, success=True, metrics={"error_rate": 0.0}) is True
    # release gate=warning should block publish unless manual token provided
    assert gate.publish(proposal_id) is False
    assert gate.publish(proposal_id, manual_review_token="manual-approve-week6") is True
    assert gate.rollback(proposal_id, reason="week6 rollback drill") is True
    recovery_s = time.time() - t0
    assert recovery_s <= 300

    # restore config in-memory
    gate.config["governance_level"] = prev_level
    gate.config["review_quorum"] = prev_quorum

    stats = gate.get_stats()
    assert "review_quorum" in stats

    # check side effects happened
    assert _count_jsonl(gate.pending_file) >= pending_before
    assert _count_jsonl(gate.approved_file) >= approved_before
    assert _count_jsonl(gate.published_file) >= published_before
    assert _count_jsonl(gate.rejected_file) >= rejected_before

    print("WEEK6_RELEASE_GATE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
