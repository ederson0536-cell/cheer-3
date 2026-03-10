#!/usr/bin/env python3
"""
Skill Performance Store - 技能表现存储
追踪每个技能的成功率、延迟、返工率等指标
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

WORKSPACE = resolve_workspace(__file__)
PERF_DIR = WORKSPACE / "memory" / "skill_performance"


class SkillPerformanceStore:
    """技能表现存储"""
    
    def __init__(self):
        PERF_DIR.mkdir(parents=True, exist_ok=True)
        self.perf_file = PERF_DIR / "performance.jsonl"
        
        # 初始化文件
        if not self.perf_file.exists():
            self.perf_file.touch()
    
    def record(
        self,
        skill_id: str,
        task_type: str,
        success: bool,
        latency_ms: float,
        rework: bool = False,
        error: str = None
    ):
        """记录技能执行"""
        
        entry = {
            "skill_id": skill_id,
            "task_type": task_type,
            "success": success,
            "latency_ms": latency_ms,
            "rework": rework,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.perf_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return entry
    
    def get_skill_stats(self, skill_id: str, days: int = 30) -> Dict:
        """获取技能统计"""
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        stats = {
            "skill_id": skill_id,
            "total_executions": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0,
            "rework_rate": 0.0,
            "error_types": {},
            "by_task_type": {}
        }
        
        if not self.perf_file.exists():
            return stats
        
        latencies = []
        rewrites = 0
        by_type = defaultdict(lambda: {"total": 0, "success": 0})
        
        with open(self.perf_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    if entry.get("skill_id") != skill_id:
                        continue
                    
                    if entry.get("timestamp", "") < cutoff:
                        continue
                    
                    stats["total_executions"] += 1
                    
                    if entry.get("success"):
                        stats["successes"] += 1
                    else:
                        stats["failures"] += 1
                    
                    # 延迟
                    latencies.append(entry.get("latency_ms", 0))
                    
                    # 返工
                    if entry.get("rework"):
                        rewrites += 1
                    
                    # 错误类型
                    error = entry.get("error")
                    if error:
                        error_type = error[:50]  # 取前50字符
                        stats["error_types"][error_type] = stats["error_types"].get(error_type, 0) + 1
                    
                    # 按任务类型
                    task_type = entry.get("task_type", "unknown")
                    by_type[task_type]["total"] += 1
                    if entry.get("success"):
                        by_type[task_type]["success"] += 1
                        
                except:
                    continue
        
        # 计算指标
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successes"] / stats["total_executions"]
            stats["rework_rate"] = rewrites / stats["total_executions"]
        
        if latencies:
            stats["avg_latency_ms"] = sum(latencies) / len(latencies)
        
        # 按任务类型
        for task_type, data in by_type.items():
            if data["total"] > 0:
                stats["by_task_type"][task_type] = {
                    "total": data["total"],
                    "success_rate": data["success"] / data["total"]
                }
        
        return stats
    
    def get_all_skills_stats(self, days: int = 30) -> Dict:
        """获取所有技能统计"""
        
        skills = defaultdict(lambda: {
            "total": 0, "success": 0, "latencies": []
        })
        
        if not self.perf_file.exists():
            return {}
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with open(self.perf_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    if entry.get("timestamp", "") < cutoff:
                        continue
                    
                    skill_id = entry.get("skill_id")
                    skills[skill_id]["total"] += 1
                    
                    if entry.get("success"):
                        skills[skill_id]["success"] += 1
                    
                    skills[skill_id]["latencies"].append(entry.get("latency_ms", 0))
                        
                except:
                    continue
        
        # 计算
        result = {}
        for skill_id, data in skills.items():
            result[skill_id] = {
                "total_executions": data["total"],
                "successes": data["success"],
                "success_rate": data["success"] / data["total"] if data["total"] > 0 else 0,
                "avg_latency_ms": sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0
            }
        
        return result
    
    def get_best_skill(self, task_type: str, days: int = 30) -> Optional[Dict]:
        """获取最佳技能"""
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        skills = defaultdict(lambda: {"total": 0, "success": 0})
        
        if not self.perf_file.exists():
            return None
        
        with open(self.perf_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    if entry.get("timestamp", "") < cutoff:
                        continue
                    
                    if entry.get("task_type") != task_type:
                        continue
                    
                    skill_id = entry.get("skill_id")
                    skills[skill_id]["total"] += 1
                    
                    if entry.get("success"):
                        skills[skill_id]["success"] += 1
                        
                except:
                    continue
        
        # 找最佳
        best = None
        best_rate = -1
        
        for skill_id, data in skills.items():
            if data["total"] < 3:  # 至少3次执行
                continue
            
            rate = data["success"] / data["total"]
            if rate > best_rate:
                best_rate = rate
                best = {
                    "skill_id": skill_id,
                    "success_rate": rate,
                    "total_executions": data["total"]
                }
        
        return best
    
    def get_recommendations(self) -> List[Dict]:
        """获取改进建议"""
        
        recommendations = []
        
        # 获取所有技能统计
        all_stats = self.get_all_skills_stats()
        
        for skill_id, stats in all_stats.items():
            # 检查成功率
            if stats["success_rate"] < 0.7:
                recommendations.append({
                    "skill_id": skill_id,
                    "issue": "low_success_rate",
                    "current": f"{stats['success_rate']:.0%}",
                    "suggestion": f"技能 {skill_id} 成功率较低，考虑改进或培训"
                })
            
            # 检查延迟
            if stats["avg_latency_ms"] > 10000:  # 10秒
                recommendations.append({
                    "skill_id": skill_id,
                    "issue": "high_latency",
                    "current": f"{stats['avg_latency_ms']/1000:.1f}s",
                    "suggestion": f"技能 {skill_id} 执行时间过长，考虑优化"
                })
            
            # 检查使用频率
            if stats["total_executions"] > 50 and stats["success_rate"] < 0.85:
                recommendations.append({
                    "skill_id": skill_id,
                    "issue": "frequent_use_low_success",
                    "current": f"使用{stats['total_executions']}次, 成功率{stats['success_rate']:.0%}",
                    "suggestion": f"高频使用技能需要提高成功率"
                })
        
        return recommendations


# 全局实例
_perf_store = None

def get_performance_store() -> SkillPerformanceStore:
    global _perf_store
    if _perf_store is None:
        _perf_store = SkillPerformanceStore()
    return _perf_store


if __name__ == "__main__":
    store = get_performance_store()
    
    # Test
    store.record("web_fetch_skill", "research", True, 2500)
    store.record("web_fetch_skill", "research", True, 3000)
    store.record("weather_skill", "information", True, 1500)
    
    print("All skills:")
    print(json.dumps(store.get_all_skills_stats(), indent=2))
    
    print("\nBest for research:")
    print(store.get_best_skill("research"))
    
    print("\nRecommendations:")
    print(store.get_recommendations())
