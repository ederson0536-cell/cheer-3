#!/usr/bin/env python3
"""Centralized ingress router for all message entrypoints."""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from hashlib import sha1

from evoclaw.runtime.continuity_resolver import resolve_continuity
from evoclaw.runtime.message_handler import get_handler
from evoclaw.runtime.observability import increment_metric


def _build_message_id(meta: dict) -> str:
    raw_message_id = str(
        meta.get("raw_message_id")
        or meta.get("platform_message_id")
        or meta.get("external_message_id")
        or meta.get("message_id")
        or ""
    )
    sender = str(meta.get("sender") or meta.get("from") or meta.get("user_id") or "unknown")
    ts = str(meta.get("timestamp") or datetime.now().isoformat())
    window = ts[:16]
    seed = f"{raw_message_id}|{sender}|{window}"
    digest = sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"msg-{digest}"


def _build_envelope(message: str, source: str, channel: str, trace_id: str | None, metadata: dict | None) -> dict:
    meta = dict(metadata or {})
    meta.setdefault("source", source)
    meta.setdefault("channel", channel)
    meta.setdefault("trace_id", trace_id or uuid4().hex)
    meta.setdefault("timestamp", datetime.now().isoformat())
    meta.setdefault("session_id", str(meta.get("session_id") or "default"))
    meta["message_id"] = _build_message_id(meta)
    meta.setdefault("ingested_by", "evoclaw")

    return {
        "envelope_id": f"env-{uuid4().hex[:12]}",
        "source": source,
        "event_type": "message",
        "received_at": meta["timestamp"],
        "message": message,
        "idempotency_key": meta["message_id"],
        "session_id": meta["session_id"],
        "trace_context": {
            "trace_id": meta["trace_id"],
            "root_task_id": meta.get("root_task_id"),
            "parent_task_id": meta.get("parent_task_id"),
        },
        "metadata": meta,
    }


def route_message(
    message: str,
    *,
    source: str,
    channel: str,
    trace_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    envelope = _build_envelope(message, source, channel, trace_id, metadata)

    handler = get_handler()
    continuity = resolve_continuity(envelope, runtime_state=handler.get_status())

    meta = dict(envelope["metadata"])
    meta["envelope_id"] = envelope["envelope_id"]
    meta["continuity_resolution"] = continuity

    increment_metric(
        "ingress_total",
        source="ingress_router",
        metadata={
            "source": source,
            "channel": channel,
            "message_id": meta["message_id"],
            "envelope_id": envelope["envelope_id"],
            "continuity_type": continuity["continuity_type"],
        },
    )

    result = handler.handle(message, metadata=meta)
    return {
        "envelope": envelope,
        "continuity_resolution": continuity,
        "handler_result": result,
        "handler_status": handler.get_status(),
    }
