#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.components.file_governance import FileGovernance
from evoclaw.runtime.hooks.before_task import run_before_task
from evoclaw.runtime.hooks.before_subtask import run_before_subtask


def main() -> int:
    gov = FileGovernance()
    count = gov.refresh_catalog()
    assert count > 0

    # precheck blocks core when not review-only
    pre = gov.catalog_precheck(["evoclaw/runtime/message_handler.py"], mode="auto")
    assert pre["pass"] is False

    # enforce block direct write on core
    direct = gov.catalog_enforce("evoclaw/runtime/message_handler.py", mode="auto", operation="direct_write")
    assert direct["allowed"] is False

    # patch transaction on working file
    tmp_rel = "docs/week5-governance-tmp.md"
    apply_result = gov.transactional_patch_apply(
        tmp_rel,
        "# week5 temp\n",
        evidence_hash="evidence-week5",
        policy_version="v1",
    )
    assert apply_result["success"] is True
    (WORKSPACE / tmp_rel).unlink(missing_ok=True)

    # before hooks should include catalog precheck payload
    bt = run_before_task("请检查 docs 下文件", context={"file_scope": ["docs/implementation-rollout-plan-2026-03-10.md"]})
    assert "file_governance" in bt

    bs = run_before_subtask(
        parent_task_id="task_week5",
        subtask_info={
            "subtask_id": "st_week5",
            "subtask_type": "edit_file",
            "goal": "edit docs",
            "file_scope": ["docs/implementation-rollout-plan-2026-03-10.md"],
        },
        task_info={"task_type": "coding", "scenario": "edit", "risk_level": "low"},
    )
    assert "file_governance" in bs

    print("WEEK5_FILE_GOVERNANCE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
