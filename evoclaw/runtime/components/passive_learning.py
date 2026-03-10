#!/usr/bin/env python3
"""
Passive Learning - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 18
Analyzes execution feedback and generates improvements
"""

import sys
import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict, Counter

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

from components.failure_taxonomy import get_failure_taxonomy
from components.proposal_processor import get_processor


class PassiveLearning:
    """Passive Learning - analyzes patterns and generates proposals"""
    
    def __init__(self):
        self.tasks_dir = WORKSPACE / "memory" / "tasks"
        self.subtasks_dir = WORKSPACE / "memory" / "subtasks"
        self.processor = get_processor()
        self.taxonomy = get_failure_taxonomy()
    
    def analyze(self, days: int = 7) -> Dict:
        """Analyze recent executions"""
        
        cutoff = datetime.now() - timedelta(days=days)
        
        stats = {
            "period_days": days,
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "success_rate": 0.0,
            "by_task_type": defaultdict(lambda: {"total": 0, "success": 0}),
            "by_risk": defaultdict(lambda: {"total": 0, "success": 0}),
            "by_scenario": defaultdict(lambda: {"total": 0, "success": 0}),
            "failure_patterns": [],
            "performance_trends": []
        }
        
        # Analyze tasks
        if self.tasks_dir.exists():
            for task_file in sorted(self.tasks_dir.glob("*.jsonl")):
                try:
                    file_date = datetime.strptime(task_file.stem, "%Y-%m-%d")
                    if file_date < cutoff:
                        continue
                except:
                    continue
                
                with open(task_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get("event") != "started":
                                continue
                            
                            stats["total_tasks"] += 1
                            
                            outcome = entry.get("outcome", "unknown")
                            task_type = entry.get("task_type", "unknown")
                            risk = entry.get("risk_level", "unknown")
                            scenario = entry.get("scenario", "unknown")
                            
                            if outcome == "success":
                                stats["successful_tasks"] += 1
                                stats["by_task_type"][task_type]["success"] += 1
                                stats["by_risk"][risk]["success"] += 1
                                stats["by_scenario"][scenario]["success"] += 1
                            else:
                                stats["failed_tasks"] += 1
                                
                                # Log failure
                                if entry.get("error"):
                                    self.taxonomy.log_failure(
                                        entry.get("task_id"),
                                        entry.get("error"),
                                        {"task_type": task_type, "risk": risk}
                                    )
                            
                            stats["by_task_type"][task_type]["total"] += 1
                            stats["by_risk"][risk]["total"] += 1
                            stats["by_scenario"][scenario]["total"] += 1
                            
                        except:
                            continue
        
        # Calculate success rates
        if stats["total_tasks"] > 0:
            stats["success_rate"] = stats["successful_tasks"] / stats["total_tasks"]
        
        for key in ["by_task_type", "by_risk", "by_scenario"]:
            for name, data in stats[key].items():
                if data["total"] > 0:
                    data["success_rate"] = data["success"] / data["total"]
        
        # Analyze failure patterns
        failure_stats = self.taxonomy.get_failure_stats(days)
        stats["failure_patterns"] = failure_stats.get("by_category", {})
        
        return stats
    
    def identify_improvements(self, days: int = 7) -> List[Dict]:
        """Identify improvement opportunities"""
        
        stats = self.analyze(days)
        opportunities = []
        
        # 1. Low success rate by task type
        for task_type, data in stats["by_task_type"].items():
            if data["total"] >= 3 and data.get("success_rate", 1.0) < 0.7:
                opportunities.append({
                    "type": "low_success_rate",
                    "target": task_type,
                    "metric": "success_rate",
                    "value": data.get("success_rate", 0),
                    "threshold": 0.7,
                    "suggestion": f"Task type '{task_type}' has {data.get('success_rate', 0):.0%} success rate. Review requirements and approach."
                })
        
        # 2. Repeated failure patterns
        for category, count in stats.get("failure_patterns", {}).items():
            if count >= 2:
                resolution = self.taxonomy.get_resolution(category)
                opportunities.append({
                    "type": "repeated_failure",
                    "target": category,
                    "count": count,
                    "suggestion": f"Category '{category}' failed {count} times. {resolution}"
                })
        
        # 3. High risk tasks with low success
        for risk, data in stats["by_risk"].items():
            if risk in ["high", "critical"] and data["total"] >= 2:
                if data.get("success_rate", 1.0) < 0.8:
                    opportunities.append({
                        "type": "high_risk_low_success",
                        "target": risk,
                        "success_rate": data.get("success_rate", 0),
                        "suggestion": f"High-risk tasks have {data.get('success_rate', 0):.0%} success rate. Add confirmation step."
                    })
        
        # 4. Performance degradation
        trends = self._analyze_trends(days)
        if trends.get("degradation"):
            opportunities.append({
                "type": "performance_degradation",
                "target": "overall",
                "details": trends["degradation"],
                "suggestion": "Performance has degraded over the period. Review recent changes."
            })
        
        return opportunities
    
    def _analyze_trends(self, days: int = 7) -> Dict:
        """Analyze performance trends"""
        
        daily_stats = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            task_file = self.tasks_dir / f"{date_str}.jsonl"
            
            total = 0
            success = 0
            
            if task_file.exists():
                with open(task_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get("event") == "started":
                                total += 1
                                if entry.get("outcome") == "success":
                                    success += 1
                        except:
                            continue
            
            if total > 0:
                daily_stats.append({
                    "date": date_str,
                    "total": total,
                    "success": success,
                    "rate": success / total
                })
        
        daily_stats.reverse()
        
        # Check for degradation (recent < earlier)
        degradation = None
        if len(daily_stats) >= 3:
            recent = sum(d["rate"] for d in daily_stats[-2:]) / 2
            earlier = sum(d["rate"] for d in daily_stats[:2]) / 2
            
            if recent < earlier - 0.1:  # 10% degradation
                degradation = f"Success rate dropped from {earlier:.0%} to {recent:.0%}"
        
        return {
            "daily_stats": daily_stats,
            "degradation": degradation
        }
    
    def generate_proposals(self) -> int:
        """Generate proposals from analysis"""
        
        opportunities = self.identify_improvements()
        proposals_generated = 0
        
        for opp in opportunities:
            proposal_type = "improvement"
            category = opp["type"]
            description = opp["suggestion"]
            
            self.processor.add({
                "type": proposal_type,
                "category": category,
                "description": description,
                "task_id": "passive_learning",
                "confidence": 0.7,
                "evidence": opp
            })
            proposals_generated += 1
        
        return proposals_generated
    def run_cycle(self) -> Dict:
        """Run complete passive learning cycle"""
        
        # Analyze
        stats = self.analyze()
        
        # Identify improvements
        opportunities = self.identify_improvements()
        
        # Generate proposals
        proposals_count = self.generate_proposals()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "opportunities": opportunities,
            "proposals_generated": proposals_count
        }



    def analyze_rule_effectiveness(self) -> List[Dict]:
        """Analyze which rules are effective"""
        
        opportunities = []
        
        # Analyze recent experiences
        experiences = []
        exp_dir = WORKSPACE / 'memory' / 'experiences'
        
        if exp_dir.exists():
            for f in sorted(exp_dir.glob('*.jsonl'))[-7:]:
                with open(f) as fp:
                    for line in fp:
                        try:
                            experiences.append(json.loads(line))
                        except:
                            continue
        
        if not experiences:
            return opportunities
        
        # Group by task type
        by_type = {}
        for exp in experiences:
            t = exp.get('task_type', 'unknown')
            if t not in by_type:
                by_type[t] = {'total': 0, 'success': 0}
            by_type[t]['total'] += 1
            if exp.get('outcome') == 'success':
                by_type[t]['success'] += 1
        
        # Analyze patterns
        for task_type, stats in by_type.items():
            if stats['total'] >= 3:
                rate = stats['success'] / stats['total']
                
                if rate < 0.7:
                    opportunities.append({
                        'type': 'rule_improvement',
                        'category': 'P2_TASK_TYPE',
                        'target': task_type,
                        'description': f'Task type {task_type} has {rate:.0%} success rate.',
                        'confidence': 0.7,
                        'evidence': stats
                    })
        
        return opportunities


# Global instance
_learner = None

def get_passive_learner() -> 'PassiveLearning':
    global _learner
    if _learner is None:
        _learner = PassiveLearning()
    return _learner
