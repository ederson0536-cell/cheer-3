#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evoclaw.sqlite_memory import SQLiteMemoryStore


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _view_exists(conn: sqlite3.Connection, view_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name = ?",
        (view_name,),
    ).fetchone()
    return row is not None


def _load_legacy_rows(conn: sqlite3.Connection, source_table: str) -> list[dict[str, object]]:
    rows = conn.execute(
        f"""
        SELECT
            id, type, content, source, created_at, updated_at,
            significance, tags_json, metadata_json, raw_json
        FROM {source_table}
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _row_to_exp(row: dict[str, object]) -> dict[str, object]:
    tags = []
    metadata = {}
    raw = {}
    try:
        if row.get("tags_json"):
            tags = json.loads(str(row["tags_json"]))
    except Exception:
        tags = []
    try:
        if row.get("metadata_json"):
            parsed = json.loads(str(row["metadata_json"]))
            if isinstance(parsed, dict):
                metadata = parsed
    except Exception:
        metadata = {}
    try:
        if row.get("raw_json"):
            parsed = json.loads(str(row["raw_json"]))
            if isinstance(parsed, dict):
                raw = parsed
    except Exception:
        raw = {}

    exp = dict(raw)
    exp.setdefault("id", row.get("id"))
    exp.setdefault("type", row.get("type") or "")
    exp.setdefault("content", row.get("content") or "")
    exp.setdefault("source", row.get("source") or "")
    exp.setdefault("created_at", row.get("created_at") or "")
    exp.setdefault("updated_at", row.get("updated_at") or exp.get("created_at") or "")
    exp.setdefault("significance", row.get("significance") or metadata.get("significance") or "")
    exp.setdefault("tags", tags if isinstance(tags, list) else [])
    if "metadata" not in exp or not isinstance(exp.get("metadata"), dict):
        exp["metadata"] = metadata
    return exp


def migrate(db_path: Path, *, create_backup: bool = True) -> dict[str, object]:
    db_path = db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    backup_path = None
    if create_backup:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = db_path.with_suffix(db_path.suffix + f".bak-{ts}")
        shutil.copy2(db_path, backup_path)

    # Read legacy rows before init_schema to avoid destructive drops.
    source_table = None
    rows: list[dict[str, object]] = []
    legacy_count = 0
    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.row_factory = sqlite3.Row
        if _table_exists(raw_conn, "experiences"):
            source_table = "experiences"
        elif _table_exists(raw_conn, "experiences_legacy"):
            source_table = "experiences_legacy"

        if source_table is not None:
            legacy_count = raw_conn.execute(
                f"SELECT COUNT(*) AS c FROM {source_table}"
            ).fetchone()["c"]
            rows = _load_legacy_rows(raw_conn, source_table)

    store = SQLiteMemoryStore(db_path)
    store.init_schema()

    if source_table is None:
        with store._connect() as conn:
            conn.row_factory = sqlite3.Row
            event_count = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
        return {
            "status": "noop",
            "db": str(db_path),
            "backup": str(backup_path) if backup_path else None,
            "message": "No legacy experiences table found.",
            "experience_events": int(event_count),
        }

    imported = 0
    failed = 0
    for row in rows:
        try:
            store.upsert_experience(_row_to_exp(row))
            imported += 1
        except Exception:
            failed += 1

    with store._connect() as conn:
        conn.row_factory = sqlite3.Row

        # Keep a legacy backup table for compatibility.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiences_legacy (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                significance TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                raw_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute("DELETE FROM experiences_legacy")
        conn.executemany(
            """
            INSERT OR REPLACE INTO experiences_legacy (
                id, type, content, source, created_at, updated_at,
                significance, tags_json, metadata_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(r.get("id") or ""),
                    str(r.get("type") or ""),
                    str(r.get("content") or ""),
                    str(r.get("source") or ""),
                    str(r.get("created_at") or ""),
                    str(r.get("updated_at") or ""),
                    str(r.get("significance") or ""),
                    str(r.get("tags_json") or "[]"),
                    str(r.get("metadata_json") or "{}"),
                    str(r.get("raw_json") or "{}"),
                )
                for r in rows
            ],
        )

        store._ensure_experiences_view(conn)

        migrated_count = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
        missing_ids = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM experiences_legacy l
            LEFT JOIN memories m ON m.id = l.id
            WHERE m.id IS NULL
            """
        ).fetchone()["c"]
        by_category = {
            row["category"]: int(row["c"])
            for row in conn.execute(
                "SELECT category, COUNT(*) AS c FROM memories GROUP BY category ORDER BY c DESC"
            ).fetchall()
        }

        # Backward-compat projection tables expected by legacy tooling/tests.
        conn.execute("CREATE TABLE IF NOT EXISTS memories_conversation AS SELECT * FROM memories WHERE 0")
        conn.execute("DELETE FROM memories_conversation")
        conn.execute("INSERT INTO memories_conversation SELECT * FROM memories WHERE category = 'conversation'")

        conn.execute("CREATE TABLE IF NOT EXISTS memories_rss AS SELECT * FROM memories WHERE 0")
        conn.execute("DELETE FROM memories_rss")
        conn.execute("INSERT INTO memories_rss SELECT * FROM memories WHERE category = 'rss'")

        has_view = _view_exists(conn, "experiences")

    status = "ok" if failed == 0 and missing_ids == 0 else "warn"
    return {
        "status": status,
        "db": str(db_path),
        "backup": str(backup_path) if backup_path else None,
        "source_table": source_table,
        "legacy_count": int(legacy_count),
        "imported": int(imported),
        "failed": int(failed),
        "experience_events": int(migrated_count),
        "missing_ids": int(missing_ids),
        "category_counts": by_category,
        "experiences_view_ready": bool(has_view),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy experiences table to split experience schema (v2)."
    )
    parser.add_argument(
        "--db-path",
        default="memory/memory.db",
        help="SQLite db path (default: memory/memory.db)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup copy before migration",
    )
    args = parser.parse_args()

    summary = migrate(Path(args.db_path), create_backup=not args.no_backup)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("status") in {"ok", "noop"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
