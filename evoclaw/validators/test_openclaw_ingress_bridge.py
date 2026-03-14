#!/usr/bin/env python3
"""Regression tests for the OpenClaw -> EvoClaw ingress bridge."""

import unittest

from evoclaw.runtime import openclaw_ingress_bridge


class OpenClawIngressBridgeTests(unittest.TestCase):
    def test_process_payload_routes_message_to_central_ingress(self):
        captured = {}

        def fake_route_message(message, *, source, channel, trace_id=None, metadata=None):
            captured["message"] = message
            captured["source"] = source
            captured["channel"] = channel
            captured["trace_id"] = trace_id
            captured["metadata"] = metadata
            return {
                "handler_result": {"type": "task_started"},
                "handler_status": {"task_status": "open"},
            }

        payload = {
            "message": "修复 Telegram hooks",
            "source": "openclaw_telegram_agent",
            "channel": "telegram",
            "trace_id": "trace-bridge-1",
            "metadata": {
                "sender": "8353876273",
                "message_id": "tg-msg-1",
                "session_id": "agent:main:telegram:direct:8353876273",
                "workspace": "/tmp/workspace-cheer",
            },
        }

        result = openclaw_ingress_bridge.process_payload(payload, route_fn=fake_route_message)

        self.assertEqual(result["handler_result"]["type"], "task_started")
        self.assertEqual(captured["message"], "修复 Telegram hooks")
        self.assertEqual(captured["source"], "openclaw_telegram_agent")
        self.assertEqual(captured["channel"], "telegram")
        self.assertEqual(captured["trace_id"], "trace-bridge-1")
        self.assertEqual(captured["metadata"]["sender"], "8353876273")
        self.assertEqual(captured["metadata"]["message_id"], "tg-msg-1")
        self.assertEqual(
            captured["metadata"]["session_id"],
            "agent:main:telegram:direct:8353876273",
        )


if __name__ == "__main__":
    unittest.main()
