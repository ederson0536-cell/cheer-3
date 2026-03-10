#!/usr/bin/env python3
"""
before_subtask Hook
执行时机：子任务执行前
功能：拉取子任务规则、局部经验、技能路由
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from components.skill_router import route_task
from components.skill_registry import get_registry
from components.file_governance import get_file_governance

WORKSPACE = str(resolve_workspace(__file__))

def run_before_subtask(
    parent_task_id: str,
    subtask_info: dict,
    task_info: dict
) -> dict:
    """
    Main before_subtask hook
    Returns: skill recommendation + local rules + checklist
    """
    
    subtask_id = subtask_info.get("subtask_id", f"st_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    print(f"[before_subtask] Analyzing subtask: {subtask_id}")
    
    # 1. Route to best skill
    routing_result = route_task(task_info, subtask_info)
    
    # 2. Load subtask-specific rules
    rules = load_subtask_rules(subtask_info.get("subtask_type"))
    
    # 3. Retrieve local experience
    local_experience = recall_local_experience(subtask_info)
    
    # 4. Generate subtask checklist
    # 4.5 Week5 file catalog precheck
    governor = get_file_governance()
    local_scope = subtask_info.get("file_scope") or task_info.get("file_scope") or []
    if isinstance(local_scope, str):
        local_scope = [local_scope]
    catalog_precheck = governor.catalog_precheck(file_scope=local_scope, mode="auto")

    checklist = generate_subtask_checklist(subtask_info, routing_result)
    
    result = {
        "hook": "before_subtask",
        "timestamp": datetime.now().isoformat(),
        "parent_task_id": parent_task_id,
        "subtask": subtask_info,
        "routing": routing_result,
        "rules": rules,
        "local_experience": local_experience,
        "checklist": checklist,
        "file_governance": {"catalog_precheck": catalog_precheck},
        "ready_to_execute": routing_result.get("ready_to_execute", True) and bool(catalog_precheck.get("pass", True))
    }
    
    # Save to working memory
    save_subtask_working(parent_task_id, subtask_id, result)
    
    # Log subtask start
    log_subtask_event(parent_task_id, subtask_id, "started", subtask_info)
    
    print(f"[before_subtask] Subtask {subtask_id} routed to {routing_result['skill_name']} (score: {routing_result['routing_score']})")
    
    return result


def load_subtask_rules(subtask_type: str) -> dict:
    """Load rules specific to subtask type"""
    
    rules = {
        "hard_rules": [],
        "local_rules": [],
        "guidelines": []
    }
    
    # Universal file operation rules
    rules["hard_rules"].extend([
        "verify_path_before_write",
        "backup_before_modify"
    ])
    
    # Type-specific rules
    type_rules = {
        "fetch": ["verify_source_reliability", "cache_results"],
        "edit_file": ["preserve_original", "test_after_change"],
        "write_output": ["verify_format", "check_permissions"],
        "analyze": ["cite_sources", "avoid_hallucination"],
        "run_validation": ["check_prerequisites", "log_output"],
        "coordinate": ["check_dependencies", "handle_failures"]
    }
    
    rules["local_rules"] = type_rules.get(subtask_type, [])
    
    return rules


def recall_local_experience(subtask_info: dict) -> dict:
    """Recall relevant experience for this subtask type"""
    
    subtask_type = subtask_info.get("subtask_type", "")
    local_scenario = subtask_info.get("local_scenario", "")
    
    experience_path = Path(WORKSPACE) / "memory" / "subtasks"
    
    recent = []
    
    if experience_path.exists():
        files = sorted(experience_path.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        
        for f in files:
            try:
                with open(f) as fp:
                    for line in fp:
                        exp = json.loads(line)
                        if exp.get("subtask_type") == subtask_type:
                            recent.append({
                                "subtask_id": exp.get("subtask_id"),
                                "outcome": exp.get("outcome"),
                                "error": exp.get("error")
                            })
            except:
                pass
    
    return {
        "similar_subtasks": recent[:3],
        "total_found": len(recent)
    }


def generate_subtask_checklist(subtask_info: dict, routing_result: dict) -> list:
    """Generate checklist for subtask execution"""
    
    checklist = []
    subtask_type = subtask_info.get("subtask_type", "")
    
    # Universal
    checklist.append({
        "item": f"Execute subtask: {subtask_type}",
        "done": False,
        "required": True
    })
    
    # Skill-specific
    skill_id = routing_result.get("skill_id")
    if skill_id:
        checklist.append({
            "item": f"Using skill: {routing_result.get('skill_name')}",
            "done": False,
            "required": True
        })
    
    # Type-specific items
    if subtask_type == "fetch":
        checklist.append({"item": "Verify data source", "done": False, "required": True})
    
    if subtask_type == "edit_file":
        checklist.append({"item": "Backup original file", "done": False, "required": False})
        checklist.append({"item": "Verify syntax after edit", "done": False, "required": True})
    
    if subtask_type == "write_output":
        checklist.append({"item": "Verify output format", "done": False, "required": True})
    
    # Post-execution
    checklist.append({
        "item": "Verify done_criteria met",
        "done": False,
        "required": True
    })
    
    return checklist


def save_subtask_working(parent_id: str, subtask_id: str, data: dict):
    """Save subtask working data"""
    
    dir_path = Path(WORKSPACE) / "memory" / "working" / "subtasks"
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{subtask_id}.json"
    
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_subtask_event(parent_id: str, subtask_id: str, event: str, data: dict):
    """Log subtask event"""
    
    dir_path = Path(WORKSPACE) / "memory" / "subtasks"
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    entry = {
        "parent_task_id": parent_id,
        "subtask_id": subtask_id,
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "subtask_type": data.get("subtask_type"),
        "goal": data.get("goal")
    }
    
    with open(file_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # Test
    task_info = {
        "task_type": "research",
        "scenario": "news_summary",
        "risk_level": "low"
    }
    
    subtask_info = {
        "subtask_id": "st_001",
        "parent_task_id": "t_test_001",
        "subtask_type": "fetch",
        "goal": "Fetch news from web"
    }
    
    result = run_before_subtask("t_test_001", subtask_info, task_info)
    print(json.dumps(result, indent=2, ensure_ascii=False))
