#!/usr/bin/env python3
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import evoclaw.feedback_server as feedback_server
import evoclaw.feedback_system as feedback_system
import evoclaw.runtime.message_handler as message_handler


class MessageHandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.memory = self.workspace / "memory"
        self.logs = self.workspace / "logs"
        self.memory.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)

        self.original_feedback_workspace = feedback_system.WORKSPACE
        self.original_feedback_memory = feedback_system.MEMORY
        self.original_feedback_store = feedback_system._MEMORY_STORE
        self.original_handler_workspace = message_handler.WORKSPACE
        self.original_analyze_task = message_handler.analyze_task
        self.original_route_message = feedback_server.route_message

        feedback_system.WORKSPACE = self.workspace
        feedback_system.MEMORY = self.memory
        feedback_system._MEMORY_STORE = None
        message_handler.WORKSPACE = self.workspace
        message_handler.analyze_task = lambda _message: {
            "task_type": "conversation",
            "task_id": "t_test_simple",
            "complexity_level": "L0",
            "tags": ["conversation"],
            "scenario": "conversation_general",
            "risk_level": "low",
        }

    def tearDown(self):
        message_handler.analyze_task = self.original_analyze_task
        message_handler.WORKSPACE = self.original_handler_workspace
        feedback_system.WORKSPACE = self.original_feedback_workspace
        feedback_system.MEMORY = self.original_feedback_memory
        feedback_system._MEMORY_STORE = self.original_feedback_store
        feedback_server.route_message = self.original_route_message
        self.tmpdir.cleanup()

    def test_simple_task_logs_single_after_task_feedback_hook(self):
        handler = message_handler.MessageHandler()

        result = handler.handle(
            "你好",
            metadata={
                "source": "test",
                "channel": "cli",
                "message_id": "msg-1",
                "session_id": "sess-1",
                "ingested_by": "evoclaw",
                "timestamp": "2026-03-11T00:00:00",
                "continuity_resolution": {"continuity_type": "new_task"},
            },
        )

        self.assertTrue(result.get("needs_confirmation"))

        with sqlite3.connect(self.memory / "memory.db") as conn:
            rows = conn.execute(
                """
                SELECT content
                FROM system_logs
                WHERE log_type = 'feedback_hook'
                ORDER BY created_at
                """
            ).fetchall()

        hooks = [json.loads(content).get("hook") for (content,) in rows]
        self.assertEqual(hooks.count("before_task"), 1)
        self.assertEqual(hooks.count("after_task"), 1)

    def test_feedback_server_message_endpoint_routes_to_central_ingress(self):
        captured = {}

        def fake_route_message(message, *, source, channel, trace_id=None, metadata=None):
            captured["message"] = message
            captured["source"] = source
            captured["channel"] = channel
            captured["trace_id"] = trace_id
            captured["metadata"] = metadata
            return {
                "envelope": {"metadata": {"message_id": "msg-test"}},
                "continuity_resolution": {"continuity_type": "new_task"},
                "handler_result": {"type": "simple_task"},
                "handler_status": {"task_status": "completed"},
            }

        feedback_server.route_message = fake_route_message
        client = feedback_server.app.test_client()

        response = client.post(
            "/message",
            json={"message": "你好", "sender": "tester", "raw_message_id": "raw-1"},
            headers={"X-Trace-Id": "trace-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["handler_result"]["type"], "simple_task")
        self.assertEqual(captured["message"], "你好")
        self.assertEqual(captured["source"], "feedback_server")
        self.assertEqual(captured["channel"], "feedback_webhook")
        self.assertEqual(captured["trace_id"], "trace-1")
        self.assertEqual(captured["metadata"]["sender"], "tester")
        self.assertEqual(captured["metadata"]["raw_message_id"], "raw-1")


if __name__ == "__main__":
    unittest.main()
