#!/usr/bin/env python3
"""One-time repair: normalize invalid JSON payload columns in memory DB."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "memory" / "memory.db"

# table -> column -> default JSON value
JSON_COLUMNS: dict[str, dict[str, object]] = {
    "memories": {
        "tags_json": [],
        "metadata_json": {},
        "raw_json": {},
    },
    "system_logs": {
        "metadata_json": {},
        "raw_json": {},
    },
    "task_runs": {
        "skills_json": [],
        "methods_json": [],
        "execution_steps_json": [],
        "thinking_json": [],
        "context_refs_json": [],
        "metadata_json": {},
    },
    "external_learning_events": {"metadata_json": {}},
    "notebook_experiences": {"metadata_json": {}},
    "notebook_reflections": {"analysis_json": {}, "metadata_json": {}},
    "notebook_proposals": {"metadata_json": {}},
    "notebook_rules": {"metadata_json": {}},
    "semantic_knowledge": {"metadata_json": {}},
    "system_state": {"value_json": {}},
    "system_catalog": {"metadata_json": {}},
    "rules": {"scope": {}},
}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _is_valid_json(raw: object) -> bool:
    if raw is None:
        return False
    text = str(raw).strip()
    if not text:
        return False
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return 1

    repaired = 0
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        for table, columns in JSON_COLUMNS.items():
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                continue

            table_cols = _table_columns(conn, table)
            pk_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            pk_cols = [str(r[1]) for r in pk_info if int(r[5]) > 0]
            if not pk_cols:
                pk_cols = ["rowid"]

            select_cols = list(pk_cols) + [c for c in columns.keys() if c in table_cols]
            if len(select_cols) == len(pk_cols):
                continue

            rows = conn.execute(f"SELECT {', '.join(select_cols)} FROM {table}").fetchall()
            for row in rows:
                updates: dict[str, str] = {}
                where: dict[str, object] = {}
                for pk in pk_cols:
                    where[pk] = row[pk]

                for col, default in columns.items():
                    if col not in table_cols:
                        continue
                    raw = row[col]
                    if _is_valid_json(raw):
                        continue
                    updates[col] = json.dumps(default, ensure_ascii=False)

                if not updates:
                    continue

                set_clause = ", ".join(f"{c} = ?" for c in updates.keys())
                where_clause = " AND ".join(f"{pk} = ?" for pk in pk_cols)
                params = list(updates.values()) + [where[pk] for pk in pk_cols]
                conn.execute(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)
                repaired += 1

        conn.execute(
            """
            INSERT INTO system_logs (
                id, log_type, source, content, created_at, updated_at, level, metadata_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"repair-invalid-json-{now}",
                "maintenance",
                "repair_invalid_json_fields",
                f"repaired_rows={repaired}",
                now,
                now,
                "info",
                json.dumps({"script": "scripts/repair_invalid_json_fields.py"}, ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
            ),
        )
        conn.commit()

    print(f"REPAIR_INVALID_JSON_DONE repaired_rows={repaired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
