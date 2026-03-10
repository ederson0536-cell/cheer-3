#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.outcome_evaluator import evaluate_outcome
from evoclaw.runtime.message_handler import MessageHandler


def main() -> int:
    success_case = evaluate_outcome(
        interaction_success=True,
        execution_success=True,
        goal_success=True,
        governance_success=True,
        done_criteria_met=True,
        constraint_check_passed=True,
        validation_check_passed=True,
    )
    assert success_case["overall_outcome"] == "success"

    partial_case = evaluate_outcome(
        interaction_success=True,
        execution_success=True,
        goal_success=False,
        governance_success=True,
        done_criteria_met=True,
        constraint_check_passed=True,
        validation_check_passed=False,
    )
    assert partial_case["overall_outcome"] == "partial"

    fail_case = evaluate_outcome(
        interaction_success=True,
        execution_success=False,
        goal_success=False,
        governance_success=True,
        done_criteria_met=False,
        constraint_check_passed=False,
        validation_check_passed=False,
    )
    assert fail_case["overall_outcome"] == "failure"

    handler = MessageHandler()
    try:
        handler.handle("no chain metadata", metadata={})
        raise AssertionError("chain guard should reject missing metadata")
    except ValueError:
        pass

    print("WEEK3_RUNTIME_GATES_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
