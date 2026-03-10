#!/usr/bin/env python3
"""
EvoClaw Runtime Wrapper
Transparent wrapper for handling user messages through the runtime
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

from evoclaw_runtime import EvoClawRuntime


class RuntimeWrapper:
    """Wrapper to handle messages through EvoClaw Runtime"""
    
    def __init__(self):
        self.runtime = EvoClawRuntime()
        self.log_file = WORKSPACE / "logs" / "runtime_interactions.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def handle_message(self, message: str) -> dict:
        """Handle a user message through the runtime"""
        
        # Log interaction
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "phase": "starting"
        }
        self._log(entry)
        
        try:
            # Start task
            result = self.runtime.start(message)
            
            # Return task info for user to continue
            task_info = result.get("task", {})
            
            entry["phase"] = "started"
            entry["task_id"] = task_info.get("task_id")
            entry["task_type"] = task_info.get("task_type")
            self._log(entry)
            
            return {
                "success": True,
                "task_id": task_info.get("task_id"),
                "task_type": task_info.get("task_type"),
                "risk_level": task_info.get("risk_level"),
                "tags": task_info.get("tags"),
                "checklist": result.get("checklist", []),
                "ready": result.get("ready_to_execute", True)
            }
            
        except Exception as e:
            entry["phase"] = "error"
            entry["error"] = str(e)
            self._log(entry)
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def execute_subtask(self, subtask_type: str, goal: str) -> dict:
        """Execute a subtask"""
        
        try:
            result = self.runtime.execute_subtask(subtask_type, goal)
            
            routing = result.get("routing", {})
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "phase": "subtask",
                "subtask_type": subtask_type,
                "skill": routing.get("skill_name"),
                "score": routing.get("routing_score")
            }
            self._log(entry)
            
            return {
                "success": True,
                "skill": routing.get("skill_name"),
                "score": routing.get("routing_score"),
                "ready": routing.get("ready_to_execute", True)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def complete_subtask(self, result: str = None, error: str = None) -> dict:
        """Complete current subtask"""
        
        try:
            self.runtime.complete_subtask(result=result, error=error)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def finish_task(self, result: str = None, error: str = None) -> dict:
        """Finish the task"""
        
        try:
            complete_result = self.runtime.complete(result=result, error=error)
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "phase": "completed",
                "success": complete_result.get("success", False),
                "proposals": len(complete_result.get("proposals", []))
            }
            self._log(entry)
            
            # Run learning
            self.runtime.learn()
            
            return {
                "success": complete_result.get("success", False),
                "proposals": len(complete_result.get("proposals", []))
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> dict:
        """Get current status"""
        
        return self.runtime.get_status()
    
    def _log(self, entry: dict):
        """Log interaction"""
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Global wrapper instance
_wrapper = None

def get_wrapper() -> RuntimeWrapper:
    """Get global wrapper"""
    global _wrapper
    if _wrapper is None:
        _wrapper = RuntimeWrapper()
    return _wrapper


if __name__ == "__main__":
    wrapper = get_wrapper()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "handle":
            # handle <message>
            result = wrapper.handle_message(sys.argv[2] if len(sys.argv) > 2 else "test")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "subtask":
            # subtask <type> <goal>
            result = wrapper.execute_subtask(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "goal")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "done":
            result = wrapper.complete_subtask(result="done")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "finish":
            result = wrapper.finish_task(result="completed")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "status":
            print(json.dumps(wrapper.get_status(), indent=2))
    else:
        print("""
EvoClaw Wrapper
================
handle <message>   - Start handling a message
subtask <type> <goal> - Execute a subtask
done               - Complete current subtask
finish             - Finish the task
status             - Show current status
""")
