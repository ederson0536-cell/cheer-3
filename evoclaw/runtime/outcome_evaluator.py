#!/usr/bin/env python3
"""Unified outcome evaluator for Week3 runtime gates."""

from __future__ import annotations

from typing import Any


def evaluate_outcome(
    *,
    interaction_success: bool,
    execution_success: bool,
    goal_success: bool,
    governance_success: bool,
    done_criteria_met: bool,
    constraint_check_passed: bool,
    validation_check_passed: bool,
) -> dict[str, Any]:
    correctness_pass = done_criteria_met and constraint_check_passed and validation_check_passed

    if interaction_success and execution_success and goal_success and governance_success and correctness_pass:
        overall_outcome = "success"
    elif interaction_success and governance_success and (execution_success or goal_success):
        overall_outcome = "partial"
    else:
        overall_outcome = "failure"

    return {
        "interaction_success": interaction_success,
        "execution_success": execution_success,
        "goal_success": goal_success,
        "governance_success": governance_success,
        "done_criteria_met": done_criteria_met,
        "constraint_check_passed": constraint_check_passed,
        "validation_check_passed": validation_check_passed,
        "overall_outcome": overall_outcome,
    }
