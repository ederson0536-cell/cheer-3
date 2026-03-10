#!/usr/bin/env python3
"""
Active Learning - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 20
Proactively validates knowledge candidates through targeted tasks
"""

import sys
import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime, timedelta
from typing import Dict, List

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

from components.candidate_memory import get_candidate_memory
from components.graph_memory import get_graph_memory


class ActiveLearning:
    """Active Learning - validates candidates and explores new areas"""
    
    def __init__(self):
        self.candidates = get_candidate_memory()
        self.graph = get_graph_memory()
    
    def validate_candidates(self) -> Dict:
        """Validate ready candidates"""
        
        ready = self.candidates.get_promotion_candidates()
        
        results = {
            "candidates_checked": len(ready),
            "validated": [],
            "rejected": [],
            "pending": ready
        }
        
        for candidate in ready:
            # Check if meets promotion criteria
            validations = candidate.get("validations", [])
            
            if len(validations) >= 3:
                success_count = sum(1 for v in validations if v.get("success"))
                success_rate = success_count / len(validations)
                
                if success_rate >= 0.7:
                    self.candidates.promote_to_semantic(candidate["candidate_id"])
                    results["validated"].append(candidate["candidate_id"])
                else:
                    self.candidates.reject_candidate(
                        candidate["candidate_id"],
                        f"Success rate {success_rate:.0%} below 70%"
                    )
                    results["rejected"].append(candidate["candidate_id"])
        
        return results
    
    def explore_new_scenarios(self) -> List[Dict]:
        """Explore new scenarios"""
        
        suggestions = []
        
        # Get recent task types
        recent_types = self._get_recent_task_types()
        
        # Check for gaps
        known_scenarios = ["news", "weather", "notion", "cron", "code"]
        
        # Suggest exploration for unknown areas
        suggestions.append({
            "type": "new_scenario",
            "target": "image_generation",
            "reason": "Not yet attempted",
            "priority": "medium"
        })
        
        return suggestions
    
    def _get_recent_task_types(self) -> List[str]:
        """Get recent task types"""
        
        types = []
        tasks_dir = WORKSPACE / "memory" / "tasks"
        
        if tasks_dir.exists():
            for f in sorted(tasks_dir.glob("*.jsonl"))[-3:]:
                with open(f) as fp:
                    for line in fp:
                        try:
                            entry = json.loads(line)
                            if entry.get("task_type"):
                                types.append(entry["task_type"])
                        except:
                            continue
        
        return types
    
    def generate_validation_tasks(self) -> List[Dict]:
        """Generate tasks for validation based on candidate knowledge"""
        
        ready = self.candidates.get_candidates(status="validating")
        
        tasks = []
        
        for candidate in ready[:5]:  # Generate up to 5 validation tasks
            knowledge = candidate.get("knowledge", "")
            context = candidate.get("context", {})
            
            # Parse the candidate to generate targeted validation
            task = self._create_targeted_validation(candidate)
            
            if task:
                tasks.append(task)
        
        return tasks
    
    def _create_targeted_validation(self, candidate: Dict) -> Dict:
        """Create a targeted validation task based on the candidate knowledge"""
        
        knowledge = candidate.get("knowledge", "")
        context = candidate.get("context", {})
        
        # Scenario-based validation
        if "scenario" in knowledge.lower():
            scenario = context.get("scenario", knowledge.split(":")[-1].strip())
            
            return {
                "candidate_id": candidate["candidate_id"],
                "task_type": context.get("task_type", "research"),
                "prompt": f"执行一个{scenario}场景的任务，验证该场景是否适用",
                "scenario": scenario,
                "validation_type": "scenario_test",
                "success_criteria": ["任务成功完成", "使用了正确的场景"]
            }
        
        # Pattern-based validation (e.g., "higher success")
        if "success" in knowledge.lower() or "higher" in knowledge.lower():
            task_type = context.get("task_type", "research")
            
            return {
                "candidate_id": candidate["candidate_id"],
                "task_type": task_type,
                "prompt": f"执行一个{task_type}类型任务，验证成功率",
                "validation_type": "success_rate_test",
                "success_criteria": ["任务成功", "与预期结果一致"]
            }
        
        # Skill recommendation validation
        if "skill" in knowledge.lower() or "web fetch" in knowledge.lower():
            return {
                "candidate_id": candidate["candidate_id"],
                "task_type": "research",
                "prompt": "使用Web Fetch技能获取新闻，验证技能选择是否正确",
                "validation_type": "skill_test",
                "success_criteria": ["技能正常工作", "返回预期结果"]
            }
        
        # Default: simple validation
        return {
            "candidate_id": candidate["candidate_id"],
            "task_type": context.get("task_type", "research"),
            "prompt": f"验证: {knowledge[:30]}",
            "validation_type": "generic",
            "success_criteria": ["完成"]
        }
    
    def record_validation(self, candidate_id: str, success: bool, details: str = ""):
        """Record a validation result for a candidate"""
        
        self.candidates.add_validation(candidate_id, success, details)
        
        # Check if ready for promotion after this validation
        ready = self.candidates.get_promotion_candidates()
        
        for cand in ready:
            if cand["candidate_id"] == candidate_id:
                validations = cand.get("validations", [])
                
                if len(validations) >= 3:
                    success_count = sum(1 for v in validations if v.get("success"))
                    rate = success_count / len(validations)
                    
                    if rate >= 0.7:
                        self.candidates.promote_to_semantic(candidate_id)
                        print(f"  🎉 候选 {candidate_id[:20]}... 升级到语义记忆!")
                    else:
                        self.candidates.reject_candidate(
                            candidate_id,
                            f"Success rate {rate:.0%} below 70%"
                        )


    def run_cycle(self) -> Dict:
        """Run complete active learning cycle"""
        
        # Validate candidates
        validation_results = self.validate_candidates()
        
        # Explore new areas
        exploration = self.explore_new_scenarios()
        
        # Generate tasks
        validation_tasks = self.generate_validation_tasks()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "validation": validation_results,
            "exploration": exploration,
            "tasks_generated": len(validation_tasks)
        }


# Global instance
_active = None

def get_active_learner():
    global _active
    if _active is None:
        _active = ActiveLearning()
    return _active


if __name__ == "__main__":
    learner = get_active_learner()
    result = learner.run_cycle()
    
    print("=== Active Learning Cycle ===")
    print(f"Validated: {len(result['validation']['validated'])}")
    print(f"Rejected: {len(result['validation']['rejected'])}")
    print(f"Tasks generated: {result['tasks_generated']}")
