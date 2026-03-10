#!/usr/bin/env python3
"""Centralized ingress router for all message entrypoints."""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from hashlib import sha1
from collections import defaultdict, deque

from evoclaw.runtime.continuity_resolver import resolve_continuity
from evoclaw.runtime.message_handler import get_handler
from evoclaw.runtime.observability import increment_metric


_PROCESSED_IDEMPOTENCY_KEYS: set[str] = set()
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 20
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def _unix_ts(iso_ts: str) -> float:
    try:
        return datetime.fromisoformat(iso_ts).timestamp()
    except ValueError:
        return datetime.now().timestamp()


def _allow_rate_limit(channel: str, timestamp_iso: str) -> tuple[bool, int]:
    now_ts = _unix_ts(timestamp_iso)
    bucket = _RATE_LIMIT_BUCKETS[channel]
    while bucket and bucket[0] < now_ts - _RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
        return False, len(bucket)
    bucket.append(now_ts)
    return True, len(bucket)


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
    idempotency_key = envelope["idempotency_key"]

    if idempotency_key in _PROCESSED_IDEMPOTENCY_KEYS:
        increment_metric(
            "dropped_message_total",
            source="ingress_router",
            metadata={
                "reason": "duplicate_idempotency_key",
                "source": source,
                "channel": channel,
                "message_id": envelope["metadata"]["message_id"],
                "envelope_id": envelope["envelope_id"],
            },
        )
        return {
            "envelope": envelope,
            "continuity_resolution": None,
            "handler_result": {
                "status": "blocked",
                "reason": "duplicate_message",
                "idempotency_key": idempotency_key,
            },
            "handler_status": None,
        }

    rate_allowed, current_count = _allow_rate_limit(channel, envelope["received_at"])
    if not rate_allowed:
        increment_metric(
            "dropped_message_total",
            source="ingress_router",
            metadata={
                "reason": "rate_limited",
                "source": source,
                "channel": channel,
                "message_id": envelope["metadata"]["message_id"],
                "envelope_id": envelope["envelope_id"],
                "window_seconds": _RATE_LIMIT_WINDOW_SECONDS,
                "max_requests": _RATE_LIMIT_MAX_REQUESTS,
            },
        )
        return {
            "envelope": envelope,
            "continuity_resolution": None,
            "handler_result": {
                "status": "blocked",
                "reason": "rate_limited",
                "window_seconds": _RATE_LIMIT_WINDOW_SECONDS,
                "max_requests": _RATE_LIMIT_MAX_REQUESTS,
                "current_count": current_count,
            },
            "handler_status": None,
        }

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
    _PROCESSED_IDEMPOTENCY_KEYS.add(idempotency_key)
    return {
        "envelope": envelope,
        "continuity_resolution": continuity,
        "handler_result": result,
        "handler_status": handler.get_status(),
    }
