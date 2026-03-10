#!/usr/bin/env python3
"""
Unified Runtime - Integrates all components
Phase 3 Complete Runtime
"""

import json
import sys
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, Optional

WORKSPACE = str(resolve_workspace(__file__))
sys.path.insert(0, f"{WORKSPACE}/evoclaw/runtime")

from hooks.before_task import run_before_task
from hooks.after_task import run_after_task
from hooks.before_subtask import run_before_subtask
from hooks.after_subtask import run_after_subtask
from components.skill_router import SkillRouter
from components.proposal_processor import get_processor
from interfaces.passive_learning import get_passive_learner
from interfaces.governance import get_governance_gate


class UnifiedRuntime:
    """Unified Runtime - Complete EvoClaw Execution"""
    
    def __init__(self):
        self.state = {
            "phase": "idle",
            "task_id": None,
            "task_info": None,
            "subtasks": []
        }
        self.router = SkillRouter()
        self.processor = get_processor()
        self.learner = get_passive_learner()
        self.gate = get_governance_gate()
    
    def start(self, message: str, context: Dict = None) -> Dict:
        """Start task with full pipeline"""
        
        print(f"\n{'='*60}")
        print(f"[RUNTIME] Starting: {message[:50]}...")
        print('='*60)
        
        # Phase 1: Task Understanding
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
        
        print(f"\n📋 Task Analysis:")
        print(f"   ID: {task_id}")
        print(f"   Type: {task_info['task_type']}")
        print(f"   Risk: {task_info['risk_level']}")
        print(f"   Tags: {', '.join(task_info['tags'])}")
        
        # Check if governance review needed
        if task_info["risk_level"] in ["high", "critical"]:
            print(f"   ⚠️ High risk - governance review recommended")
        
        return before_result
    
    def execute_subtask(self, subtask_type: str, goal: str) -> Dict:
        """Execute a subtask with routing"""
        
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
        
        # Before subtask
        before_result = run_before_subtask(task_id, subtask_info, task_info)
        
        # Route
        routing = before_result["routing"]
        
        self.state["subtasks"].append({
            "subtask_id": subtask_id,
            "subtask_info": subtask_info,
            "routing": routing,
            "status": "in_progress",
            "start_time": datetime.now().isoformat()
        })
        
        self.state["phase"] = "subtask"
        
        print(f"\n🔧 Subtask {subtask_id}:")
        print(f"   Type: {subtask_type}")
        print(f"   Goal: {goal}")
        print(f"   → Skill: {routing['skill_name']}")
        print(f"   → Score: {routing['routing_score']}")
        
        if not routing["ready_to_execute"]:
            print(f"   ⚠️ Low confidence - review recommended")
        
        return before_result
    
    def complete_subtask(self, result=None, error: Optional[str] = None):
        """Complete current subtask"""
        
        if self.state["phase"] != "subtask":
            raise RuntimeError("No subtask in progress")
        
        current = self.state["subtasks"][-1]
        subtask_id = current["subtask_id"]
        
        # Calculate latency
        start = datetime.fromisoformat(current["start_time"])
        latency_ms = (datetime.now() - start).total_seconds() * 1000
        
        # After subtask
        after_result = run_after_subtask(
            parent_task_id=self.state["task_id"],
            subtask_id=subtask_id,
            subtask_info=current["subtask_info"],
            routing_info=current["routing"],
            result=result,
            error=error,
            latency_ms=latency_ms
        )
        
        # Update state
        current["status"] = "completed" if not error else "failed"
        current["result"] = result
        current["error"] = error
        self.state["phase"] = "task_started"
        
        print(f"\n✅ Subtask {subtask_id}: {'Success' if not error else 'Failed'}")
        
        return after_result
    
    def complete(self, result=None, error: Optional[str] = None) -> Dict:
        """Complete entire task"""
        
        if self.state.get("phase") not in ["task_started", "subtask"]:
            raise RuntimeError("No active task")
        
        task_id = self.state["task_id"]
        task_info = self.state["task_info"]
        
        # After task
        after_result = run_after_task(
            task_id=task_id,
            task_info=task_info,
            result=result,
            error=error
        )
        
        # Generate proposals from this task
        self._generate_task_proposals(after_result)
        
        print(f"\n{'='*60}")
        print(f"✅ TASK COMPLETED: {task_id}")
        print(f"   Success: {after_result['success']}")
        print(f"   Subtasks: {len(self.state['subtasks'])}")
        
        if after_result.get("proposals"):
            print(f"   Proposals: {len(after_result['proposals'])}")
        
        print('='*60)
        
        # Reset state
        self.state = {
            "phase": "idle",
            "task_id": None,
            "task_info": None,
            "subtasks": []
        }
        
        return after_result
    
    def _generate_task_proposals(self, after_result: Dict):
        """Generate proposals from task execution"""
        
        for proposal in after_result.get("proposals", []):
            self.processor.add_proposal(
                proposal_type=proposal.get("type", "improvement"),
                category=proposal.get("category", "general"),
                description=proposal.get("description", ""),
                task_id=self.state.get("task_id", "unknown"),
                confidence=proposal.get("confidence", 0.5)
            )
    
    def run_passive_learning(self) -> Dict:
        """Run passive learning analysis"""
        return self.learner.run_passive_learning()
    
    def analyze_proposals(self) -> Dict:
        """Analyze pending proposals"""
        return self.processor.analyze_proposals()
    
    def status(self) -> Dict:
        """Get current status"""
        return {
            "phase": self.state["phase"],
            "task_id": self.state.get("task_id"),
            "subtasks_count": len(self.state.get("subtasks", [])),
            "pending_proposals": self.processor.get_pending_count()
        }


# Global runtime instance
_runtime = None

def get_runtime() -> UnifiedRuntime:
    """Get global runtime instance"""
    global _runtime
    if _runtime is None:
        _runtime = UnifiedRuntime()
    return _runtime


# CLI
if __name__ == "__main__":
    runtime = get_runtime()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "start":
            if len(sys.argv) < 3:
                print("Usage: unified_runtime.py start <message>")
                sys.exit(1)
            runtime.start(sys.argv[2])
        
        elif cmd == "subtask":
            if len(sys.argv) < 4:
                print("Usage: unified_runtime.py subtask <type> <goal>")
                sys.exit(1)
            runtime.execute_subtask(sys.argv[2], sys.argv[3])
        
        elif cmd == "done":
            runtime.complete_subtask(result="done")
        
        elif cmd == "finish":
            error = None
            if "--error" in sys.argv:
                idx = sys.argv.index("--error")
                error = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "error"
            runtime.complete(result="completed", error=error)
        
        elif cmd == "learn":
            result = runtime.run_passive_learning()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "proposals":
            result = runtime.analyze_proposals()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "status":
            print(json.dumps(runtime.status(), indent=2))
        
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("""
Unified Runtime - Phase 3
=========================
Commands:
  start <message>     - Start a new task
  subtask <type> <goal> - Execute a subtask
  done                - Mark subtask complete
  finish              - Complete the task
  learn               - Run passive learning
  proposals           - Analyze proposals
  status              - Show current status
""")
