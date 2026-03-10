#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.continuity_resolver import resolve_continuity
from evoclaw.runtime.ingress_router import route_message


def main() -> int:
    envelope = {
        "received_at": "2026-03-10T00:00:00",
        "message": "继续处理上一个任务",
        "trace_context": {"root_task_id": None, "parent_task_id": None},
        "metadata": {"message_id": "msg-1", "session_id": "sess-1"},
    }
    cont = resolve_continuity(envelope, runtime_state={"active": True, "task_id": "task_1"})
    assert cont["continuity_type"] in {
        "continue_existing_task",
        "attach_as_subtask",
        "fork_from_existing_task",
        "new_task",
    }

    payload = route_message(
        "你好",
        source="validator",
        channel="test",
        metadata={"session_id": "sess-week2", "sender": "validator"},
    )
    env = payload["envelope"]
    assert env["envelope_id"].startswith("env-")
    assert env["metadata"]["ingested_by"] == "evoclaw"
    assert payload["continuity_resolution"]["message_id"] == env["metadata"]["message_id"]


    duplicate = route_message(
        "你好",
        source="validator",
        channel="test",
        metadata={
            "session_id": "sess-week2",
            "sender": "validator",
            "raw_message_id": "fixed-1",
            "timestamp": "2026-03-10T00:00:00",
        },
    )
    duplicate_again = route_message(
        "你好",
        source="validator",
        channel="test",
        metadata={
            "session_id": "sess-week2",
            "sender": "validator",
            "raw_message_id": "fixed-1",
            "timestamp": "2026-03-10T00:00:00",
        },
    )
    assert isinstance(duplicate["handler_result"], dict)
    assert duplicate_again["handler_result"]["status"] == "blocked"
    assert duplicate_again["handler_result"]["reason"] == "duplicate_message"

    blocked = None
    for i in range(30):
        out = route_message(
            f"burst-{i}",
            source="validator",
            channel="burst-channel",
            metadata={
                "session_id": "sess-burst",
                "sender": "validator",
                "raw_message_id": f"burst-{i}",
                "timestamp": "2026-03-10T00:00:00",
            },
        )
        if out["handler_result"].get("reason") == "rate_limited":
            blocked = out
            break
    assert blocked is not None
    assert blocked["handler_result"]["status"] == "blocked"

    cron_code = (WORKSPACE / "evoclaw" / "cron_runner.py").read_text(encoding="utf-8")
    assert "route_message(" in cron_code
    assert "handler.handle(message)" not in cron_code
    assert "handler.handle(text.strip())" not in cron_code

    print("WEEK2_INGRESS_CONTINUITY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
