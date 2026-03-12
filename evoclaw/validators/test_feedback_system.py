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

    def test_after_task_records_execution_steps_and_appends_button_feedback(self):
        task = {"name": "编码任务", "type": "coding"}
        result = {
            "success": True,
            "message": "任务处理完成",
            "duration_ms": 120,
            "tools_used": ["rg", "pytest"],
            "steps": ["定位文件", "修改逻辑", "执行测试"],
        }

        feedback_system.after_task(task, result)
        self.assertEqual(result.get("feedback_mode"), "buttons")
        self.assertEqual(len(result.get("feedback_buttons", [])), 2)
        self.assertNotIn("这个回答满足你的需求吗", result.get("message", ""))

        logs = feedback_system._get_memory_store().query_system_logs(
            log_type="feedback_hook", source="feedback_system", limit=20
        )
        after_task_payload = None
        for log in logs:
            payload = json.loads(log["content"])
            if payload.get("hook") == "after_task":
                after_task_payload = payload
                break

        self.assertIsNotNone(after_task_payload)
        self.assertGreaterEqual(len(after_task_payload.get("execution_steps", [])), 3)

    def test_handle_user_confirmation_reply_is_deprecated_and_returns_none(self):
        response = feedback_system.handle_user_confirmation_reply("满足，谢谢")
        self.assertIsNone(response)

    def test_after_task_persists_task_run_summary_with_message_metadata(self):
        task = {
            "name": "用户消息",
            "type": "conversation",
            "source": "message_handler",
            "message": "请记住这条用户对话",
            "message_id": "msg-1",
            "session_id": "sess-1",
            "channel": "cli",
            "sender": "tester",
        }
        result = {"success": True, "message": "已处理"}

        feedback_system.after_task(task, result)

        rows = feedback_system._get_memory_store().query_task_runs(limit=20)
        self.assertTrue(rows)
        target = rows[0]
        self.assertEqual(target.get("task_type"), "conversation")
        self.assertEqual(target.get("metadata", {}).get("user_message"), "请记住这条用户对话")
        self.assertEqual(target.get("metadata", {}).get("assistant_message"), "已处理")


if __name__ == "__main__":
    unittest.main()
