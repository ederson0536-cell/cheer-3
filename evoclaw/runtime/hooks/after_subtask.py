#!/usr/bin/env python3
"""
after_subtask Hook
执行时机：子任务完成后
功能：记录技能选择、成功率、更新技能表现
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from components.skill_registry import get_registry

WORKSPACE = str(resolve_workspace(__file__))

def run_after_subtask(
    parent_task_id: str,
    subtask_id: str,
    subtask_info: dict,
    routing_info: dict,
    result: Any,
    error: Optional[str] = None,
    latency_ms: float = 0
) -> dict:
    """
    Main after_subtask hook
    Returns: subtask summary + proposal queue items
    """
    
    print(f"[after_subtask] Completing subtask: {subtask_id}")
    
    # 1. Determine outcome
    outcome = "success" if not error else "failed"
    
    # 2. Determine if rework needed
    rework = error is not None or (isinstance(result, dict) and result.get("needs_retry"))
    
    # 3. Update skill performance
    skill_id = routing_info.get("skill_id")
    if skill_id:
        registry = get_registry()
        registry.update_performance(skill_id, not rework, latency_ms, rework)
    
    # 4. Generate summary
    summary = generate_subtask_summary(
        parent_task_id, subtask_id, subtask_info, 
        routing_info, result, error, latency_ms
    )
    
    # 5. Update episodic memory
    update_subtask_memory(subtask_id, summary)
    
    # 6. Check for proposals
    proposals = check_subtask_proposals(subtask_info, error)
    
    # 7. Cleanup
    cleanup_subtask_working(subtask_id)
    
    result_output = {
        "hook": "after_subtask",
        "timestamp": datetime.now().isoformat(),
        "parent_task_id": parent_task_id,
        "subtask_id": subtask_id,
        "summary": summary,
        "proposals": proposals,
        "success": error is None
    }
    
    print(f"[after_subtask] Subtask {subtask_id} completed - success: {error is None}")
    
    return result_output


def generate_subtask_summary(
    parent_task_id: str,
    subtask_id: str,
    subtask_info: dict,
    routing_info: dict,
    result: Any,
    error: Optional[str],
    latency_ms: float
) -> dict:
    """Generate subtask summary"""
    
    return {
        "subtask_id": subtask_id,
        "parent_task_id": parent_task_id,
        "subtask_type": subtask_info.get("subtask_type"),
        "goal": subtask_info.get("goal"),
        "skill_selected": routing_info.get("skill_id"),
        "skill_name": routing_info.get("skill_name"),
        "routing_score": routing_info.get("routing_score"),
        "outcome": "success" if not error else "failed",
        "error_message": error,
        "latency_ms": latency_ms,
        "done_criteria_met": subtask_info.get("done_criteria", []),
        "completed_at": datetime.now().isoformat(),
        "alternatives_considered": routing_info.get("alternatives", [])
    }


def update_subtask_memory(subtask_id: str, summary: dict):
    """Update episodic memory with subtask experience"""
    
    dir_path = Path(WORKSPACE) / "memory" / "subtasks"
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    # Update existing entry or create new
    entries = []
    if file_path.exists():
        with open(file_path, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("subtask_id") == subtask_id:
                    # Update with outcome
                    entry["outcome"] = summary.get("outcome")
                    entry["skill_selected"] = summary.get("skill_selected")
                    entry["error"] = summary.get("error_message")
                    entry["latency_ms"] = summary.get("latency_ms")
                    entry["completed_at"] = summary.get("completed_at")
                entries.append(entry)
    
    # If not found, append new
    if not any(e.get("subtask_id") == subtask_id for e in entries):
        entries.append({
            "subtask_id": subtask_id,
            "parent_task_id": summary.get("parent_task_id"),
            "subtask_type": summary.get("subtask_type"),
            "outcome": summary.get("outcome"),
            "skill_selected": summary.get("skill_selected"),
            "error": summary.get("error_message"),
            "timestamp": summary.get("completed_at")
        })
    
    with open(file_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_subtask_proposals(subtask_info: dict, error: Optional[str]) -> list:
    """Check if subtask generates any proposals"""
    
    proposals = []
    
    if error:
        proposals.append({
            "type": "skill_improvement",
            "category": "subtask_error",
            "description": f"Subtask {subtask_info.get('subtask_type')} failed: {error[:50]}",
            "skill_id": subtask_info.get("skill_id"),
            "confidence": 0.7
        })
    
    # Check for repeated failures
    # In real implementation, check recent failure patterns
    
    return proposals


def cleanup_subtask_working(subtask_id: str):
    """Clean up subtask working memory"""
    
    dir_path = Path(WORKSPACE) / "memory" / "working" / "subtasks"
    file_path = dir_path / f"{subtask_id}.json"
    
    if file_path.exists():
        # Archive instead of delete
        archive_dir = dir_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        import shutil
        shutil.move(str(file_path), str(archive_dir / f"{subtask_id}.json"))


if __name__ == "__main__":
    # Test
    subtask_info = {
        "subtask_id": "st_test_001",
        "parent_task_id": "t_test_001",
        "subtask_type": "fetch",
        "goal": "Fetch news data"
    }
    
    routing_info = {
        "skill_id": "web_fetch_skill",
        "skill_name": "Web Fetch",
        "routing_score": 0.85
    }
    
    result = run_after_subtask(
        parent_task_id="t_test_001",
        subtask_id="st_test_001",
        subtask_info=subtask_info,
        routing_info=routing_info,
        result={"data": "fetched"},
        error=None,
        latency_ms=2500
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
