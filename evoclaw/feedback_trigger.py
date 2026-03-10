#!/usr/bin/env python3
"""
EvoClaw Feedback Trigger
Called by webhook transform when a message is received.

This trigger routes Telegram/OpenClaw text into the same centralized
`MessageHandler` flow used by `evoclaw/run.py`, so hooks, task state, log
files, and memory persistence all happen in one place.
"""

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = WORKSPACE / "evoclaw" / "runtime"
for p in (WORKSPACE, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.ingress_router import route_message


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: feedback_trigger.py <sender> <message>")
        return 1

    sender = str(sys.argv[1]).strip() or "unknown"
    message = str(sys.argv[2]).strip()

    if not message:
        print("No message provided, skipping")
        return 0

    routed_message = f"[@{sender}] {message}"

    payload = route_message(
        routed_message,
        source="feedback_trigger",
        channel="telegram_transform",
        metadata={"sender": sender, "raw_message": message},
    )
    payload.update({"sender": sender, "raw_message": message, "routed_message": routed_message})
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
