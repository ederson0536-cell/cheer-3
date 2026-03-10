#!/usr/bin/env python3
"""
after_task Hook
执行时机：任务完成后
功能：汇总结果、更新记忆、生成提案
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Import feedback system
WORKSPACE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE))
try:
    from evoclaw.feedback_system import after_task as feedback_after_task
except Exception as import_err:
    print(f"[after_task] Feedback system import failed: {import_err}")
    feedback_after_task = None

WORKSPACE = str(WORKSPACE)

def run_after_task(
    task_id: str, 
    task_info: dict,
    result: Any,
    error: Optional[str] = None,
    user_feedback: Optional[str] = None
) -> dict:
    """
    Main after_task hook
    Returns: task summary + proposal queue items
    """
    
    print(f"[after_task] Completing task: {task_id}")
    
    # 1. Generate task summary
    summary = generate_summary(task_id, task_info, result, error, user_feedback)
    
    # 2. Update episodic memory
    update_episodic_memory(task_id, summary)
    
    # 3. Check for proposals
    proposals = check_for_proposals(task_info, result, error)
    
    # 4. Update task log with outcome
    log_task_outcome(task_id, summary)
    
    # 5. Cleanup working memory
    cleanup_working_memory(task_id)
    
    result = {
        "hook": "after_task",
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "summary": summary,
        "proposals": proposals,
        "success": error is None
    }
    
    print(f"[after_task] Task {task_id} completed - success:{error is None}")
    
    # Call feedback system after_task
    if feedback_after_task:
        try:
            feedback_task = {
                "name": task_id,
                "type": task_info.get("type", "unknown"),
                "source": "runtime_hook",
                "message": task_info.get("message", ""),
            }
            feedback_result = {
                "success": error is None,
                "summary": summary,
                "error": error,
            }
            feedback_after_task(feedback_task, feedback_result)
        except Exception as e:
            print(f"[after_task] Feedback system error: {e}")
    
    return result


def generate_summary(
    task_id: str, 
    task_info: dict,
    result: Any,
    error: Optional[str],
    user_feedback: Optional[str]
) -> dict:
    """Generate task summary"""
    
    # Determine outcome
    if error:
        outcome = "failed"
    elif user_feedback:
        # Check if feedback is positive or negative
        positive_words = ["好", "不错", "谢谢", "good", "great", "thanks", "perfect"]
        negative_words = ["不", "错", "不好", "bad", "wrong", "not"]
        
        if any(w in user_feedback.lower() for w in positive_words):
            outcome = "success_with_feedback_positive"
        elif any(w in user_feedback.lower() for w in negative_words):
            outcome = "failed_needs_retry"
        else:
            outcome = "success_with_feedback"
    else:
        outcome = "success"
    
    # Calculate duration (if we had start time)
    # For now, just mark completion
    
    # Extract key metrics
    metrics = {
        "task_type": task_info.get("task_type", "unknown"),
        "risk_level": task_info.get("risk_level", "unknown"),
        "complexity": task_info.get("complexity_level", "unknown"),
        "file_operations": task_info.get("file_write_flag", False),
        "tools_used": task_info.get("requires_tools", [])
    }
    
    # Result summary (truncate if too long)
    result_summary = str(result)[:500] if result else None
    
    return {
        "task_id": task_id,
        "outcome": outcome,
        "error_message": error,
        "user_feedback": user_feedback,
        "metrics": metrics,
        "result_summary": result_summary,
        "completed_at": datetime.now().isoformat()
    }


def update_episodic_memory(task_id: str, summary: dict):
    """Update episodic memory with task experience"""
    
    # This logs to the daily task log
    log_dir = Path(WORKSPACE) / "memory" / "tasks"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    # Add to episodic memory
    entry = {
        "task_id": task_id,
        "task_type": summary.get("metrics", {}).get("task_type"),
        "scenario": summary.get("scenario", "unknown"),
        "outcome": summary.get("outcome"),
        "risk_level": summary.get("metrics", {}).get("risk_level"),
        "tags": summary.get("tags", []),
        "timestamp": summary.get("completed_at"),
        "error": summary.get("error_message"),
        "feedback": summary.get("user_feedback")
    }
    
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_for_proposals(task_info: dict, result: Any, error: Optional[str]) -> list:
    """Check if task generates any proposals for evolution"""
    
    proposals = []
    
    # Proposal 1: Task pattern detected
    if error:
        proposals.append({
            "type": "improvement",
            "category": "error_pattern",
            "description": f"Task type {task_info.get('task_type')} had error: {error[:100]}",
            "task_id": task_info.get("task_id"),
            "confidence": 0.6
        })
    
    # Proposal 2: High uncertainty tasks
    uncertainty = task_info.get("uncertainty_level", 0)
    if uncertainty > 0.5:
        proposals.append({
            "type": "improvement",
            "category": "task_understanding",
            "description": f"High uncertainty ({uncertainty}) task - consider better prompting",
            "task_id": task_info.get("task_id"),
            "confidence": 0.5
        })
    
    # Proposal 3: New scenario encountered
    scenario = task_info.get("scenario", "")
    if scenario and "_general" in scenario:
        proposals.append({
            "type": "knowledge",
            "category": "scenario_discovery",
            "description": f"New scenario pattern: {scenario}",
            "task_id": task_info.get("task_id"),
            "confidence": 0.4
        })
    
    return proposals


def log_task_outcome(task_id: str, summary: dict):
    """Log final task outcome"""
    
    log_dir = Path(WORKSPACE) / "memory" / "tasks"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Update the existing entry with outcome
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    # Read existing entries and update
    entries = []
    if log_file.exists():
        with open(log_file, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("task_id") == task_id:
                    entry["outcome"] = summary.get("outcome")
                    entry["completed_at"] = summary.get("completed_at")
                    if summary.get("error_message"):
                        entry["error"] = summary.get("error_message")
                entries.append(entry)
    
    # Rewrite file
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cleanup_working_memory(task_id: str):
    """Clean up working memory for this task"""
    
    memory_dir = Path(WORKSPACE) / "memory" / "working"
    memory_file = memory_dir / f"{task_id}.json"
    
    if memory_file.exists():
        # Optionally archive instead of delete
        archive_dir = memory_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Move to archive
        import shutil
        shutil.move(str(memory_file), str(archive_dir / f"{task_id}.json"))


if __name__ == "__main__":
    # Test
    task_info = {
        "task_id": "t_test_001",
        "task_type": "research",
        "scenario": "news_summary",
        "risk_level": "medium",
        "complexity_level": "L1",
        "uncertainty_level": 0.3
    }
    
    result = run_after_task(
        task_id="t_test_001",
        task_info=task_info,
        result={"status": "completed", "items": 5},
        error=None
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
