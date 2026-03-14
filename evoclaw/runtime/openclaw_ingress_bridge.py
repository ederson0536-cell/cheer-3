#!/usr/bin/env python3
"""Bridge OpenClaw agent turns into EvoClaw's centralized ingress router."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = WORKSPACE_ROOT / "evoclaw" / "runtime"
for p in (WORKSPACE_ROOT, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.ingress_router import route_message


RouteFn = Callable[..., dict[str, Any]]


def process_payload(payload: dict[str, Any], *, route_fn: RouteFn = route_message) -> dict[str, Any]:
    """Route one OpenClaw payload into the centralized EvoClaw ingress."""
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message is required")

    source = str(payload.get("source") or "openclaw_agent")
    channel = str(payload.get("channel") or "telegram")
    trace_id = payload.get("trace_id")
    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("source", source)
    metadata.setdefault("channel", channel)
    metadata.setdefault("ingress_origin", "openclaw_agent")

    return route_fn(
        message,
        source=source,
        channel=channel,
        trace_id=trace_id,
        metadata=metadata,
    )


def main() -> int:
    payload = json.load(sys.stdin)
    result = process_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
