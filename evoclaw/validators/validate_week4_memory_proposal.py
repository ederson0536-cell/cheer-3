#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.components.memory_lifecycle import MemoryLifecycle
from evoclaw.runtime.components.proposal_processor import CompleteProposalProcessor
from evoclaw.runtime.components.governance import GovernanceGate


def main() -> int:
    lifecycle = MemoryLifecycle()

    # ingest dedup + schema guard
    first = lifecycle.ingest({
        "record_type": "episodic",
        "memory_status": "episodic",
        "schema_version": "v1",
        "task_id": "task_w4",
        "content": "same content",
        "source_hook": "after_task",
    })
    assert first["accepted"] is True and first["deduped"] is False

    second = lifecycle.ingest({
        "record_type": "episodic",
        "memory_status": "episodic",
        "schema_version": "v1",
        "task_id": "task_w4",
        "content": "same content",
        "source_hook": "after_task",
    })
    assert second["accepted"] is True and second["deduped"] is True

    bad = lifecycle.ingest({"record_type": "episodic", "schema_version": "v999"})
    assert bad["accepted"] is False

    guard_block = lifecycle.promotion_guard("candidate", "semantic", reviewed=False, confidence=0.95)
    assert guard_block["allowed"] is False

    guard_pass = lifecycle.promotion_guard("candidate", "semantic", reviewed=True, confidence=0.95)
    assert guard_pass["allowed"] is True

    # proposal priority + merge
    processor = CompleteProposalProcessor()
    pid_1 = processor.add({
        "category": "repeated_failure",
        "description": "merge-me",
        "confidence": 0.8,
        "task_risk_level": "high",
        "source_hook": "after_task",
    })
    pid_2 = processor.add({
        "category": "repeated_failure",
        "description": "merge-me",
        "confidence": 0.7,
        "task_risk_level": "high",
        "source_hook": "after_task",
    })
    assert pid_1 == pid_2

    queue = processor.get_priority_queue(limit=1)
    assert len(queue) == 1
    assert int(queue[0].get("merge_count", 0)) >= 2

    # governance quorum check
    gate = GovernanceGate()
    gpid = gate.submit({
        "category": "rule_change",
        "confidence": 0.7,
        "proposal_status": "candidate",
    })
    assert gate.approve(gpid, reviewer="r1", notes="vote1") is False
    assert gate.approve(gpid, reviewer="r2", notes="vote2") is True

    print("WEEK4_MEMORY_PROPOSAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
