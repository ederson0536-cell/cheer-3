#!/usr/bin/env python3
"""
Complete EvoClaw Runtime - Integrated All Components
Based on SYSTEM_FRAMEWORK_PROPOSAL.md
"""

import json
import sys
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

# Import all components
from components.task_engine import analyze_task
from components.rule_engine import get_rule_engine
from components.config_center import get_config
from components.planner import get_decomposer
from components.skill_router import get_router
from components.skill_registry import get_registry
from components.failure_taxonomy import get_failure_taxonomy
from interfaces.passive_learning import get_passive_learner
from components.active_learning import get_active_learner
from interfaces.governance import get_governance_gate
from components.proposal_processor import get_processor


class CompleteEvoClawRuntime:
    """Complete EvoClaw Runtime - All Components Integrated"""
    
    def __init__(self):
        # Initialize all components
        self.task_engine = analyze_task
        self.rule_engine = get_rule_engine()
        self.config = get_config()
        self.decomposer = get_decomposer()
        self.router = get_router()
        self.registry = get_registry()
        self.taxonomy = get_failure_taxonomy()
        self.passive_learner = get_passive_learner()
        self.active_learner = get_active_learner()
        self.governance = get_governance_gate()
        self.processor = get_processor()
        
        self.current_task = None
    
    def execute(self, message: str, context: dict = None) -> dict:
        """Execute complete workflow"""
        
        print(f"\n{'='*60}")
        print(f"[EvoClaw] Input: {message[:50]}...")
        print('='*60)
        
        # Phase 1: Task Understanding
        print(f"\n[1/6] 📋 Task Understanding...")
        task = self.task_engine(message, context)
        task_id = task["task_id"]
        print(f"   Type: {task['task_type']}, Risk: {task['risk_level']}")
        
        # Phase 2: Rule Injection
        print(f"\n[2/6] 📜 Rule Injection...")
        rules = self.rule_engine.get_rules_for_task(
            task['task_type'],
            task['risk_level'],
            task.get('scenario', '')
        )
        rule_count = sum(len(v) for v in rules.values())
        print(f"   Rules loaded: {rule_count} (P0-P4)")
        
        # Phase 3: Task Decomposition
        print(f"\n[3/6] 🎯 Task Decomposition...")
        plan = self.decomposer.decompose(
            task['task_type'],
            task['complexity_level'],
            {"task_id": task_id}
        )
        print(f"   Subtasks: {plan['total_subtasks']}, Parallel: {plan['can_parallel']}")
        
        # Phase 4: Skill Routing
        print(f"\n[4/6] 🛤️ Skill Routing...")
        routing = self.router.route(task)
        print(f"   Skill: {routing['skill_name']}, Score: {routing['routing_score']}")
        
        # Phase 5: Check Auto-Execute
        print(f"\n[5/6] ⚡ Execution Check...")
        can_auto, reason = self.config.can_auto_execute(
            routing['routing_score'],
            task['uncertainty_level'],
            task['risk_level'],
            routing.get('skill_id', 'unknown')
        )
        print(f"   Auto-execute: {can_auto} ({reason})")
        
        # Phase 6: Execution (simulated)
        print(f"\n[6/6] 🔄 Executing...")
        success = True
        result = {"message": f"Executed {routing['skill_name']}", "success": True}
        
        # Record in processor
        self.processor.add({
            "type": "execution",
            "task_type": task['task_type'],
            "skill": routing['skill_name'],
            "confidence": routing['routing_score']
        })
        
        print(f"\n{'='*60}")
        print(f"✅ Complete! Task: {task_id}, Skill: {routing['skill_name']}")
        print('='*60)
        
        return {
            "task_id": task_id,
            "task": task,
            "rules": rules,
            "plan": plan,
            "routing": routing,
            "result": result,
            "success": success
        }
    
    def run_passive_learning(self):
        """Run passive learning cycle"""
        return self.passive_learner.run_cycle()
    
    def run_active_learning(self):
        """Run active learning cycle"""
        return self.active_learner.run_cycle()
    
    def get_status(self) -> dict:
        """Get system status"""
        startup_checks = {
            "task_engine_ready": callable(self.task_engine),
            "rule_engine_ready": self.rule_engine is not None,
            "config_ready": self.config is not None,
            "decomposer_ready": self.decomposer is not None,
            "router_ready": self.router is not None,
            "registry_ready": self.registry is not None,
            "taxonomy_ready": self.taxonomy is not None,
            "passive_learner_ready": self.passive_learner is not None,
            "active_learner_ready": self.active_learner is not None,
            "governance_ready": self.governance is not None,
            "processor_ready": self.processor is not None,
        }
        return {
            "config_version": self.config.get("config_version", "unknown"),
            "skills_count": len(self.registry.skills),
            "pending_proposals": self.processor.get_pending_count(),
            "governance_stats": self.governance.get_stats(),
            "passive_stats": self.passive_learner.analyze(),
            "startup_checks": startup_checks,
        }


# Global runtime
_runtime = None

def get_runtime():
    global _runtime
    if _runtime is None:
        _runtime = CompleteEvoClawRuntime()
    return _runtime


if __name__ == "__main__":
    runtime = get_runtime()
    
    # Test
    tests = [
        "今天天气怎么样",
        "搜索科技新闻",
        "上传到Notion"
    ]
    
    for msg in tests:
        result = runtime.execute(msg)
        print(f"\n>>> {result['result']['message']}")
