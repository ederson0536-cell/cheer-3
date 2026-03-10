#!/usr/bin/env python3
"""
Enhanced Task Manager - 统一入口 (Phase 2)
支持完整任务闭环：before_task -> before_subtask -> execute -> after_subtask -> after_task

用法:
  python enhanced_task_manager.py start "<消息>"
  python enhanced_task_manager.py subtask <subtask_type> <goal>
  python enhanced_task_manager.py finish [--error <错误>]
"""

from evoclaw.workspace_resolver import resolve_workspace
import sys
import json
from datetime import datetime

WORKSPACE = str(resolve_workspace(__file__))
sys.path.insert(0, f"{WORKSPACE}/evoclaw/runtime")

from hooks.before_task import run_before_task
from hooks.after_task import run_after_task
from hooks.before_subtask import run_before_subtask
from hooks.after_subtask import run_after_subtask
from evoclaw.sqlite_memory import SQLiteMemoryStore

STATE_KEY = "runtime_task_state"

class TaskManager:
    """Enhanced Task Manager with subtask support"""
    
    def __init__(self):
        self.store = SQLiteMemoryStore(f"{WORKSPACE}/memory/memory.db")
        self.store.init_schema()
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        default = {"phase": "idle", "task_id": None, "subtasks": []}
        state = self.store.get_state(STATE_KEY, default)
        if not isinstance(state, dict):
            return dict(default)
        normalized = dict(default)
        normalized.update(state)
        if not isinstance(normalized.get("subtasks"), list):
            normalized["subtasks"] = []
        return normalized
    
    def _save_state(self):
        self.store.upsert_state(STATE_KEY, self.state, datetime.now().isoformat())
    
    def start_task(self, message: str) -> dict:
        """Start a new task with full hook pipeline"""
        
        print(f"\n{'='*50}")
        print(f"[START TASK] {message[:50]}...")
        print('='*50)
        
        # Run before_task hook
        before_result = run_before_task(message)
        
        task_info = before_result["task"]
        task_id = task_info["task_id"]
        
        # Update state
        self.state = {
            "phase": "task_started",
            "task_id": task_id,
            "task_info": task_info,
            "subtasks": [],
            "start_time": datetime.now().isoformat()
        }
        self._save_state()
        
        # Print summary
        print(f"\n✅ Task Started")
        print(f"   ID: {task_id}")
        print(f"   Type: {task_info['task_type']}")
        print(f"   Risk: {task_info['risk_level']}")
        print(f"   Tags: {', '.join(task_info['tags'])}")
        print(f"   Ready: {before_result['ready_to_execute']}")
        
        return before_result
    
    def start_subtask(self, subtask_type: str, goal: str) -> dict:
        """Start a subtask with routing"""
        
        if self.state["phase"] != "task_started":
            print("❌ No active task. Start with 'start' first.")
            return None
        
        task_id = self.state["task_id"]
        task_info = self.state["task_info"]
        
        subtask_id = f"st_{len(self.state['subtasks'])+1:03d}"
        
        subtask_info = {
            "subtask_id": subtask_id,
            "parent_task_id": task_id,
            "subtask_type": subtask_type,
            "goal": goal,
            "local_scenario": f"{subtask_type}_execution"
        }
        
        print(f"\n[START SUBTASK] {subtask_type}: {goal}")
        
        # Run before_subtask hook
        before_result = run_before_subtask(task_id, subtask_info, task_info)
        
        # Add to state
        self.state["subtasks"].append({
            "subtask_id": subtask_id,
            "subtask_info": subtask_info,
            "routing": before_result["routing"],
            "status": "in_progress",
            "start_time": datetime.now().isoformat()
        })
        self.state["phase"] = "subtask_in_progress"
        self._save_state()
        
        # Print routing result
        print(f"   Skill: {before_result['routing']['skill_name']}")
        print(f"   Score: {before_result['routing']['routing_score']}")
        
        return before_result
    
    def finish_subtask(self, result=None, error: str = None):
        """Finish current subtask"""
        
        if self.state["phase"] != "subtask_in_progress":
            print("❌ No subtask in progress.")
            return None
        
        current = self.state["subtasks"][-1]
        subtask_id = current["subtask_id"]
        
        import time
        start_time = datetime.fromisoformat(current["start_time"])
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Run after_subtask hook
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
        current["latency_ms"] = latency_ms
        self.state["phase"] = "task_started"
        self._save_state()
        
        print(f"\n✅ Subtask {subtask_id} completed - Success: {not error}")
        
        return after_result
    
    def finish_task(self, result=None, error: str = None):
        """Finish the entire task"""
        
        if self.state.get("phase") not in ["task_started", "subtask_in_progress"]:
            print("❌ No active task.")
            return None
        
        task_id = self.state["task_id"]
        task_info = self.state["task_info"]
        
        print(f"\n[FINISH TASK] {task_id}")
        
        # Run after_task hook
        after_result = run_after_task(
            task_id=task_id,
            task_info=task_info,
            result=result,
            error=error
        )
        
        # Print summary
        print(f"\n{'='*50}")
        print(f"✅ Task Completed")
        print(f"   ID: {task_id}")
        print(f"   Success: {after_result['success']}")
        print(f"   Subtasks: {len(self.state['subtasks'])}")
        if after_result['proposals']:
            print(f"   Proposals: {len(after_result['proposals'])}")
        print('='*50)
        
        # Reset state
        self.state = {"phase": "idle", "task_id": None, "subtasks": []}
        self._save_state()
        
        return after_result
    
    def status(self):
        """Show current task status"""
        
        print(f"\n=== Task Status ===")
        print(f"Phase: {self.state.get('phase', 'idle')}")
        print(f"Task ID: {self.state.get('task_id', 'None')}")
        
        if self.state.get("subtasks"):
            print(f"Subtasks ({len(self.state['subtasks'])}):")
            for st in self.state["subtasks"]:
                print(f"  - {st['subtask_id']}: {st['subtask_info']['subtask_type']} [{st['status']}]")


def main():
    if len(sys.argv) < 2:
        print("""
Enhanced Task Manager - Phase 2
==============================
Usage:
  python enhanced_task_manager.py start "<message>"
  python enhanced_task_manager.py subtask <type> <goal>
  python enhanced_task_manager.py next
  python enhanced_task_manager.py finish [--error <message>]
  python enhanced_task_manager.py status

Examples:
  start "帮我搜索新闻并上传到Notion"
  subtask fetch "获取新闻数据"
  subtask analyze "分析新闻内容"
  finish "已完成上传"
""")
        sys.exit(1)
    
    manager = TaskManager()
    command = sys.argv[1]
    
    if command == "start":
        if len(sys.argv) < 3:
            print("Usage: start <message>")
            sys.exit(1)
        manager.start_task(sys.argv[2])
    
    elif command == "subtask":
        if len(sys.argv) < 4:
            print("Usage: subtask <type> <goal>")
            sys.exit(1)
        manager.start_subtask(sys.argv[2], sys.argv[3])
    
    elif command == "next":
        # Continue to next subtask
        print("Use 'subtask' command to start next subtask")
    
    elif command == "finish":
        error = None
        if "--error" in sys.argv:
            idx = sys.argv.index("--error")
            error = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "Unknown error"
        manager.finish_task(result="completed", error=error)
    
    elif command == "status":
        manager.status()
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
