#!/usr/bin/env python3
"""Transport adapter that routes messages into centralized ingress router."""

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = WORKSPACE / "evoclaw" / "runtime"
for p in (WORKSPACE, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.ingress_router import route_message


class IntegratedHandler:
    """Compatibility wrapper for old integrated handler callers."""

    def handle(self, message: str) -> dict:
        payload = route_message(
            message,
            source="integrated_handler",
            channel="runtime_integrated",
        )
        return payload["handler_result"]


if __name__ == "__main__":
    handler = IntegratedHandler()
    tests = ["今天天气怎么样", "搜索科技新闻", "设置每天早上8点提醒", "上传到Notion"]
    for msg in tests:
        result = handler.handle(msg)
        print(json.dumps(result, ensure_ascii=False))
