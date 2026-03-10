#!/usr/bin/env python3
"""Centralized ingress router for all message entrypoints."""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from hashlib import sha1

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
    window = ts[:16]  # minute-level window
    seed = f"{raw_message_id}|{sender}|{window}"
    digest = sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"msg-{digest}"


def route_message(
    message: str,
    *,
    source: str,
    channel: str,
    trace_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Route one incoming message through the single MessageHandler entry."""
    meta = dict(metadata or {})
    meta.setdefault("source", source)
    meta.setdefault("channel", channel)
    meta.setdefault("trace_id", trace_id or uuid4().hex)
    meta.setdefault("timestamp", datetime.now().isoformat())
    meta["message_id"] = _build_message_id(meta)

    increment_metric("ingress_total", source="ingress_router", metadata={"source": source, "channel": channel, "message_id": meta["message_id"]})

    handler = get_handler()
    result = handler.handle(message, metadata=meta)
    return {
        "message": message,
        "ingress": meta,
        "handler_result": result,
        "handler_status": handler.get_status(),
    }
