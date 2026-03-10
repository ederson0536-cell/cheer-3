#!/usr/bin/env python3
"""
Decision WAL - 决策日志
记录每个决策的详细信息，用于审计和回溯
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List, Any
from enum import Enum

WORKSPACE = resolve_workspace(__file__)
WAL_DIR = WORKSPACE / "memory" / "wal"


class DecisionType(Enum):
    """决策类型"""
    TASK_UNDERSTANDING = "task_understanding"
    RULE_INJECTION = "rule_injection"
    EXPERIENCE_RECALL = "experience_recall"
    TASK_DECOMPOSITION = "task_decomposition"
    SKILL_ROUTING = "skill_routing"
    SUBTASK_START = "subtask_start"
    SUBTASK_COMPLETE = "subtask_complete"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    MANUAL_INTERVENTION = "manual_intervention"


class DecisionWAL:
    """决策日志"""
    
    def __init__(self):
        WAL_DIR.mkdir(parents=True, exist_ok=True)
        self.wal_file = WAL_DIR / f"{datetime.now().strftime('%Y-%m')}.jsonl"
    
    def log(
        self,
        decision_type: DecisionType,
        task_id: str,
        details: Dict,
        context: Dict = None,
        outcome: Any = None,
        error: str = None
    ) -> str:
        """
        记录决策
        """
        
        entry = {
            "id": f"wal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{task_id}",
            "timestamp": datetime.now().isoformat(),
            "decision_type": decision_type.value,
            "task_id": task_id,
            "details": details,
            "context": context or {},
            "outcome": outcome,
            "error": error
        }
        
        # 追加到WAL
        with open(self.wal_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return entry["id"]
    
    def get_task_decisions(self, task_id: str, limit: int = 100) -> List[Dict]:
        """获取任务的决策"""
        
        decisions = []
        
        if not self.wal_file.exists():
            return decisions
        
        with open(self.wal_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("task_id") == task_id:
                        decisions.append(entry)
                except:
                    continue
        
        return decisions[-limit:]
    
    def get_recent_decisions(self, limit: int = 50) -> List[Dict]:
        """获取最近的决策"""
        
        decisions = []
        
        if not self.wal_file.exists():
            return decisions
        
        with open(self.wal_file) as f:
            for line in f:
                try:
                    decisions.append(json.loads(line))
                except:
                    continue
        
        return decisions[-limit:]
    
    def search(
        self,
        decision_type: DecisionType = None,
        task_id: str = None,
        from_date: str = None,
        to_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """搜索决策"""
        
        results = []
        
        # 扫描当月WAL
        wal_file = WAL_DIR / f"{datetime.now().strftime('%Y-%m')}.jsonl"
        
        if not wal_file.exists():
            return results
        
        with open(wal_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    # 过滤条件
                    if decision_type and entry.get("decision_type") != decision_type.value:
                        continue
                    
                    if task_id and entry.get("task_id") != task_id:
                        continue
                    
                    if from_date and entry.get("timestamp") < from_date:
                        continue
                    
                    if to_date and entry.get("timestamp") > to_date:
                        continue
                    
                    results.append(entry)
                    
                except:
                    continue
        
        return results[-limit:]
    
    def get_statistics(self, days: int = 7) -> Dict:
        """获取统计信息"""
        
        from datetime import timedelta
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        stats = {
            "total_decisions": 0,
            "by_type": {},
            "success_rate": 0.0,
            "errors": 0
        }
        
        if not self.wal_file.exists():
            return stats
        
        successes = 0
        total = 0
        
        with open(self.wal_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    if entry.get("timestamp", "") < cutoff:
                        continue
                    
                    total += 1
                    
                    # 统计类型
                    dtype = entry.get("decision_type", "unknown")
                    stats["by_type"][dtype] = stats["by_type"].get(dtype, 0) + 1
                    
                    # 统计错误
                    if entry.get("error"):
                        stats["errors"] += 1
                    
                    # 统计成功
                    if entry.get("outcome"):
                        successes += 1
                        
                except:
                    continue
        
        stats["total_decisions"] = total
        stats["success_rate"] = successes / total if total > 0 else 0.0
        
        return stats


# 全局实例
_wal = None

def get_wal() -> DecisionWAL:
    global _wal
    if _wal is None:
        _wal = DecisionWAL()
    return _wal


if __name__ == "__main__":
    wal = get_wal()
    
    # Test
    wal.log(
        DecisionType.TASK_UNDERSTANDING,
        "t_001",
        {"task_type": "research", "confidence": 0.9}
    )
    
    print(f"Stats: {wal.get_statistics()}")
