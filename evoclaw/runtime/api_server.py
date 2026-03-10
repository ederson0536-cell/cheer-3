#!/usr/bin/env python3
"""Simple API Server for EvoClaw centralized ingress."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from uuid import uuid4
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = WORKSPACE / "evoclaw" / "runtime"
for p in (WORKSPACE, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.ingress_router import route_message
from evoclaw.runtime.observability import get_health_snapshot, increment_metric

PORT = 8899


class EvoClawHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {"status": "running", "service": "EvoClaw Runtime"}
        if self.path == "/health":
            payload = get_health_snapshot()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        message = ""
        try:
            data = json.loads(body)
            message = data.get("message", "")
        except Exception:
            try:
                params = parse_qs(body)
                message = params.get("message", [""])[0]
            except Exception:
                message = body

        if message:
            payload = route_message(
                message,
                source="api_server",
                channel="http",
                trace_id=self.headers.get("X-Trace-Id") or uuid4().hex,
                metadata={"path": self.path},
            )
            response = {"success": True, **payload}
        else:
            increment_metric("dropped_message_total", source="api_server", metadata={"reason": "empty_message", "path": self.path})
            response = {"success": False, "error": "No message provided"}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("", PORT), EvoClawHandler)
    print(f"EvoClaw API Server running on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
