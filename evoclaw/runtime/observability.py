#!/usr/bin/env python3
"""Runtime observability helpers: counters + health snapshot."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from evoclaw.workspace_resolver import resolve_workspace
from evoclaw.sqlite_memory import SQLiteMemoryStore

WORKSPACE = resolve_workspace(__file__)
DB_PATH = WORKSPACE / "memory" / "memory.db"
COUNTER_KEY = "runtime_metrics_counters"


_METRIC_KEYS = {
    "ingress_total",
    "handler_success_total",
    "handler_error_total",
    "db_write_success_total",
    "db_write_failed_total",
    "dropped_message_total",
}


def _ensure_schema() -> None:
    store = SQLiteMemoryStore(DB_PATH)
    store.init_schema()


def increment_metric(metric: str, *, source: str, value: int = 1, metadata: dict | None = None) -> None:
    if metric not in _METRIC_KEYS:
        raise ValueError(f"unknown metric: {metric}")

    _ensure_schema()
    now = datetime.now().isoformat()
    meta = dict(metadata or {})
    meta["increment"] = int(value)

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value_json FROM system_state WHERE key = ?",
            (COUNTER_KEY,),
        ).fetchone()
        counters: dict[str, int] = {}
        if row and row[0]:
            try:
                counters = json.loads(row[0])
            except json.JSONDecodeError:
                counters = {}
        counters[metric] = int(counters.get(metric, 0)) + int(value)
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value_json, updated_at) VALUES (?, ?, ?)",
            (COUNTER_KEY, json.dumps(counters, ensure_ascii=False), now),
        )
        conn.execute(
            """
            INSERT INTO system_logs (
                id, log_type, source, content, created_at, updated_at,
                level, metadata_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"metric-{uuid4().hex[:16]}",
                "metric_counter",
                source,
                metric,
                now,
                now,
                "info",
                json.dumps(meta, ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
            ),
        )
        conn.commit()


def get_health_snapshot() -> dict:
    _ensure_schema()
    now = datetime.now()
    since = (now - timedelta(hours=1)).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value_json FROM system_state WHERE key = ?",
            (COUNTER_KEY,),
        ).fetchone()
        counters = {}
        if row and row[0]:
            try:
                counters = json.loads(row[0])
            except json.JSONDecodeError:
                counters = {}

        hour_rows = conn.execute(
            """
            SELECT content, COUNT(*) AS c
            FROM system_logs
            WHERE log_type = 'metric_counter' AND created_at >= ?
            GROUP BY content
            """,
            (since,),
        ).fetchall()

    last_hour = {str(name): int(count) for name, count in hour_rows}
    ingress = int(last_hour.get("ingress_total", 0))
    handler_errors = int(last_hour.get("handler_error_total", 0))
    db_success = int(last_hour.get("db_write_success_total", 0))
    db_failed = int(last_hour.get("db_write_failed_total", 0))

    handler_failure_rate = (handler_errors / ingress) if ingress else 0.0
    db_failure_rate = (db_failed / (db_success + db_failed)) if (db_success + db_failed) else 0.0

    return {
        "status": "ok",
        "window": "1h",
        "generated_at": now.isoformat(),
        "counters_total": counters,
        "counters_last_hour": last_hour,
        "failure_rates_last_hour": {
            "handler_failure_rate": handler_failure_rate,
            "db_write_failure_rate": db_failure_rate,
        },
    }
