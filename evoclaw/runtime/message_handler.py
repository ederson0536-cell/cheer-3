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
from evoclaw.hooks import before_task, before_subtask, after_subtask, after_task
from evoclaw.runtime.observability import increment_metric


REQUIRED_CHAIN_FIELDS = ("message_id", "session_id", "ingested_by")


class MessageHandler:
    """消息处理器 - 集成 Runtime"""

    def __init__(self):
        self.runtime = EvoClawRuntime()
        self.state = {
            "task_id": None,
            "task_status": "new",
        }
        self.log_file = WORKSPACE / "logs" / "message_handler.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _enforce_chain_guard(self, metadata: dict):
        missing = [k for k in REQUIRED_CHAIN_FIELDS if k not in metadata]
        if missing:
            increment_metric(
                "bypass_attempt_total",
                source="message_handler",
                metadata={"missing": ",".join(missing)},
            )
            raise ValueError(f"Single Ingress chain guard failed, missing: {missing}")

        if metadata.get("ingested_by") != "evoclaw":
            raise ValueError("Single Ingress chain guard failed: ingested_by must be 'evoclaw'")

    def _set_task_status(self, to_status: str, reason: str):
        from_status = self.state.get("task_status")
        self.state["task_status"] = to_status
        self._log(
            "state_transition",
            {
                "object": "task",
                "from_state": from_status,
                "to_state": to_status,
                "reason": reason,
            },
        )

    def handle(self, message: str, metadata: dict | None = None) -> dict:
        """处理每条消息"""

        metadata = metadata or {}
        self._enforce_chain_guard(metadata)

        continuity = metadata.get("continuity_resolution") if isinstance(metadata.get("continuity_resolution"), dict) else {}
        task_info = {
            "name": message[:80] or "user_message",
            "type": "user_message",
            "source": metadata.get("source", "message_handler"),
            "message": message,
            "channel": metadata.get("channel"),
            "trace_id": metadata.get("trace_id"),
            "message_id": metadata.get("message_id"),
            "session_id": metadata.get("session_id"),
            "ingested_by": metadata.get("ingested_by"),
            "continuity_type": continuity.get("continuity_type", "independent_message_task"),
            "sender": metadata.get("sender") or metadata.get("from") or metadata.get("user_id"),
            "timestamp": metadata.get("timestamp") or datetime.now().isoformat(),
        }
        self._log("receive", {"message": message[:100], "metadata": metadata})
        result = None
        error = None

        try:
            before_task(task_info)
        except Exception as hook_err:
            self._log("hook_warn", {"hook": "before_task", "error": str(hook_err)})

        try:
            task_analysis = analyze_task(message)
            task_info["type"] = task_analysis.get("task_type", "user_message")
            msg_task_id = f"msgtask-{task_info.get('message_id') or datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            task_info["task_id"] = msg_task_id
            task_info["analysis_task_id"] = task_analysis.get("task_id")

            subtask = {
                "name": str(task_analysis.get("task_type") or "message_task"),
                "type": "message_execution",
                "task_id": task_info.get("task_id"),
            }
            try:
                before_subtask(subtask)
            except Exception as hook_err:
                self._log("hook_warn", {"hook": "before_subtask", "error": str(hook_err)})
            result = self._handle_new_task(message, task_analysis, task_id=msg_task_id)
            try:
                after_subtask(subtask, result if isinstance(result, dict) else {"success": True})
            except Exception as hook_err:
                self._log("hook_warn", {"hook": "after_subtask", "error": str(hook_err)})
            increment_metric("handler_success_total", source="message_handler", metadata={"path": "message_task"})
            return result
        except Exception as exc:
            error = exc
            self._set_task_status("failed", "exception")
            increment_metric("handler_error_total", source="message_handler", metadata={"error": str(exc)[:200]})
            raise
        finally:
            feedback_result = result or {
                "success": False,
                "message": str(error) if error else "unknown error",
                "errors": [str(error)] if error else []
            }
            try:
                after_task(task_info, feedback_result)
            except Exception as hook_err:
                self._log("hook_warn", {"hook": "after_task", "error": str(hook_err)})

    def _handle_new_task(self, message: str, analysis: dict, *, task_id: str | None = None) -> dict:
        current_task_id = str(task_id or analysis.get("task_id") or f"task-{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
        self.state["task_id"] = current_task_id
        self._set_task_status("open", "single_message_task")

        self.runtime.start(message)
        subtask_type = self._infer_subtask_type(analysis)
        exec_result = self.runtime.execute_subtask(subtask_type, f"执行: {message[:30]}")
        self._set_task_status("in_progress", "single_message_subtask_executed")
        self.runtime.complete(result=f"message-task:{current_task_id}")

        self.state["task_id"] = None
        self._set_task_status("completed", "single_message_task_finished")

        self._log("task_completed", {
            "task_id": current_task_id,
            "task_type": analysis.get("task_type"),
            "subtask": subtask_type,
        })

        return {
            "type": "task_completed",
            "task_id": current_task_id,
            "task_type": analysis.get("task_type"),
            "subtask": subtask_type,
            "skill": exec_result.get("routing", {}).get("skill_name"),
            "success": True,
            "message": f"消息任务已完成: {subtask_type}",
        }



    def _infer_subtask_type(self, analysis: dict) -> str:
        tags = analysis.get("tags", [])
        if "fetch" in str(tags) or "search" in str(tags):
            return "fetch"
        if "write" in str(tags) or "notion" in str(tags):
            return "write_output"
        if "analyze" in str(tags):
            return "analyze"
        return "fetch"

    def _log(self, event: str, data: dict):
        entry = {"timestamp": datetime.now().isoformat(), "event": event, **data}
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_status(self) -> dict:
        return {
            "task_id": self.state["task_id"],
            "task_status": self.state["task_status"],
        }


_handler = None


def get_handler() -> MessageHandler:
    global _handler
    if _handler is None:
        _handler = MessageHandler()
    return _handler


if __name__ == "__main__":
    handler = get_handler()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "handle":
            result = handler.handle(
                sys.argv[2] if len(sys.argv) > 2 else "test",
                metadata={
                    "source": "message_handler_direct",
                    "channel": "cli",
                    "message_id": "msg-direct",
                    "session_id": "sess-direct",
                    "ingested_by": "evoclaw",
                },
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif cmd == "status":
            print(json.dumps(handler.get_status(), indent=2))
