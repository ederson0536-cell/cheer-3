#!/usr/bin/env python3
"""Continuity resolver for Single Ingress pipeline."""

from __future__ import annotations


def resolve_continuity(envelope: dict, runtime_state: dict | None = None) -> dict:
    """Resolve continuity type for incoming envelope.

    Returns one of:
    - new_task
    - continue_existing_task
    - attach_as_subtask
    - fork_from_existing_task
    """
    runtime_state = runtime_state or {}
    meta = envelope.get("metadata", {})
    message = (envelope.get("message") or "").strip().lower()

    # explicit hint wins
    hinted = meta.get("continuity_type")
    if hinted in {
        "new_task",
        "continue_existing_task",
        "attach_as_subtask",
        "fork_from_existing_task",
    }:
        continuity_type = hinted
        confidence = float(meta.get("continuity_confidence", 0.95))
    else:
        active_task = bool(runtime_state.get("active"))
        if any(k in message for k in ["继续", "接着", "继续做", "continue"]):
            continuity_type = "continue_existing_task" if active_task else "new_task"
            confidence = 0.8
        elif any(k in message for k in ["顺便", "另外", "再加", "also"]):
            continuity_type = "attach_as_subtask" if active_task else "new_task"
            confidence = 0.7
        elif any(k in message for k in ["另开", "分支", "fork"]):
            continuity_type = "fork_from_existing_task" if active_task else "new_task"
            confidence = 0.75
        else:
            continuity_type = "continue_existing_task" if active_task else "new_task"
            confidence = 0.6 if active_task else 0.7

    return {
        "message_id": meta.get("message_id"),
        "session_id": meta.get("session_id"),
        "task_id": runtime_state.get("task_id"),
        "root_task_id": envelope.get("trace_context", {}).get("root_task_id"),
        "parent_task_id": envelope.get("trace_context", {}).get("parent_task_id"),
        "continuity_type": continuity_type,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "schema_version": "v1",
        "policy_version": "v1",
        "created_at": envelope.get("received_at"),
    }
