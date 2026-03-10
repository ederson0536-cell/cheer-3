#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import evoclaw.feedback_system as feedback_system


class FeedbackSystemTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.memory = self.workspace / "memory"
        self.memory.mkdir(parents=True, exist_ok=True)

        feedback_system.WORKSPACE = self.workspace
        feedback_system.MEMORY = self.memory
        feedback_system._MEMORY_STORE = None

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_after_task_records_execution_steps_and_appends_confirmation_prompt(self):
        task = {"name": "编码任务", "type": "coding"}
        result = {
            "success": True,
            "message": "任务处理完成",
            "duration_ms": 120,
            "tools_used": ["rg", "pytest"],
            "steps": ["定位文件", "修改逻辑", "执行测试"],
        }

        feedback_system.after_task(task, result)
        self.assertIn("这个回答满足你的需求吗？", result["message"])
        self.assertTrue(result.get("needs_confirmation"))

        logs = feedback_system._get_memory_store().query_system_logs(log_type="feedback_hook", source="feedback_system", limit=20)
        after_task_payload = None
        for log in logs:
            payload = json.loads(log["content"])
            if payload.get("hook") == "after_task":
                after_task_payload = payload
                break

        self.assertIsNotNone(after_task_payload)
        self.assertGreaterEqual(len(after_task_payload.get("execution_steps", [])), 3)
        pending = feedback_system._get_memory_store().get_state(feedback_system.CONFIRMATION_STATE_KEY, default={})
        self.assertTrue(pending.get("active"))

    def test_handle_user_confirmation_reply_records_feedback_and_closes_pending(self):
        now = "2026-03-08T12:00:00"
        feedback_system._get_memory_store().upsert_state(
            feedback_system.CONFIRMATION_STATE_KEY,
            {
                "active": True,
                "task_name": "process-message",
                "task_type": "messaging",
                "created_at": now,
            },
            now,
        )

        response = feedback_system.handle_user_confirmation_reply("满足，谢谢")
        self.assertIsNotNone(response)
        self.assertTrue(response["success"])
        self.assertTrue(response["satisfied"])

        pending = feedback_system._get_memory_store().get_state(feedback_system.CONFIRMATION_STATE_KEY, default={})
        self.assertFalse(pending.get("active"))

        logs = feedback_system._get_memory_store().query_system_logs(log_type="feedback_hook", source="feedback_system", limit=20)
        confirmation_payload = None
        for log in logs:
            payload = json.loads(log["content"])
            if payload.get("hook") == "user_confirmation":
                confirmation_payload = payload
                break

        self.assertIsNotNone(confirmation_payload)
        self.assertTrue(confirmation_payload.get("confirmation", {}).get("satisfied"))

    def test_after_task_writes_conversation_memory_into_memories_table(self):
        task = {
            "name": "用户消息",
            "type": "conversation",
            "source": "message_handler",
            "message": "请记住这条用户对话"
        }
        result = {"success": True, "message": "已处理"}

        feedback_system.after_task(task, result)

        rows = feedback_system._get_memory_store().query_experiences(
            exp_type="conversation",
            source="message_handler",
            limit=20,
        )
        target = next((row for row in rows if row.get("content") == "请记住这条用户对话"), None)
        self.assertIsNotNone(target)


if __name__ == "__main__":
    unittest.main()
