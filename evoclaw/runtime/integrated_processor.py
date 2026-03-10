#!/usr/bin/env python3
"""
Integrated Message Processor with Experience Logging
"""

import sys
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
import json

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

from components.task_engine import analyze_task
from components.rule_engine import get_rule_engine
from components.experience_recall import get_experience_recall
from components.planner import get_decomposer
from components.skill_router import get_router
from components.config_center import get_config



def process_message(message: str, context: dict = None) -> dict:
    """Process message with full pipeline and experience logging"""
    if message is None or not str(message).strip():
        raise ValueError("message must not be empty")
    
    print(f"\n{'='*50}")
    print(f"🐲 Processing: {message[:30]}...")
    print('='*50)
    
    context = context or {}
    
    # === 1. Task Understanding ===
    print("\n[1] 📋 Understanding...")
    task = analyze_task(message)
    task_id = task['task_id']
    print(f"    Type: {task['task_type']}, Risk: {task['risk_level']}")
    
    # === 2. Experience Recall (BEFORE) ===
    print("\n[2] 🧠 Recall Experience...")
    recaller = get_experience_recall()
    recalled = recaller.recall(message)
    print(f"    Found: {len(recalled)} relevant experiences")
    
    # === 3. Rule Injection ===
    print("\n[3] 📜 Load Rules...")
    rule_engine = get_rule_engine()
    rules = rule_engine.get_rules_for_task(
        task['task_type'], 
        task['risk_level'], 
        task.get('scenario', '')
    )
    print(f"    Loaded: {sum(len(v) for v in rules.values())} rules")
    
    # === 4. Task Decomposition ===
    print("\n[4] 🎯 Decompose...")
    decomposer = get_decomposer()
    plan = decomposer.decompose(
        task['task_type'],
        task['complexity_level'],
        {"task_id": task_id}
    )
    print(f"    Subtasks: {plan['total_subtasks']}")
    
    # === 5. Skill Routing ===
    print("\n[5] 🛤️ Route Skill...")
    router = get_router()
    routing = router.route(task)
    print(f"    Skill: {routing['skill_name']} ({routing['routing_score']:.2f})")
    
    # === 6. Execute (simulated) ===
    print("\n[6] ⚡ Execute...")
    success = True
    result_msg = f"Completed with {routing['skill_name']}"
    print(f"    Result: {result_msg}")
    
    # === 7. Record Experience (AFTER) ===
    print("\n[7] 💾 Record Experience...")
    record_experience(
        task_id=task_id,
        message=message,
        task=task,
        routing=routing,
        success=success,
        recalled_count=len(recalled)
    )
    print("    ✓ Recorded")
    
    print(f"\n{'='*50}")
    print(f"✅ Done: {task_id}")
    print('='*50)
    
    return {
        "task_id": task_id,
        "task": task,
        "routing": routing,
        "result": result_msg,
        "success": success
    }


def record_experience(task_id: str, message: str, task: dict, routing: dict, success: bool, recalled_count: int):
    """Record task execution as experience"""
    
    # Determine significance
    if task['risk_level'] in ['high', 'critical'] or not success:
        significance = "pivotal"
    elif recalled_count > 0:
        significance = "notable"
    else:
        significance = "routine"
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "message": message[:100],
        "task_type": task['task_type'],
        "risk_level": task['risk_level'],
        "skill_used": routing.get('skill_name', 'unknown'),
        "routing_score": routing.get('routing_score', 0),
        "success": success,
        "significance": significance,
        "recalled_experiences": recalled_count,
        "outcome": "success" if success else "failed"
    }
    
    # Write to experiences
    date_str = datetime.now().strftime("%Y-%m-%d")
    exp_file = WORKSPACE / "memory" / "experiences" / f"{date_str}.jsonl"
    exp_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(exp_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # If notable/pivotal, also write to significant
    if significance in ["notable", "pivotal"]:
        sig_file = WORKSPACE / "memory" / "significant" / "significant.jsonl"
        sig_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(sig_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    tests = [
        "今天天气怎么样",
        "搜索科技新闻",
        "帮我写个函数"
    ]
    
    for msg in tests:
        process_message(msg)
