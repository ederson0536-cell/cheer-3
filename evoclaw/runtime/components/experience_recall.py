#!/usr/bin/env python3
"""
Experience Recall - 从记忆系统检索相关经验
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import re

WORKSPACE = resolve_workspace(__file__)


class ExperienceRecall:
    """经验召回 - 从记忆系统检索相关经验"""
    
    def __init__(self):
        self.tasks_dir = Path(WORKSPACE) / "memory" / "tasks"
        self.proposals_dir = Path(WORKSPACE) / "memory" / "proposals"
        self.candidates_dir = Path(WORKSPACE) / "memory" / "candidate"
    
    def recall(
        self,
        task_type: str,
        scenario: str = "",
        tags: List[str] = None,
        recent_days: int = 7
    ) -> dict:
        """
        检索相关经验
        """
        
        results = {
            "similar_tasks": [],
            "success_patterns": [],
            "failure_patterns": [],
            "learned_lessons": [],
            "skill_recommendations": [],
            "confidence": 0.0
        }
        
        tags = tags or []
        
        # 1. 检索相似任务
        similar_tasks = self._find_similar_tasks(task_type, scenario, tags, recent_days)
        results["similar_tasks"] = similar_tasks
        
        # 2. 分析成功模式
        if similar_tasks:
            successes = [t for t in similar_tasks if t.get("outcome") == "success"]
            results["success_patterns"] = self._extract_patterns(successes, "success")
            results["confidence"] = min(1.0, len(successes) / 3)
        
        # 3. 分析失败模式
        failures = [t for t in similar_tasks if t.get("outcome") != "success"]
        if failures:
            results["failure_patterns"] = self._extract_patterns(failures, "failure")
        
        # 4. 生成经验教训
        results["learned_lessons"] = self._generate_lessons(similar_tasks)
        
        # 5. 技能建议
        results["skill_recommendations"] = self._suggest_skills(task_type, similar_tasks)
        
        return results
    
    def _find_similar_tasks(
        self,
        task_type: str,
        scenario: str,
        tags: List[str],
        recent_days: int
    ) -> List[dict]:
        """查找相似任务"""
        
        cutoff = datetime.now() - timedelta(days=recent_days)
        similar = []
        
        if not self.tasks_dir.exists():
            return similar
        
        # 读取最近的任务文件
        task_files = sorted(
            self.tasks_dir.glob("*.jsonl"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:recent_days]
        
        for task_file in task_files:
            try:
                with open(task_file) as f:
                    for line in f:
                        task = json.loads(line)
                        
                        # 计算相似度
                        score = self._calculate_similarity(
                            task, task_type, scenario, tags
                        )
                        
                        if score > 0.3:
                            task["similarity_score"] = score
                            similar.append(task)
                            
            except Exception as e:
                continue
        
        # 按相似度排序
        similar.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        return similar[:10]  # 返回top 10
    
    def _calculate_similarity(
        self,
        task: dict,
        task_type: str,
        scenario: str,
        tags: List[str]
    ) -> float:
        """计算相似度"""
        
        score = 0.0
        
        # 任务类型匹配
        if task.get("task_type") == task_type:
            score += 0.4
        
        # 场景匹配
        if scenario and task.get("scenario") == scenario:
            score += 0.3
        
        # 标签匹配
        task_tags = set(task.get("tags", []))
        input_tags = set(tags)
        if task_tags & input_tags:
            score += 0.3 * len(task_tags & input_tags) / max(len(task_tags), len(input_tags))
        
        return score
    
    def _extract_patterns(self, tasks: List[dict], pattern_type: str) -> List[dict]:
        """提取模式"""
        
        patterns = []
        
        for task in tasks:
            pattern = {
                "task_id": task.get("task_id"),
                "task_type": task.get("task_type"),
                "outcome": task.get("outcome"),
                "timestamp": task.get("timestamp", "")
            }
            
            if pattern_type == "success":
                # 提取成功因素
                pattern["factors"] = [
                    f"Type: {task.get('task_type')}",
                    f"Risk: {task.get('risk_level')}"
                ]
            else:
                # 提取失败原因
                pattern["reasons"] = [task.get("error", "Unknown")]
            
            patterns.append(pattern)
        
        return patterns
    
    def _generate_lessons(self, tasks: List[dict]) -> List[str]:
        """生成经验教训"""
        
        lessons = []
        
        if not tasks:
            return ["No previous experience found for this task type"]
        
        # 统计成功率
        total = len(tasks)
        successes = len([t for t in tasks if t.get("outcome") == "success"])
        rate = successes / total if total > 0 else 0
        
        lessons.append(f"Historical success rate: {rate:.0%} ({successes}/{total})")
        
        # 从失败中学习
        failures = [t for t in tasks if t.get("outcome") != "success"]
        if failures:
            error_types = defaultdict(int)
            for f in failures:
                err = f.get("error", "unknown")
                error_types[err] += 1
            
            if error_types:
                lessons.append("Common issues to avoid:")
                for err, count in sorted(error_types.items(), key=lambda x: -x[1])[:3]:
                    err_str = str(err)[:50] if err else "unknown"
                    lessons.append(f"  • {err_str}... ({count}x)")
        
        return lessons
    
    def _suggest_skills(self, task_type: str, tasks: List[dict]) -> List[dict]:
        """建议技能"""
        
        suggestions = []
        
        # 基于历史表现推荐
        skill_performance = defaultdict(lambda: {"total": 0, "success": 0})
        
        for task in tasks:
            skill = task.get("skill_selected", "unknown")
            if skill and skill != "unknown":
                skill_performance[skill]["total"] += 1
                if task.get("outcome") == "success":
                    skill_performance[skill]["success"] += 1
        
        # 排序
        sorted_skills = sorted(
            skill_performance.items(),
            key=lambda x: x[1]["success"] / max(x[1]["total"], 1),
            reverse=True
        )
        
        for skill, stats in sorted_skills[:3]:
            rate = stats["success"] / max(stats["total"], 1)
            suggestions.append({
                "skill": skill,
                "success_rate": f"{rate:.0%}",
                "attempts": stats["total"]
            })
        
        return suggestions
    
    def get_context_summary(self, recall_results: dict) -> str:
        """生成上下文摘要"""
        
        summary = []
        
        # 成功率
        lessons = recall_results.get("learned_lessons", [])
        if lessons:
            summary.append("📊 经验:")
            for lesson in lessons[:3]:
                summary.append(f"   • {lesson}")
        
        # 技能建议
        skills = recall_results.get("skill_recommendations", [])
        if skills:
            summary.append("\n💡 推荐技能:")
            for s in skills[:2]:
                summary.append(f"   • {s['skill']} (成功率: {s['success_rate']})")
        
        # 风险提示
        failures = recall_results.get("failure_patterns", [])
        if failures:
            summary.append("\n⚠️ 注意:")
            summary.append(f"   • 历史有 {len(failures)} 次失败记录")
        
        return "\n".join(summary) if summary else "无相关经验"


def get_experience_recall():
    return ExperienceRecall()


if __name__ == "__main__":
    recall = ExperienceRecall()
    
    # Test
    result = recall.recall(
        task_type="research",
        scenario="news_summary",
        tags=["news", "tech"]
    )
    
    print("=== Experience Recall ===")
    print(f"Similar tasks: {len(result['similar_tasks'])}")
    print(f"Confidence: {result['confidence']}")
    print(f"Lessons: {result['learned_lessons']}")
