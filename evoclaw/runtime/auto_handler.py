#!/usr/bin/env python3
"""Auto handler transport adapter using centralized ingress router."""

from evoclaw.runtime.ingress_router import route_message


class AutoHandler:
    def process(self, message: str) -> dict:
        payload = route_message(
            message,
            source="auto_handler",
            channel="runtime_auto",
        )
        return {
            "type": "routed",
            "result": payload["handler_result"],
            "envelope": payload["envelope"],
            "continuity_resolution": payload.get("continuity_resolution"),
        }


_auto_handler = None


def get_auto_handler():
    global _auto_handler
    if _auto_handler is None:
        _auto_handler = AutoHandler()
    return _auto_handler


if __name__ == "__main__":
    handler = get_auto_handler()
    for msg in ["今天天气怎么样", "你好啊", "帮我搜索新闻"]:
        print(handler.process(msg))
