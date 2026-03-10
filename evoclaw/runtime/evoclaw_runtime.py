#!/usr/bin/env python3
"""
Complete EvoClaw Runtime - Phase 4
All components integrated
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = WORKSPACE / "evoclaw" / "runtime"
for p in (WORKSPACE, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.hooks.before_task import run_before_task
from evoclaw.runtime.hooks.after_task import run_after_task
from evoclaw.runtime.hooks.before_subtask import run_before_subtask
from evoclaw.runtime.hooks.after_subtask import run_after_subtask
from evoclaw.runtime.components.skill_router import SkillRouter
from evoclaw.runtime.components.proposal_processor import get_processor
from evoclaw.runtime.interfaces.passive_learning import get_passive_learner
from evoclaw.runtime.interfaces.governance import get_governance_gate
from evoclaw.runtime.components.candidate_memory import get_candidate_memory
from evoclaw.runtime.components.graph_memory import get_graph_memory
from evoclaw.runtime.components.active_learning import get_active_learner


class EvoClawRuntime:
    """Complete EvoClaw Runtime - All Phases Integrated"""
    
    def __init__(self):
        self.state = {
            "phase": "idle",
            "task_id": None,
            "task_info": None,
            "subtasks": []
        }
        
        # Initialize all components
        self.router = SkillRouter()
        self.processor = get_processor()
        self.learner = get_passive_learner()
        self.gate = get_governance_gate()
        self.candidate_memory = get_candidate_memory()
        self.graph_memory = get_graph_memory()
        self.active_learner = get_active_learner()
    
    def start(self, message: str, context: Dict = None) -> Dict:
        """Start task with full pipeline"""
        
        print(f"\n{'='*60}")
        print(f"[EvoClaw] Starting: {message[:50]}...")
        print('='*60)
        
        # Task Understanding
        before_result = run_before_task(message, context)
        task_info = before_result["task"]
        task_id = task_info["task_id"]
        
        self.state = {
            "phase": "task_started",
            "task_id": task_id,
            "task_info": task_info,
            "subtasks": [],
            "start_time": datetime.now().isoformat()
        }
        
        print(f"\n📋 Task: {task_id}")
        print(f"   Type: {task_info['task_type']} | Risk: {task_info['risk_level']}")
        print(f"   Tags: {', '.join(task_info['tags'])}")
        
        return before_result
    
    def execute_subtask(self, subtask_type: str, goal: str) -> Dict:
        """Execute a subtask"""
        
        if self.state["phase"] != "task_started":
            raise RuntimeError("No active task")
        
        task_id = self.state["task_id"]
        task_info = self.state["task_info"]
        
        subtask_id = f"st_{len(self.state['subtasks'])+1:03d}"
        
        subtask_info = {
            "subtask_id": subtask_id,
            "parent_task_id": task_id,
            "subtask_type": subtask_type,
            "goal": goal
        }
        
        before_result = run_before_subtask(task_id, subtask_info, task_info)
        routing = before_result["routing"]
        
        self.state["subtasks"].append({
            "subtask_id": subtask_id,
            "subtask_info": subtask_info,
            "routing": routing,
            "status": "in_progress",
            "start_time": datetime.now().isoformat()
        })
        
        self.state["phase"] = "subtask"
        
        print(f"\n🔧 Subtask {subtask_id}: {subtask_type} -> {routing['skill_name']}")
        
        return before_result
    
    def complete_subtask(self, result=None, error: Optional[str] = None):
        """Complete current subtask"""
        
        if self.state["phase"] != "subtask":
            raise RuntimeError("No subtask in progress")
        
        current = self.state["subtasks"][-1]
        subtask_id = current["subtask_id"]
        
        start = datetime.fromisoformat(current["start_time"])
        latency_ms = (datetime.now() - start).total_seconds() * 1000
        
        after_result = run_after_subtask(
            parent_task_id=self.state["task_id"],
            subtask_id=subtask_id,
            subtask_info=current["subtask_info"],
            routing_info=current["routing"],
            result=result,
            error=error,
            latency_ms=latency_ms
        )
        
        current["status"] = "completed" if not error else "failed"
        self.state["phase"] = "task_started"
        
        print(f"\n✅ Subtask {subtask_id}: {'Success' if not error else 'Failed'}")
        
        return after_result
    
    def complete(self, result=None, error: Optional[str] = None) -> Dict:
        """Complete entire task"""
        
        if self.state.get("phase") not in ["task_started", "subtask"]:
            raise RuntimeError("No active task")
        
        task_id = self.state["task_id"]
        task_info = self.state["task_info"]
        
        after_result = run_after_task(
            task_id=task_id,
            task_info=task_info,
            result=result,
            error=error
        )
        
        # Generate proposals
        for proposal in after_result.get("proposals", []):
            self.processor.add_proposal(
                proposal_type=proposal.get("type", "improvement"),
                category=proposal.get("category", "general"),
                description=proposal.get("description", ""),
                task_id=task_id,
                confidence=proposal.get("confidence", 0.5)
            )
        
        # Extract knowledge candidates
        if result and not error:
            self._extract_knowledge_candidates(task_info, result)
        
        print(f"\n{'='*60}")
        print(f"✅ COMPLETED: {task_id}")
        print(f"   Success: {after_result['success']}")
        print(f"   Subtasks: {len(self.state['subtasks'])}")
        print('='*60)
        
        self.state = {
            "phase": "idle",
            "task_id": None,
            "task_info": None,
            "subtasks": []
        }
        
        return after_result
    
    def _extract_knowledge_candidates(self, task_info: Dict, result):
        """Extract knowledge candidates from task execution"""
        
        # Extract from tags and scenario
        scenario = task_info.get("scenario", "")
        
        if scenario and "_general" not in scenario:
            self.candidate_memory.add_candidate(
                knowledge=f"Scenario: {scenario}",
                source=task_info.get("task_id"),
                context={
                    "task_type": task_info.get("task_type"),
                    "tags": task_info.get("tags", [])
                }
            )
    
    def learn(self) -> Dict:
        """Run learning cycle"""
        
        # Passive learning
        passive_result = self.learner.run_passive_learning()
        
        # Active learning
        active_result = self.active_learner.run_active_learning_cycle()
        
        return {
            "passive": passive_result,
            "active": active_result,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict:
        """Get system status"""
        
        return {
            "task": {
                "phase": self.state["phase"],
                "task_id": self.state.get("task_id"),
                "subtasks": len(self.state.get("subtasks", []))
            },
            "proposals": self.processor.get_pending_count(),
            "candidates": self.candidate_memory.get_stats(),
            "learner": {
                "pending_validations": len(self.active_learner.get_ready_for_validation())
            }
        }
    
    def query_graph(self, entity_id: str, depth: int = 2) -> Dict:
        """Query graph memory"""
        
        related = self.graph_memory.find_related(entity_id, depth=depth)
        
        return {
            "entity": entity_id,
            "related": related
        }


# Global runtime
_runtime = None

def get_runtime() -> EvoClawRuntime:
    """Get global runtime"""
    global _runtime
    if _runtime is None:
        _runtime = EvoClawRuntime()
    return _runtime


# CLI
if __name__ == "__main__":
    runtime = get_runtime()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "start":
            runtime.start(sys.argv[2] if len(sys.argv) > 2 else "task")
        
        elif cmd == "subtask":
            runtime.execute_subtask(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "goal")
        
        elif cmd == "done":
            runtime.complete_subtask(result="done")
        
        elif cmd == "finish":
            error = None
            if "--error" in sys.argv:
                idx = sys.argv.index("--error")
                error = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "error"
            runtime.complete(result="done", error=error)
        
        elif cmd == "learn":
            result = runtime.learn()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "status":
            print(json.dumps(runtime.get_status(), indent=2))
        
        elif cmd == "graph":
            result = runtime.query_graph(sys.argv[2] if len(sys.argv) > 2 else "task_001")
            print(json.dumps(result, indent=2))
    else:
        print("""
EvoClaw Runtime - Phase 4
==========================
start <msg>     - Start task
subtask <type> <goal> - Execute subtask
done            - Complete subtask
finish          - Complete task
learn           - Run learning cycle
status          - Show status
graph <id>      - Query graph
""")
