#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDES = {'.git', '.venv', '__pycache__'}


def load_root_registry(root: Path) -> dict[str, dict]:
    registry_path = root / 'evoclaw' / 'runtime' / 'config' / 'root_file_registry.json'
    if not registry_path.exists():
        return {}
    try:
        payload = json.loads(registry_path.read_text(encoding='utf-8'))
        return {row.get('path'): row for row in payload.get('files', []) if isinstance(row, dict) and row.get('path')}
    except Exception:
        return {}


def load_memory_directory_registry(root: Path) -> list[dict]:
    registry_path = root / 'evoclaw' / 'runtime' / 'config' / 'memory_directory_registry.json'
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding='utf-8'))
        return [row for row in payload.get('directories', []) if isinstance(row, dict) and row.get('path')]
    except Exception:
        return []


def classify(path: str, root_registry: dict[str, dict]) -> tuple[str, str, str, str, str, str, str]:
    row = root_registry.get(path)
    if row:
        return (
            row.get('file_class', 'CONTROLLED'),
            row.get('owner_domain', 'governance'),
            row.get('task_risk_level', 'medium'),
            row.get('writable_mode', 'review-only'),
            row.get('file_status', 'review_pending'),
            row.get('primary_function', ''),
            row.get('change_trigger', ''),
        )

    if path in {'SOUL.md', 'AGENTS.md'} or path.startswith('evoclaw/runtime/'):
        return ('CORE', 'system', 'high', 'review-only', 'locked', 'Runtime/core governance code.', 'Change only with reviewed runtime governance updates')
    if path.startswith('evoclaw/runtime/contracts/') or path.startswith('evoclaw/runtime/config/'):
        return ('CONTROLLED', 'contracts', 'medium', 'review-only', 'review_pending', 'Runtime contracts and policies.', 'When schema/policy contracts are revised')
    if path.startswith('docs/'):
        return ('WORKING', 'docs', 'low', 'auto', 'active', 'Documentation and reports.', 'When docs/reporting needs updates')
    if path.startswith('memory/'):
        return ('GENERATED', 'runtime-memory', 'medium', 'auto', 'active', 'Generated runtime memory artifacts.', 'Managed by runtime pipeline outputs')
    return ('WORKING', 'general', 'medium', 'auto', 'active', 'General workspace file.', 'When implementation/tasks require update')


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDES]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            yield p, rel


def load_task_count(root: Path) -> int:
    tasks_dir = root / 'memory' / 'tasks'
    if not tasks_dir.exists():
        return 0
    total = 0
    for fp in tasks_dir.glob('*.jsonl'):
        try:
            total += sum(1 for line in fp.read_text(encoding='utf-8').splitlines() if line.strip())
        except Exception:
            continue
    return total


def write_system_catalog(memory_db: Path, rows: list[dict], task_count: int, root_registry: dict[str, dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    file_counter = Counter(row['file_class'] for row in rows)

    with sqlite3.connect(memory_db) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS system_catalog (
              object_key TEXT PRIMARY KEY,
              object_type TEXT NOT NULL,
              object_count INTEGER NOT NULL DEFAULT 0,
              primary_function TEXT NOT NULL DEFAULT '',
              change_trigger TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL DEFAULT '',
              metadata_json TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT NOT NULL
            )
            '''
        )
        cur.execute('DELETE FROM system_catalog')

        summary_rows = [
            (
                'tasks.total', 'task', task_count,
                'Total task records currently indexed by runtime.',
                'Update after new task ingestion or task log compaction.',
                'memory/tasks/*.jsonl',
                json.dumps({'path': 'memory/tasks', 'count_rule': 'line_count'}, ensure_ascii=False),
                now,
            ),
            (
                'files.total', 'file', len(rows),
                'Total files indexed in file catalog.',
                'Update after repository scan or structure change.',
                'memory/file_catalog.sqlite',
                json.dumps({'path': 'workspace', 'count_rule': 'catalog_rows'}, ensure_ascii=False),
                now,
            ),
        ]

        for cls, cnt in sorted(file_counter.items()):
            summary_rows.append(
                (
                    f'files.class.{cls.lower()}', 'file', cnt,
                    f'Number of files in class {cls}.',
                    'Update when file class policy/classification changes.',
                    'memory/file_catalog.sqlite',
                    json.dumps({'file_class': cls}, ensure_ascii=False),
                    now,
                )
            )

        for path, info in sorted(root_registry.items()):
            summary_rows.append(
                (
                    f'root_file.{path}', 'file', 1,
                    info.get('primary_function', ''),
                    info.get('change_trigger', ''),
                    'evoclaw/runtime/config/root_file_registry.json',
                    json.dumps({'path': path, 'file_class': info.get('file_class')}, ensure_ascii=False),
                    now,
                )
            )

        cur.executemany(
            '''
            INSERT INTO system_catalog
            (object_key, object_type, object_count, primary_function, change_trigger, source, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            summary_rows,
        )
        conn.commit()


def write_readable_checklist(memory_db: Path, root_registry: dict[str, dict], memory_dirs: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(memory_db) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS system_readable_checklist (
              checklist_id TEXT PRIMARY KEY,
              checklist_type TEXT NOT NULL,
              target_path TEXT NOT NULL,
              purpose TEXT NOT NULL,
              when_to_change TEXT NOT NULL,
              source TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            '''
        )
        cur.execute('DELETE FROM system_readable_checklist')

        rows = []
        for path, info in sorted(root_registry.items()):
            rows.append(
                (
                    f'root_file::{path}',
                    'root_file',
                    path,
                    info.get('primary_function', ''),
                    info.get('change_trigger', ''),
                    'evoclaw/runtime/config/root_file_registry.json',
                    now,
                )
            )
        for item in memory_dirs:
            rows.append(
                (
                    f'memory_dir::{item.get("path")}',
                    'memory_directory',
                    item.get('path', ''),
                    item.get('purpose', ''),
                    item.get('when_to_change', ''),
                    'evoclaw/runtime/config/memory_directory_registry.json',
                    now,
                )
            )

        cur.executemany(
            '''
            INSERT INTO system_readable_checklist
            (checklist_id, checklist_type, target_path, purpose, when_to_change, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            rows,
        )
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description='Build file catalog sqlite db for OpenClaw governance.')
    parser.add_argument('--root', default='.', help='Repository root')
    parser.add_argument('--db', default='memory/file_catalog.sqlite', help='SQLite output path')
    parser.add_argument('--memory-db', default='memory/memory.db', help='Runtime memory db path for system catalog/checklist')
    parser.add_argument('--dry-run', action='store_true', help='Only count files and print summary')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    root_registry = load_root_registry(root)
    memory_dirs = load_memory_directory_registry(root)

    for p, rel in iter_files(root):
        fclass, domain, task_risk_level, mode, file_status, primary_function, change_trigger = classify(rel, root_registry)
        digest = file_hash(p)
        file_id = f"file_{hashlib.sha256(rel.encode('utf-8')).hexdigest()[:16]}"
        rows.append((file_id, rel, file_status, fclass, domain, task_risk_level, mode, digest, primary_function, change_trigger, 'v1', 'v1', now, now, 1))

    if args.dry_run:
        print(f'files_scanned={len(rows)}')
        return 0

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS file_catalog (
              file_id TEXT PRIMARY KEY,
              path TEXT NOT NULL UNIQUE,
              file_status TEXT NOT NULL,
              file_class TEXT NOT NULL,
              owner_domain TEXT,
              task_risk_level TEXT NOT NULL,
              writable_mode TEXT NOT NULL,
              last_hash TEXT,
              primary_function TEXT NOT NULL DEFAULT '',
              change_trigger TEXT NOT NULL DEFAULT '',
              schema_version TEXT NOT NULL,
              policy_version TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              exists_flag INTEGER NOT NULL
            )
            '''
        )
        columns = {row[1] for row in cur.execute('PRAGMA table_info(file_catalog)').fetchall()}
        if 'primary_function' not in columns:
            cur.execute("ALTER TABLE file_catalog ADD COLUMN primary_function TEXT NOT NULL DEFAULT ''")
        if 'change_trigger' not in columns:
            cur.execute("ALTER TABLE file_catalog ADD COLUMN change_trigger TEXT NOT NULL DEFAULT ''")
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_class ON file_catalog(file_class)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_mode ON file_catalog(writable_mode)')
        cur.execute('DELETE FROM file_catalog')
        cur.executemany(
            '''
            INSERT INTO file_catalog
            (file_id, path, file_status, file_class, owner_domain, task_risk_level, writable_mode, last_hash, primary_function, change_trigger, schema_version, policy_version, created_at, updated_at, exists_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    memory_db = Path(args.memory_db)
    memory_db.parent.mkdir(parents=True, exist_ok=True)
    simple_rows = [{'path': row[1], 'file_class': row[3]} for row in rows]
    write_system_catalog(memory_db, simple_rows, load_task_count(root), root_registry)
    write_readable_checklist(memory_db, root_registry, memory_dirs)

    print(f'catalog_written={db_path} files={len(rows)} system_catalog={memory_db}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
