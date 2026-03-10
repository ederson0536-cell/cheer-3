#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure local imports work when this script is executed directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evoclaw.sqlite_memory import SQLiteMemoryStore


def iter_experience_files(experiences_dir: Path) -> list[Path]:
    if not experiences_dir.exists():
        return []
    return sorted(experiences_dir.glob("*.jsonl"))


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] {path}:{lineno} invalid json: {exc}", file=sys.stderr)
                continue
            if not isinstance(obj, dict):
                print(f"[WARN] {path}:{lineno} expected object", file=sys.stderr)
                continue
            yield obj


def run(memory_root: Path, db_path: Path) -> int:
    experiences_dir = memory_root / "experiences"
    files = iter_experience_files(experiences_dir)

    store = SQLiteMemoryStore(db_path)
    store.init_schema()

    imported = 0
    skipped = 0
    for file_path in files:
        for obj in load_jsonl(file_path):
            if not obj.get("id"):
                skipped += 1
                continue
            try:
                store.upsert_experience(obj)
                imported += 1
            except Exception as exc:
                skipped += 1
                print(
                    f"[WARN] failed to import experience id={obj.get('id')!r}: {exc}",
                    file=sys.stderr,
                )

    print(
        f"Migration finished: files={len(files)} imported={imported} skipped={skipped} db={db_path}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate memory/experiences/*.jsonl into SQLite memory.db"
    )
    parser.add_argument(
        "--memory-root",
        default="memory",
        help="Path to memory root (default: ./memory)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to sqlite db (default: <memory-root>/memory.db)",
    )
    args = parser.parse_args()

    memory_root = Path(args.memory_root).resolve()
    db_path = Path(args.db_path).resolve() if args.db_path else (memory_root / "memory.db").resolve()
    return run(memory_root, db_path)


if __name__ == "__main__":
    raise SystemExit(main())
