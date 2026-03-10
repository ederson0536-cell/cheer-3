#!/usr/bin/env python3
"""after_subtask Hook - Week3 outcome-gated summary."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from evoclaw.workspace_resolver import resolve_workspace

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from components.skill_registry import get_registry
from evoclaw.runtime.outcome_evaluator import evaluate_outcome

WORKSPACE = str(resolve_workspace(__file__))


def run_after_subtask(
    parent_task_id: str,
    subtask_id: str,
    subtask_info: dict,
    routing_info: dict,
    result: Any,
    error: Optional[str] = None,
    latency_ms: float = 0,
) -> dict:
    print(f"[after_subtask] Completing subtask: {subtask_id}")

    rework = error is not None or (isinstance(result, dict) and result.get("needs_retry"))

    skill_id = routing_info.get("skill_id")
    if skill_id:
        registry = get_registry()
        registry.update_performance(skill_id, not rework, latency_ms, rework)

    summary = generate_subtask_summary(parent_task_id, subtask_id, subtask_info, routing_info, result, error, latency_ms)
    update_subtask_memory(subtask_id, summary)
    proposals = check_subtask_proposals(subtask_info, error)
    cleanup_subtask_working(subtask_id)

    return {
        "hook": "after_subtask",
        "timestamp": datetime.now().isoformat(),
        "parent_task_id": parent_task_id,
        "subtask_id": subtask_id,
        "summary": summary,
        "proposals": proposals,
        "success": summary["overall_outcome"] == "success",
    }


def _subtask_outcome(subtask_info: dict, result: Any, error: Optional[str]) -> dict:
    done_criteria_met = bool(subtask_info.get("done_criteria"))
    constraint_check_passed = not bool(error) and not bool(subtask_info.get("policy_conflict", False))
    validation_check_passed = True
    if isinstance(result, dict):
        validation_check_passed = bool(result.get("validation_check_passed", True))
    if error:
        validation_check_passed = False

    return evaluate_outcome(
        interaction_success=True,
        execution_success=not bool(error),
        goal_success=not bool(error),
        governance_success=not bool(subtask_info.get("governance_violation", False)),
        done_criteria_met=done_criteria_met,
        constraint_check_passed=constraint_check_passed,
        validation_check_passed=validation_check_passed,
    )


def generate_subtask_summary(
    parent_task_id: str,
    subtask_id: str,
    subtask_info: dict,
    routing_info: dict,
    result: Any,
    error: Optional[str],
    latency_ms: float,
) -> dict:
    outcome = _subtask_outcome(subtask_info, result, error)
    return {
        "subtask_id": subtask_id,
        "parent_task_id": parent_task_id,
        "subtask_type": subtask_info.get("subtask_type"),
        "goal": subtask_info.get("goal"),
        "skill_selected": routing_info.get("skill_id"),
        "skill_name": routing_info.get("skill_name"),
        "routing_score": routing_info.get("routing_score"),
        "error_message": error,
        "latency_ms": latency_ms,
        "schema_version": "v1",
        "policy_version": "v1",
        "created_at": datetime.now().isoformat(),
        **outcome,
    }


def update_subtask_memory(subtask_id: str, summary: dict):
    dir_path = Path(WORKSPACE) / "memory" / "subtasks"
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    entries = []
    if file_path.exists():
        with open(file_path, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("subtask_id") == subtask_id:
                    entry.update({
                        "overall_outcome": summary.get("overall_outcome"),
                        "skill_selected": summary.get("skill_selected"),
                        "error": summary.get("error_message"),
                        "latency_ms": summary.get("latency_ms"),
                        "updated_at": summary.get("created_at"),
                    })
                entries.append(entry)

    if not any(e.get("subtask_id") == subtask_id for e in entries):
        entries.append({
            "subtask_id": subtask_id,
            "parent_task_id": summary.get("parent_task_id"),
            "subtask_type": summary.get("subtask_type"),
            "overall_outcome": summary.get("overall_outcome"),
            "skill_selected": summary.get("skill_selected"),
            "error": summary.get("error_message"),
            "timestamp": summary.get("created_at"),
        })

    with open(file_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_subtask_proposals(subtask_info: dict, error: Optional[str]) -> list:
    proposals = []
    if error:
        proposals.append({
            "type": "skill_improvement",
            "category": "subtask_error",
            "description": f"Subtask {subtask_info.get('subtask_type')} failed: {error[:50]}",
            "skill_id": subtask_info.get("skill_id"),
            "confidence": 0.7,
        })
    return proposals


def cleanup_subtask_working(subtask_id: str):
    dir_path = Path(WORKSPACE) / "memory" / "working" / "subtasks"
    file_path = dir_path / f"{subtask_id}.json"
    if file_path.exists():
        archive_dir = dir_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.move(str(file_path), str(archive_dir / f"{subtask_id}.json"))
