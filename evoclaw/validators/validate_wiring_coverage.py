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


ENTRYPOINT_FILES = [
    "evoclaw/runtime/api_server.py",
    "evoclaw/runtime/auto_handler.py",
    "evoclaw/runtime/integrated_handler.py",
    "evoclaw/feedback_trigger.py",
    "evoclaw/cron_runner.py",
    "evoclaw/run.py",
]


def _read(path: str) -> str:
    return (WORKSPACE / path).read_text(encoding="utf-8")


def main() -> int:
    # 1) ingress wiring: all known external entrypoints must route via ingress router
    for rel in ENTRYPOINT_FILES:
        code = _read(rel)
        assert "route_message(" in code, f"{rel} missing route_message()"

    # 2) registry files must be parseable and non-empty
    root_registry_path = WORKSPACE / "evoclaw/runtime/config/root_file_registry.json"
    memory_registry_path = WORKSPACE / "evoclaw/runtime/config/memory_directory_registry.json"

    root_registry = json.loads(root_registry_path.read_text(encoding="utf-8"))
    memory_registry = json.loads(memory_registry_path.read_text(encoding="utf-8"))

    root_files = root_registry.get("files", [])
    memory_dirs = memory_registry.get("directories", [])
    assert root_files, "root_file_registry.json has no files"
    assert memory_dirs, "memory_directory_registry.json has no directories"

    # 3) file governance must consume root file registry
    fg_code = _read("evoclaw/runtime/components/file_governance.py")
    assert "ROOT_FILE_REGISTRY" in fg_code
    assert "_load_root_file_registry" in fg_code

    # 4) catalog builder must consume both registries and write checklist table
    builder = _read("scripts/build_file_catalog_db.py")
    assert "load_root_registry" in builder
    assert "load_memory_directory_registry" in builder
    assert "system_readable_checklist" in builder

    # 5) runtime DB schema must contain checklist table and accessors
    sqlite_code = _read("evoclaw/sqlite_memory.py")
    assert "CREATE TABLE IF NOT EXISTS system_readable_checklist" in sqlite_code
    assert "def replace_readable_checklist" in sqlite_code
    assert "def query_readable_checklist" in sqlite_code

    # 6) end-to-end: run builder and verify every registry item lands into checklist DB table
    with tempfile.TemporaryDirectory(prefix="wiring_coverage_") as td:
        td_path = Path(td)
        file_catalog_db = td_path / "file_catalog.sqlite"
        memory_db = td_path / "memory.db"

        result = subprocess.run(
            [
                "python3",
                "scripts/build_file_catalog_db.py",
                "--root",
                str(WORKSPACE),
                "--db",
                str(file_catalog_db),
                "--memory-db",
                str(memory_db),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        with sqlite3.connect(memory_db) as conn:
            cur = conn.cursor()
            root_count = cur.execute(
                "SELECT COUNT(*) FROM system_readable_checklist WHERE checklist_type='root_file'"
            ).fetchone()[0]
            memory_count = cur.execute(
                "SELECT COUNT(*) FROM system_readable_checklist WHERE checklist_type='memory_directory'"
            ).fetchone()[0]

        assert root_count == len(root_files), f"root checklist count mismatch: {root_count} != {len(root_files)}"
        assert memory_count == len(memory_dirs), f"memory checklist count mismatch: {memory_count} != {len(memory_dirs)}"

    print("WIRING_COVERAGE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
