#!/usr/bin/env python3
"""EvoClaw feedback webhook server.

Receives Telegram/OpenClaw webhook events and forwards every message into the
centralized ingress router so the full Evo pipeline (continuity, hooks,
logging, memory) is always applied.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

from evoclaw.workspace_resolver import resolve_workspace

app = Flask(__name__)

WORKSPACE = resolve_workspace(__file__)
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.ingress_router import route_message
from evoclaw.feedback_system import apply_feedback_button


def _pick_message(data: dict) -> str:
    return str(data.get("message") or data.get("text") or "").strip()


def _pick_sender(data: dict) -> str:
    sender = data.get("sender") or data.get("from") or data.get("user_id")
    if isinstance(sender, dict):
        sender = sender.get("id") or sender.get("username")
    return str(sender or "unknown")


def _pick_raw_message_id(data: dict) -> str:
    explicit = data.get("raw_message_id") or data.get("message_id") or data.get("update_id")
    if explicit is not None and str(explicit).strip():
        return str(explicit)

    telegram_message = data.get("telegram_message")
    if isinstance(telegram_message, dict) and telegram_message.get("message_id") is not None:
        return str(telegram_message["message_id"])

    update = data.get("update")
    if isinstance(update, dict):
        message = update.get("message")
        if isinstance(message, dict) and message.get("message_id") is not None:
            return str(message["message_id"])
        if update.get("update_id") is not None:
            return str(update["update_id"])

    return ""


def _parse_callback_data(data: dict) -> tuple[str, str, str | None]:
    callback_data = data.get("callback_data")
    if not isinstance(callback_data, str) or not callback_data.strip():
        return "", "", "missing_callback_data"

    parts = callback_data.split(":", 3)
    if len(parts) < 4 or parts[0] != "feedback":
        return "", "", "invalid_callback_data_format"

    _, version, task_id, value = parts
    if version != "v1":
        return "", "", "unsupported_callback_data_version"

    if not task_id.strip() or not value.strip():
        return "", "", "invalid_callback_data_payload"

    return task_id.strip(), value.strip(), None


def _pick_feedback_payload(data: dict) -> tuple[dict | None, str | None]:
    event_type = str(data.get("event_type") or "").strip().lower()
    if event_type != "feedback_button":
        return None, "invalid_event_type"

    task_id = str(data.get("task_id") or "").strip()
    value = data.get("feedback_value") or data.get("feedback") or data.get("satisfaction")
    message = str(data.get("feedback_message") or "").strip()

    if not task_id or value is None:
        parsed_task_id, parsed_value, parse_error = _parse_callback_data(data)
        if parse_error:
            return None, parse_error
        task_id = task_id or parsed_task_id
        value = value or parsed_value

    if not task_id or value is None:
        return None, "missing_feedback_fields"

    return {"task_id": task_id, "value": str(value), "message": message}, None


def _verify_feedback_signature(raw_body: bytes) -> bool:
    secret = os.environ.get("FEEDBACK_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Backward-compatible: if secret is not configured, skip signature check.
        return True

    signature = request.headers.get("X-Feedback-Signature", "").strip()
    if not signature:
        return False

    normalized = signature
    if signature.startswith("sha256="):
        normalized = signature.split("=", 1)[1]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(normalized, expected)


@app.route("/message", methods=["POST"])
def handle_message():
    data = request.get_json(silent=True) or {}

    if str(data.get("event_type") or "").strip().lower() == "feedback_button":
        return jsonify({"success": False, "error": "feedback_endpoint_required", "hint": "POST /feedback"}), 400

    message = _pick_message(data)
    if not message:
        return jsonify({"success": False, "error": "empty_message"}), 400

    sender = _pick_sender(data)
    raw_message_id = _pick_raw_message_id(data)

    metadata = {
        "sender": sender,
        "raw_message": message,
    }
    if raw_message_id:
        metadata["raw_message_id"] = raw_message_id

    result = route_message(
        message,
        source="feedback_server",
        channel="feedback_webhook",
        trace_id=request.headers.get("X-Trace-Id"),
        metadata=metadata,
    )

    return jsonify(
        {
            "success": True,
            "message_id": result.get("envelope", {}).get("metadata", {}).get("message_id"),
            "continuity_resolution": result.get("continuity_resolution"),
            "handler_result": result.get("handler_result"),
            "handler_status": result.get("handler_status"),
        }
    )


@app.route("/callback", methods=["POST"])
def handle_callback():
    """Handle Telegram inline button callback queries."""
    data = request.get_json(silent=True) or {}
    
    # Handle Telegram callback_query
    callback_query = data.get("callback_query", {})
    if callback_query:
        return _handle_telegram_callback(callback_query)
    
    # Handle direct feedback format
    feedback_payload, error = _pick_feedback_payload(data)
    if error:
        return jsonify({"success": False, "error": error}), 400

    applied = apply_feedback_button(
        task_id=feedback_payload["task_id"],
        value=feedback_payload["value"],
        user_message=feedback_payload.get("message") or None,
    )
    status = 200 if applied.get("success") else 400
    return jsonify(applied), status


def _handle_telegram_callback(callback_query: dict) -> dict:
    """Handle Telegram callback_query (button click)."""
    from evoclaw.feedback_system import apply_feedback_button
    
    # Extract callback_data which contains: feedback:v1:message_id:value
    callback_data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    
    if not callback_data.startswith("feedback:"):
        return jsonify({"success": False, "error": "unknown_callback"}), 400
    
    # Parse: feedback:v1:message_id:value
    parts = callback_data.split(":")
    if len(parts) >= 4:
        task_id = parts[2]  # message_id
        value = parts[3]    # satisfied or unsatisfied
    else:
        return jsonify({"success": False, "error": "invalid_callback_data"}), 400
    
    # Apply the feedback
    applied = apply_feedback_button(
        task_id=task_id,
        value=value,
        user_message=None,
    )
    
    # Answer the callback to remove loading state
    # (This would need the bot token to answer callback)
    
    status = 200 if applied.get("success") else 400
    return jsonify(applied), status


@app.route("/feedback", methods=["POST"])
def handle_feedback():
    raw_body = request.get_data(cache=True) or b""
    if not _verify_feedback_signature(raw_body):
        return jsonify({"success": False, "error": "invalid_signature"}), 401

    data = request.get_json(silent=True) or {}
    feedback_payload, error = _pick_feedback_payload(data)
    if error:
        return jsonify({"success": False, "error": error}), 400

    applied = apply_feedback_button(
        task_id=feedback_payload["task_id"],
        value=feedback_payload["value"],
        user_message=feedback_payload.get("message") or None,
    )
    status = 200 if applied.get("success") else 400
    return jsonify(applied), status


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("=" * 50)
    print("EvoClaw Feedback Webhook Server")
    print("Listening on http://localhost:8899")
    print("=" * 50)
    app.run(port=8899, debug=False)
