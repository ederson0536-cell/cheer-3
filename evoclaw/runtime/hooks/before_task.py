#!/usr/bin/env python3
"""
Enhanced before_task Hook - 完整版
执行时机：收到任务后、执行前
功能：任务理解、规则注入(完整)、经验检索(完整)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = str(resolve_workspace(__file__))
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.task_engine import analyze_task
from components.memory_retrieval import get_memory_retrieval
from components.file_governance import get_file_governance


def run_before_task(message: str, context: dict = None) -> dict:
    """
    完整版 before_task hook
    1. 任务理解
    2. 规则注入
    3. 经验检索
    4. 生成上下文
    """
    
    print(f"\n[before_task] 分析任务: {message[:50]}...")
    
    # 1. 任务理解
    task_understanding = analyze_task(message, context)
    
    # 2-3. 统一记忆检索（规则 + 经验）
    memory_retrieval = get_memory_retrieval()
    retrieval = memory_retrieval.retrieve(
        message=message,
        task_understanding=task_understanding,
        recent_days=7,
    )

    # 3.5 file catalog precheck (Week5)
    governor = get_file_governance()
    file_scope = task_understanding.get("file_scope") or []
    if isinstance(file_scope, str):
        file_scope = [file_scope]
    catalog_precheck = governor.catalog_precheck(file_scope=file_scope, mode="auto")

    # 4. 兼容旧字段
    rules = retrieval["rules_track"]["rules"]
    experience = retrieval["experience_track"]["episodic"]
    context_summary = retrieval.get("context_summary", "")
    rule_description = (
        f"P0:{len(rules.get('P0_HARD', []))} "
        f"P1:{len(rules.get('P1_GOVERNANCE', []))} "
        f"P2:{len(rules.get('P2_TASK_TYPE', []))} "
        f"P3:{len(rules.get('P3_SCENARIO', []))}"
    )

    # 规则约束提取：支持动态 rules 的 action=block/deny 或 constraints 中的 block/deny
    all_rule_rows = []
    for bucket in ("P0_HARD", "P1_GOVERNANCE", "P2_TASK_TYPE", "P3_SCENARIO", "P4_SUGGESTION"):
        all_rule_rows.extend(rules.get(bucket, []))

    blocking_rules = []
    for rule in all_rule_rows:
        action = str(rule.get("action") or "").lower()
        if action in {"block", "deny", "forbid"}:
            blocking_rules.append(rule)
            continue
        constraints = rule.get("constraints")
        if isinstance(constraints, list):
            for item in constraints:
                if isinstance(item, dict):
                    c_action = str(item.get("action") or "").lower()
                    if c_action in {"block", "deny", "forbid"}:
                        blocking_rules.append(rule)
                        break
    
    # 构建完整输出
    result = {
        "hook": "before_task",
        "timestamp": datetime.now().isoformat(),
        "task": task_understanding,
        "memory_retrieval": retrieval,
        "rules": rules,
        "rule_constraints": {
            "blocking_rules": blocking_rules,
            "blocking_count": len(blocking_rules),
        },
        "rule_description": rule_description,
        "experience": experience,
        "context_summary": context_summary,
        "file_governance": {"catalog_precheck": catalog_precheck},
        "ready_to_execute": (
            task_understanding["uncertainty_level"] < 0.7
            and len(blocking_rules) == 0
            and bool(catalog_precheck.get("pass", True))
        ),
    }
    
    # 保存工作内存
    save_working_memory(task_understanding["task_id"], result)
    
    # 记录任务开始
    log_task_start(task_understanding["task_id"], task_understanding)
    
    # 打印摘要
    print(f"\n[before_task] 📋 {task_understanding['task_type']} | 风险:{task_understanding['risk_level']}")
    print(
        "[before_task] 🔒 规则数: "
        f"{len(rules.get('P0_HARD', []))}条硬规则, "
        f"{len(rules.get('P2_TASK_TYPE', []))}条任务规则"
    )
    if blocking_rules:
        print(f"[before_task] ⛔ 阻断规则: {len(blocking_rules)} 条")
    print(f"[before_task] 📊 置信度: {experience.get('confidence', 0):.0%}")
    print(f"[before_task] 💡 经验: {len(experience.get('similar_tasks', []))}个相似任务")
    
    return result


def save_working_memory(task_id: str, data: dict):
    """保存工作内存"""
    
    memory_dir = Path(WORKSPACE) / "memory" / "working"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    memory_file = memory_dir / f"{task_id}.json"
    
    with open(memory_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_task_start(task_id: str, task_info: dict):
    """记录任务开始"""
    
    log_dir = Path(WORKSPACE) / "memory" / "tasks"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    entry = {
        "task_id": task_id,
        "event": "started",
        "timestamp": datetime.now().isoformat(),
        "task_type": task_info.get("task_type"),
        "scenario": task_info.get("scenario"),
        "risk_level": task_info.get("risk_level"),
        "tags": task_info.get("tags", []),
        "uncertainty": task_info.get("uncertainty_level")
    }
    
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # Test
    test_msg = "帮我搜索今天的科技新闻"
    result = run_before_task(test_msg)
    
    print("\n=== Task Analysis ===")
    print(f"Type: {result['task']['task_type']}")
    print(f"Risk: {result['task']['risk_level']}")
    print(f"Tags: {result['task']['tags']}")
    
    print("\n=== Rules ===")
    print(result['rule_description'])
    
    print("\n=== Experience ===")
    print(result['context_summary'])
