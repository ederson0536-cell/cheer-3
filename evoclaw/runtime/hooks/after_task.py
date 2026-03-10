#!/usr/bin/env python3
"""after_task Hook - Week3 outcome-gated summary."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

WORKSPACE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.outcome_evaluator import evaluate_outcome


def run_after_task(
    task_id: str,
    task_info: dict,
    result: Any,
    error: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> dict:
    print(f"[after_task] Completing task: {task_id}")

    summary = generate_summary(task_id, task_info, result, error, user_feedback)
    update_episodic_memory(task_id, summary)
    proposals = check_for_proposals(task_info, result, error)
    log_task_outcome(task_id, summary)
    cleanup_working_memory(task_id)

    return {
        "hook": "after_task",
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "summary": summary,
        "proposals": proposals,
        "success": summary["overall_outcome"] == "success",
    }


def _extract_checks(task_info: dict, result: Any, error: Optional[str]) -> dict:
    done_criteria = bool(task_info.get("done_criteria") or task_info.get("candidate_subtasks"))
    constraint_ok = not bool(error) and not bool(task_info.get("policy_conflict", False))

    validation_ok = True
    if isinstance(result, dict):
        validation_ok = bool(result.get("validation_check_passed", True))
    if error:
        validation_ok = False

    interaction_success = True
    execution_success = not bool(error)
    goal_success = bool(execution_success and result is not None)
    governance_success = not bool(task_info.get("governance_violation", False))

    return evaluate_outcome(
        interaction_success=interaction_success,
        execution_success=execution_success,
        goal_success=goal_success,
        governance_success=governance_success,
        done_criteria_met=done_criteria,
        constraint_check_passed=constraint_ok,
        validation_check_passed=validation_ok,
    )


def generate_summary(task_id: str, task_info: dict, result: Any, error: Optional[str], user_feedback: Optional[str]) -> dict:
    metrics = {
        "task_type": task_info.get("task_type", "unknown"),
        "task_risk_level": task_info.get("task_risk_level") or task_info.get("risk_level", "unknown"),
        "complexity": task_info.get("complexity_level", "unknown"),
        "file_operations": task_info.get("file_write_flag", False),
        "tools_used": task_info.get("requires_tools", []),
    }

    outcome_fields = _extract_checks(task_info, result, error)

    return {
        "task_id": task_id,
        "error_message": error,
        "user_feedback": user_feedback,
        "metrics": metrics,
        "result_summary": str(result)[:500] if result else None,
        "schema_version": "v1",
        "policy_version": "v1",
        "created_at": datetime.now().isoformat(),
        **outcome_fields,
    }


def update_episodic_memory(task_id: str, summary: dict):
    log_dir = WORKSPACE / "memory" / "tasks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    entry = {
        "task_id": task_id,
        "task_type": summary.get("metrics", {}).get("task_type"),
        "overall_outcome": summary.get("overall_outcome"),
        "task_risk_level": summary.get("metrics", {}).get("task_risk_level"),
        "interaction_success": summary.get("interaction_success"),
        "execution_success": summary.get("execution_success"),
        "goal_success": summary.get("goal_success"),
        "governance_success": summary.get("governance_success"),
        "timestamp": summary.get("created_at"),
        "error": summary.get("error_message"),
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_for_proposals(task_info: dict, result: Any, error: Optional[str]) -> list:
    proposals = []
    if error:
        proposals.append({
            "type": "improvement",
            "category": "error_pattern",
            "description": f"Task type {task_info.get('task_type')} had error: {error[:100]}",
            "task_id": task_info.get("task_id"),
            "confidence": 0.6,
        })
    return proposals


def log_task_outcome(task_id: str, summary: dict):
    log_dir = WORKSPACE / "memory" / "tasks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    if not log_file.exists():
        return
    entries = []
    with open(log_file, "r") as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("task_id") == task_id:
                entry.update({
                    "overall_outcome": summary.get("overall_outcome"),
                    "created_at": summary.get("created_at"),
                    "error": summary.get("error_message"),
                })
            entries.append(entry)
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cleanup_working_memory(task_id: str):
    memory_dir = WORKSPACE / "memory" / "working"
    memory_file = memory_dir / f"{task_id}.json"
    if memory_file.exists():
        archive_dir = memory_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.move(str(memory_file), str(archive_dir / f"{task_id}.json"))
