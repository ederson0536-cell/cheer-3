#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
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
        self.original_handle_new_task = message_handler.MessageHandler._handle_new_task
        self.original_apply_feedback_button = feedback_server.apply_feedback_button
        self.original_feedback_secret = os.environ.get("FEEDBACK_WEBHOOK_SECRET")

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
        message_handler.MessageHandler._handle_new_task = lambda _self, _message, analysis, **_kwargs: {
            "type": "task_started",
            "task_id": analysis.get("task_id"),
            "task_type": analysis.get("task_type"),
            "subtask": "fetch",
            "skill": "stub-skill",
            "message": "开始执行任务，已启动子任务: fetch",
            "success": True,
        }

    def tearDown(self):
        message_handler.analyze_task = self.original_analyze_task
        message_handler.WORKSPACE = self.original_handler_workspace
        feedback_system.WORKSPACE = self.original_feedback_workspace
        feedback_system.MEMORY = self.original_feedback_memory
        feedback_system._MEMORY_STORE = self.original_feedback_store
        feedback_server.route_message = self.original_route_message
        message_handler.MessageHandler._handle_new_task = self.original_handle_new_task
        feedback_server.apply_feedback_button = self.original_apply_feedback_button
        if self.original_feedback_secret is None:
            os.environ.pop("FEEDBACK_WEBHOOK_SECRET", None)
        else:
            os.environ["FEEDBACK_WEBHOOK_SECRET"] = self.original_feedback_secret
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

        self.assertEqual(result.get("feedback_mode"), "buttons")
        self.assertEqual(len(result.get("feedback_buttons", [])), 2)
        self.assertNotIn("这个回答满足你的需求吗", result.get("message", ""))

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

    def test_message_endpoint_rejects_feedback_events(self):
        client = feedback_server.app.test_client()
        response = client.post("/message", json={"event_type": "feedback_button", "message": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json().get("error"), "feedback_endpoint_required")

    def test_feedback_endpoint_requires_valid_signature_and_event_type(self):
        client = feedback_server.app.test_client()
        os.environ["FEEDBACK_WEBHOOK_SECRET"] = "secret"

        payload = {"event_type": "feedback_button", "callback_data": "feedback:v1:task-1:satisfied"}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(b"secret", raw_body, hashlib.sha256).hexdigest()

        captured = {}

        def fake_apply_feedback_button(task_id, value, user_message=None):
            captured["task_id"] = task_id
            captured["value"] = value
            captured["user_message"] = user_message
            return {"success": True, "task_id": task_id, "satisfaction": value}

        feedback_server.apply_feedback_button = fake_apply_feedback_button

        response = client.post(
            "/feedback",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Feedback-Signature": f"sha256={signature}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(captured["task_id"], "task-1")
        self.assertEqual(captured["value"], "satisfied")

        bad_sig = client.post(
            "/feedback",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Feedback-Signature": "sha256=deadbeef"},
        )
        self.assertEqual(bad_sig.status_code, 401)

        missing_event_payload = {"callback_data": "feedback:v1:task-1:satisfied"}
        missing_event_raw = json.dumps(missing_event_payload, separators=(",", ":")).encode("utf-8")
        missing_event_sig = hmac.new(b"secret", missing_event_raw, hashlib.sha256).hexdigest()
        missing_event = client.post(
            "/feedback",
            data=missing_event_raw,
            headers={"Content-Type": "application/json", "X-Feedback-Signature": f"sha256={missing_event_sig}"},
        )
        self.assertEqual(missing_event.status_code, 400)
        self.assertEqual(missing_event.get_json().get("error"), "invalid_event_type")

    def test_feedback_endpoint_rejects_unsupported_callback_data_version(self):
        client = feedback_server.app.test_client()
        os.environ["FEEDBACK_WEBHOOK_SECRET"] = "secret"

        payload = {"event_type": "feedback_button", "callback_data": "feedback:v2:task-1:satisfied"}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(b"secret", raw_body, hashlib.sha256).hexdigest()

        response = client.post(
            "/feedback",
            data=raw_body,
            headers={"Content-Type": "application/json", "X-Feedback-Signature": f"sha256={signature}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json().get("error"), "unsupported_callback_data_version")

    def test_every_message_persists_task_run_with_buttons(self):
        handler = message_handler.MessageHandler()
        now_iso = "2026-03-12T00:00:00"

        result = handler.handle(
            "后续消息",
            metadata={
                "source": "test",
                "channel": "cli",
                "message_id": "msg-followup",
                "session_id": "sess-1",
                "ingested_by": "evoclaw",
                "timestamp": now_iso,
                "continuity_resolution": {"continuity_type": "continue_existing_task"},
            },
        )

        self.assertEqual(result.get("feedback_mode"), "buttons")
        self.assertEqual(len(result.get("feedback_buttons", [])), 2)

        task_runs = feedback_system._get_memory_store().query_task_runs(limit=20)
        self.assertTrue(task_runs)
        latest = task_runs[0]
        self.assertEqual(latest.get("metadata", {}).get("user_message"), "后续消息")
        self.assertIn("message_handler", latest.get("methods", []))

    def test_feedback_button_unsatisfied_marks_task_notable(self):
        handler = message_handler.MessageHandler()
        now_iso = "2026-03-12T01:00:00"

        result = handler.handle(
            "请处理这个任务",
            metadata={
                "source": "test",
                "channel": "cli",
                "message_id": "msg-task-1",
                "session_id": "sess-1",
                "ingested_by": "evoclaw",
                "timestamp": now_iso,
                "continuity_resolution": {"continuity_type": "new_task"},
            },
        )
        self.assertEqual(result.get("feedback_mode"), "buttons")

        task_runs = feedback_system._get_memory_store().query_task_runs(limit=20)
        self.assertTrue(task_runs)
        task_id = task_runs[0].get("task_id")

        applied = feedback_system.apply_feedback_button(task_id, "unsatisfied", "结果不对")
        self.assertTrue(applied.get("success"))

        refreshed = feedback_system._get_memory_store().query_task_runs(limit=20)
        target = next(t for t in refreshed if t.get("task_id") == task_id)
        self.assertEqual(target.get("satisfaction"), "unsatisfied")
        self.assertEqual(target.get("significance"), "notable")

    def test_message_handler_does_not_require_continuity_resolution(self):
        handler = message_handler.MessageHandler()

        result = handler.handle(
            "无continuity字段",
            metadata={
                "source": "test",
                "channel": "cli",
                "message_id": "msg-no-continuity",
                "session_id": "sess-1",
                "ingested_by": "evoclaw",
                "timestamp": "2026-03-12T02:00:00",
            },
        )

        self.assertEqual(result.get("type"), "task_started")
        self.assertEqual(result.get("feedback_mode"), "buttons")


if __name__ == "__main__":
    unittest.main()
