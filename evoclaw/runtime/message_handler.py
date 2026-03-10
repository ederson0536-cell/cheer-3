#!/usr/bin/env python3
"""
Message Handler - Integrates Runtime into message flow
每条消息自动经过 EvoClaw Runtime
"""

import json
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))
sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.evoclaw_runtime import EvoClawRuntime
from evoclaw.runtime.components.task_engine import analyze_task
from evoclaw.hooks import before_task, after_task, handle_user_confirmation_reply
from evoclaw.runtime.observability import increment_metric


class MessageHandler:
    """消息处理器 - 集成 Runtime"""
    
    def __init__(self):
        self.runtime = EvoClawRuntime()
        self.state = {
            "active": False,
            "task_id": None,
            "waiting_for": None  # "subtask_result" / "task_completion"
        }
        self.log_file = WORKSPACE / "logs" / "message_handler.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def handle(self, message: str, metadata: dict | None = None) -> dict:
        """处理每条消息"""

        metadata = metadata or {}
        self._log("receive", {"message": message[:100], "metadata": metadata})
        confirmation_result = handle_user_confirmation_reply(message)
        if confirmation_result:
            self._log("confirmation", {"message": message[:100], "satisfied": confirmation_result.get("satisfied")})
            increment_metric("handler_success_total", source="message_handler", metadata={"path": "confirmation"})
            return confirmation_result

        task_info = {
            "name": message[:80] or "user_message",
            "type": "user_message",
            "source": metadata.get("source", "message_handler"),
            "message": message,
            "channel": metadata.get("channel"),
            "trace_id": metadata.get("trace_id"),
            "message_id": metadata.get("message_id"),
            "sender": metadata.get("sender") or metadata.get("from") or metadata.get("user_id"),
            "timestamp": metadata.get("timestamp") or datetime.now().isoformat(),
        }
        result = None
        error = None

        try:
            # handle() 开头触发 before_task
            before_task(task_info)
        except Exception as hook_err:
            self._log("hook_warn", {"hook": "before_task", "error": str(hook_err)})

        try:
            # 分析任务
            task_analysis = analyze_task(message)
            task_info["type"] = task_analysis.get("task_type", "user_message")
            task_info["task_id"] = task_analysis.get("task_id")

            # 检查是否有活跃任务
            if self.state["active"]:
                result = self._handle_continuation(message, task_analysis)
                increment_metric("handler_success_total", source="message_handler", metadata={"path": "continuation"})
                return result

            # 新任务
            result = self._handle_new_task(message, task_analysis)
            increment_metric("handler_success_total", source="message_handler", metadata={"path": "new_task"})
            return result
        except Exception as exc:
            error = exc
            increment_metric("handler_error_total", source="message_handler", metadata={"error": str(exc)[:200]})
            raise
        finally:
            # handle() 结尾触发 after_task，成功/失败都执行
            feedback_result = result or {
                "success": False,
                "message": str(error) if error else "unknown error",
                "errors": [str(error)] if error else []
            }
            try:
                after_task(task_info, feedback_result)
            except Exception as hook_err:
                self._log("hook_warn", {"hook": "after_task", "error": str(hook_err)})
    
    def _handle_new_task(self, message: str, analysis: dict) -> dict:
        """处理新任务"""
        
        # 简单任务直接执行
        if analysis["complexity_level"] == "L0" and analysis["task_type"] == "conversation":
            return self._execute_simple_task(message, analysis)
        
        # 复杂任务启动 Runtime
        self.state["active"] = True
        self.state["task_id"] = analysis["task_id"]
        self.state["waiting_for"] = "subtask_result"
        
        # 启动 Runtime
        self.runtime.start(message)
        
        # 自动生成第一个子任务
        subtask_type = self._infer_subtask_type(analysis)
        result = self.runtime.execute_subtask(subtask_type, f"执行: {message[:30]}")
        
        self._log("task_started", {
            "task_id": analysis["task_id"],
            "task_type": analysis["task_type"],
            "subtask": subtask_type
        })
        
        return {
            "type": "task_started",
            "task_id": analysis["task_id"],
            "task_type": analysis["task_type"],
            "subtask": subtask_type,
            "skill": result.get("routing", {}).get("skill_name"),
            "message": f"开始执行任务，已启动子任务: {subtask_type}"
        }
    
    def _execute_simple_task(self, message: str, analysis: dict) -> dict:
        """执行简单任务"""
        
        # 直接返回执行建议
        return {
            "type": "simple_task",
            "task_type": analysis["task_type"],
            "tags": analysis["tags"],
            "message": f"识别为{analysis['task_type']}任务，标签: {', '.join(analysis['tags'])}"
        }
    
    def _handle_continuation(self, message: str, analysis: dict) -> dict:
        """处理任务继续"""
        
        # 检查是否完成子任务
        if any(w in message for w in ["完成", "好了", "done", "success", "成功"]):
            # 完成当前子任务
            self.runtime.complete_subtask(result=message)
            
            # 检查是否还有更多子任务
            if len(self.runtime.state.get("subtasks", [])) < 2:
                # 完成任务
                result = self.runtime.complete(result=message)
                self.state["active"] = False
                self.state["task_id"] = None
                
                self._log("task_completed", {"task_id": result.get("task_id")})
                
                return {
                    "type": "task_completed",
                    "message": "任务已完成！",
                    "success": True
                }
            else:
                # 继续下一个子任务
                return {
                    "type": "subtask_completed",
                    "message": "子任务完成，继续执行..."
                }
        
        # 用户取消
        if any(w in message for w in ["取消", "cancel", "停止", "stop"]):
            self.runtime.complete(error="用户取消")
            self.state["active"] = False
            
            return {
                "type": "cancelled",
                "message": "任务已取消"
            }
        
        # 等待中
        return {
            "type": "waiting",
            "message": "任务进行中，请告诉我完成或取消"
        }
    
    def _infer_subtask_type(self, analysis: dict) -> str:
        """推断子任务类型"""
        
        task_type = analysis.get("task_type", "research")
        tags = analysis.get("tags", [])
        
        if "fetch" in str(tags) or "search" in str(tags):
            return "fetch"
        if "write" in str(tags) or "notion" in str(tags):
            return "write_output"
        if "analyze" in str(tags):
            return "analyze"
        
        return "fetch"  # Default
    
    def _log(self, event: str, data: dict):
        """记录日志"""
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **data
        }
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def get_status(self) -> dict:
        """获取状态"""
        
        return {
            "active": self.state["active"],
            "task_id": self.state["task_id"],
            "waiting_for": self.state["waiting_for"]
        }


# Global handler
_handler = None

def get_handler() -> MessageHandler:
    """获取消息处理器"""
    global _handler
    if _handler is None:
        _handler = MessageHandler()
    return _handler


if __name__ == "__main__":
    handler = get_handler()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "handle":
            # handle <message>
            result = handler.handle(sys.argv[2] if len(sys.argv) > 2 else "test")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "status":
            print(json.dumps(handler.get_status(), indent=2))
        
        elif cmd == "test":
            # Test sequence
            print("Test 1: New task")
            r1 = handler.handle("帮我搜索今天的新闻")
            print(json.dumps(r1, indent=2, ensure_ascii=False))
            
            print("\nTest 2: Complete")
            r2 = handler.handle("完成了")
            print(json.dumps(r2, indent=2, ensure_ascii=False))
    else:
        print("""
Message Handler
==============
handle <message>   - Handle a message
status             - Show status
test               - Run test sequence
""")
