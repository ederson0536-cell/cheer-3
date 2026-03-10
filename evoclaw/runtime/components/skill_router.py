#!/usr/bin/env python3
"""
Complete Skill Router - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 9
With hard constraint checking and P0-P4 rules
"""

import sys
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)

from components.skill_registry import get_registry
from components.rule_engine import get_rule_engine
from components.config_center import get_config


class CompleteSkillRouter:
    """Complete Skill Router with hard constraints and P0-P4 rules"""
    
    def __init__(self):
        self.registry = get_registry()
        self.rule_engine = get_rule_engine()
        self.config = get_config()
        self.weights = self.config.get_routing_weights()
    
    def route(self, task_info: Dict, subtask_info: Optional[Dict] = None) -> Dict:
        """
        Complete routing with constraint checking
        Returns: {
            "skill_id": str,
            "routing_score": float,
            "hard_constraints_pass": bool,
            "constraints_violated": [],
            "reason": str,
            "alternatives": []
        }
        """
        
        task_type = task_info.get("task_type", "conversation")
        scenario = task_info.get("scenario", "")
        risk_level = task_info.get("risk_level", "low")
        
        # Get candidate skills
        candidates = self._get_candidates(task_info, subtask_info)
        
        if not candidates:
            return self._no_candidates_response()
        
        # Phase 1: Hard constraint check (P0 rules)
        candidates = self._apply_hard_constraints(candidates, task_info)
        
        if not candidates:
            return {
                "skill_id": None,
                "skill_name": "no_candidate",
                "routing_score": 0.0,
                "hard_constraints_pass": False,
                "constraints_violated": ["all_candidates_failed_hard_constraints"],
                "reason": "No skill passed P0 hard constraints",
                "alternatives": []
            }
        
        # Phase 2: Score candidates
        scored = []
        for skill in candidates:
            score_result = self._calculate_score(skill, task_info, subtask_info)
            
            scored.append({
                "skill_id": skill["skill_id"],
                "skill_name": skill["skill_name"],
                "score": score_result["total"],
                "components": score_result["components"],
                "hard_constraint_pass": True
            })
        
        # Sort by score
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        best = scored[0]
        
        # Get alternatives
        alternatives = [
            {"skill_id": s["skill_id"], "score": s["score"]}
            for s in scored[1:4]
        ]
        
        # Determine if ready to execute
        ready = (
            best["hard_constraint_pass"] and 
            best["score"] >= self.config.get("auto_execute_thresholds", {}).get("routing_score_min", 0.75)
        )
        
        return {
            "skill_id": best["skill_id"],
            "skill_name": best["skill_name"],
            "routing_score": best["score"],
            "hard_constraints_pass": best["hard_constraint_pass"],
            "constraints_violated": [],
            "reason": self._explain_choice(best, task_info),
            "alternatives": alternatives,
            "ready_to_execute": ready
        }
    
    def _get_candidates(self, task_info: Dict, subtask_info: Optional[Dict]) -> List[Dict]:
        """Get candidate skills"""
        
        candidates = []
        
        if subtask_info:
            subtask_type = subtask_info.get("subtask_type")
            if subtask_type:
                candidates = self.registry.get_skills_for_task(subtask_type)
        
        if not candidates:
            task_type = task_info.get("task_type", "conversation")
            candidates = self.registry.get_skills_for_task(task_type)
        
        return candidates
    
    def _apply_hard_constraints(self, candidates: List[Dict], task_info: Dict) -> List[Dict]:
        """Apply P0 hard constraints"""
        
        risk_level = task_info.get("risk_level", "low")
        filtered = []
        
        for skill in candidates:
            # Check 1: Skill exists
            if not skill:
                continue
            
            # Check 2: Risk vs Trust
            can_use, reason = self.registry.can_use_skill(
                skill["skill_id"],
                task_info.get("task_type", "conversation"),
                risk_level
            )
            
            if not can_use:
                continue
            
            # Check 3: P0 rule - File scope
            if task_info.get("file_write_flag") and skill.get("read_only", False):
                continue
            
            # Check 4: P0 rule - High risk requires high trust
            if risk_level in ["high", "critical"]:
                if skill.get("trust_level") not in ["high", "medium"]:
                    continue
            
            filtered.append(skill)
        
        return filtered
    
    def _calculate_score(self, skill: Dict, task_info: Dict, subtask_info: Optional[Dict]) -> Dict:
        """Calculate routing score with all factors"""
        
        w = self.weights
        
        # 1. Rule alignment (w1)
        rule_score = self._score_rule_alignment(skill, task_info)
        
        # 2. Success rate (w2)
        perf = skill.get("performance", {})
        success_rate = perf.get("avg_success_rate", 0.5)
        
        # 3. Rework penalty (w3)
        rework_rate = perf.get("avg_rework_rate", 0.2)
        rework_score = 1.0 - rework_rate
        
        # 4. Latency penalty (w4)
        latency = perf.get("avg_latency_ms", 5000)
        latency_score = max(0, 1.0 - (latency - 1000) / 10000)
        
        # 5. Trust level (w5)
        trust_scores = {"unverified": 0.3, "low": 0.5, "medium": 0.75, "high": 1.0}
        trust_score = trust_scores.get(skill.get("trust_level", "unverified"), 0.3)
        
        # 6. Scenario match (w6)
        scenario_score = self._score_scenario_match(skill, task_info)
        
        # Calculate total
        total = (
            w.get("w1", 0.2) * rule_score +
            w.get("w2", 0.25) * success_rate +
            w.get("w3", 0.15) * rework_score +
            w.get("w4", 0.1) * latency_score +
            w.get("w5", 0.15) * trust_score +
            w.get("w6", 0.15) * scenario_score
        )
        
        return {
            "total": round(total, 3),
            "components": {
                "rule_alignment": rule_score,
                "success_rate": success_rate,
                "rework_penalty": rework_score,
                "latency_penalty": latency_score,
                "trust": trust_score,
                "scenario_match": scenario_score
            }
        }
    
    def _score_rule_alignment(self, skill: Dict, task_info: Dict) -> float:
        """Score rule alignment"""
        
        task_type = task_info.get("task_type", "")
        compatible = skill.get("compatible_rules", [])
        incompatible = skill.get("incompatible_rules", [])
        
        score = 0.7
        
        # Bonus for compatible
        if task_type in ["research", "coding", "automation", "writing"]:
            score += len(compatible) * 0.05
        
        # Penalty for incompatible
        score -= len(incompatible) * 0.1
        
        return min(1.0, max(0.0, score))
    
    def _score_scenario_match(self, skill: Dict, task_info: Dict) -> float:
        """Score scenario match"""
        
        scenario = task_info.get("scenario", "").lower()
        tags = [t.lower() for t in task_info.get("tags", [])]
        preferred = [s.lower() for s in skill.get("preferred_scenarios", skill.get("supported_scenarios", []))]
        
        # Direct match
        if any(s in scenario for s in preferred if s):
            return 1.0
        
        # Tag match
        if any(s in ' '.join(tags) for s in preferred if s):
            return 0.8
        
        return 0.5
    
    def _no_candidates_response(self) -> Dict:
        """Response when no candidates found"""
        
        return {
            "skill_id": None,
            "skill_name": "default_fallback",
            "routing_score": 0.0,
            "hard_constraints_pass": True,
            "constraints_violated": [],
            "reason": "No specific skill found, using fallback",
            "alternatives": [],
            "ready_to_execute": True
        }
    
    def _explain_choice(self, best: Dict, task_info: Dict) -> str:
        """Explain routing decision"""
        
        components = best.get("components", {})
        
        reasons = []
        
        if components.get("success_rate", 0) > 0.9:
            reasons.append("高成功率")
        if components.get("trust", 0) > 0.7:
            reasons.append("高可信度")
        if components.get("scenario_match", 0) > 0.8:
            reasons.append("场景匹配")
        if components.get("rework_penalty", 0) > 0.9:
            reasons.append("低返工率")
        
        return " + ".join(reasons) if reasons else "综合评分最高"


# Global instance
_router = None

def get_router() -> CompleteSkillRouter:
    global _router
    if _router is None:
        _router = CompleteSkillRouter()
    return _router


# Backward compatibility exports used by runtime hooks.
class SkillRouter(CompleteSkillRouter):
    pass


def route_task(task_info: Dict, subtask_info: Optional[Dict] = None) -> Dict:
    return get_router().route(task_info, subtask_info)


if __name__ == "__main__":
    router = CompleteSkillRouter()
    
    tests = [
        {"task_type": "research", "scenario": "news_search", "risk_level": "low"},
        {"task_type": "automation", "scenario": "scheduled_task", "risk_level": "high"},
        {"task_type": "writing", "scenario": "notion_update", "risk_level": "medium"}
    ]
    
    for task in tests:
        result = router.route(task)
        print(f"\n{task['task_type']} / {task['risk_level']}")
        print(f"  -> Skill: {result['skill_name']} (score: {result['routing_score']})")
        print(f"  -> Ready: {result['ready_to_execute']}")
        print(f"  -> Reason: {result['reason']}")
