#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from evoclaw.runtime.ingress_router import route_message


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="coordination_validator_") as td:
        tmp_dir = Path(td)
        file_catalog_db = tmp_dir / "file_catalog.sqlite"
        memory_db = tmp_dir / "memory.db"

        cmd = [
        "python3",
        "scripts/build_file_catalog_db.py",
        "--root",
        str(WORKSPACE),
        "--db",
        str(file_catalog_db),
        "--memory-db",
        str(memory_db),
    ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        with sqlite3.connect(memory_db) as conn:
            cur = conn.cursor()
            total = cur.execute("SELECT object_count FROM system_catalog WHERE object_key='files.total'").fetchone()
            assert total and int(total[0]) > 0

            task_total = cur.execute("SELECT object_count FROM system_catalog WHERE object_key='tasks.total'").fetchone()
            assert task_total is not None

            root_file = cur.execute("SELECT purpose, when_to_change FROM system_readable_checklist WHERE checklist_id='root_file::AGENTS.md'").fetchone()
            assert root_file and root_file[0] and root_file[1]

            memory_dir = cur.execute(
                "SELECT purpose, when_to_change FROM system_readable_checklist WHERE checklist_id='memory_dir::memory/experiences'"
            ).fetchone()
            assert memory_dir and memory_dir[0] and memory_dir[1]

    route_message(
        "系统协调性验证消息",
        source="coordination_validator",
        channel="coordination_check",
        metadata={"session_id": "coordination", "sender": "validator"},
    )

    runtime_db = WORKSPACE / "memory" / "memory.db"
    with sqlite3.connect(runtime_db) as conn:
        conn.row_factory = sqlite3.Row
        memory_row = conn.execute(
            "SELECT id, source, type FROM memories WHERE source='coordination_validator' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert memory_row is not None

        feedback_row = conn.execute(
            "SELECT content FROM system_logs WHERE log_type='feedback_hook' AND source='feedback_system' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert feedback_row is not None
        payload = json.loads(feedback_row["content"])
        assert payload.get("hook") == "after_task"
        assert isinstance(payload.get("task"), dict)
        assert isinstance(payload.get("result"), dict)

    print("SYSTEM_COORDINATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
