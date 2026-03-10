#!/usr/bin/env python3
"""
Task Manager - 统一入口
用法:
  python task_manager.py start "<消息>"
  python task_manager.py finish <task_id> <结果> [--error <错误信息>]
"""

import sys
import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = str(resolve_workspace(__file__))
sys.path.insert(0, f"{WORKSPACE}/evoclaw/runtime")

from hooks.before_task import run_before_task
from hooks.after_task import run_after_task

def main():
    if len(sys.argv) < 2:
        print("Usage: task_manager.py start|finish <args>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        if len(sys.argv) < 3:
            print("Usage: task_manager.py start <message>")
            sys.exit(1)
        
        message = sys.argv[2]
        result = run_before_task(message)
        
        # Output task_id for tracking
        print(f"\n=== TASK STARTED ===")
        print(f"Task ID: {result['task']['task_id']}")
        print(f"Type: {result['task']['task_type']}")
        print(f"Risk: {result['task']['risk_level']}")
        print(f"Priority: {result['task']['priority']}")
        print(f"Tags: {', '.join(result['task']['tags'])}")
        print(f"Ready: {result['ready_to_execute']}")
        
        # Save task_id for later
        with open(f"{WORKSPACE}/.current_task_id", "w") as f:
            f.write(result['task']['task_id'])
        
        sys.exit(0)
    
    elif command == "finish":
        # Load current task_id
        task_id_file = Path(f"{WORKSPACE}/.current_task_id")
        if not task_id_file.exists():
            print("No active task found")
            sys.exit(1)
        
        task_id = task_id_file.read_text().strip()
        
        # Load task info
        task_info = None
        memory_file = Path(f"{WORKSPACE}/memory/working/{task_id}.json")
        if memory_file.exists():
            with open(memory_file) as f:
                task_info = json.load(f)['task']
        
        if not task_info:
            print(f"Task info not found for {task_id}")
            sys.exit(1)
        
        # Get result and error
        result = sys.argv[2] if len(sys.argv) > 2 else "completed"
        error = None
        
        # Check for error flag
        if "--error" in sys.argv:
            idx = sys.argv.index("--error")
            error = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "Unknown error"
            result = None
        
        # Run after_task
        after_result = run_after_task(task_id, task_info, result, error)
        
        print(f"\n=== TASK COMPLETED ===")
        print(f"Task ID: {task_id}")
        print(f"Success: {after_result['success']}")
        if after_result['proposals']:
            print(f"Proposals: {len(after_result['proposals'])}")
        
        sys.exit(0 if after_result['success'] else 1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
