#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDES = {'.git', '.venv', '__pycache__'}


def classify(path: str) -> tuple[str, str, str, str, str]:
    if path in {'SOUL.md', 'AGENTS.md'} or path.startswith('evoclaw/runtime/'):
        return ('CORE', 'system', 'high', 'review-only', 'locked')
    if path.startswith('evoclaw/runtime/contracts/') or path.startswith('evoclaw/runtime/config/'):
        return ('CONTROLLED', 'contracts', 'medium', 'review-only', 'review_pending')
    if path.startswith('docs/'):
        return ('WORKING', 'docs', 'low', 'auto', 'active')
    return ('WORKING', 'general', 'medium', 'auto', 'active')


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


def main() -> int:
    parser = argparse.ArgumentParser(description='Build file catalog sqlite db for OpenClaw governance.')
    parser.add_argument('--root', default='.', help='Repository root')
    parser.add_argument('--db', default='memory/file_catalog.sqlite', help='SQLite output path')
    parser.add_argument('--dry-run', action='store_true', help='Only count files and print summary')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = []
    now = datetime.now(timezone.utc).isoformat()

    for p, rel in iter_files(root):
        fclass, domain, task_risk_level, mode, file_status = classify(rel)
        digest = file_hash(p)
        path_digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()
        file_id = f"file_{path_digest[:24]}"
        rows.append((file_id, rel, file_status, fclass, domain, task_risk_level, mode, digest, 'v1', 'v1', now, now, 1))

    if args.dry_run:
        print(f'files_scanned={len(rows)}')
        return 0

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS file_catalog (
              file_id TEXT PRIMARY KEY,
              path TEXT NOT NULL UNIQUE,
              file_status TEXT NOT NULL,
              file_class TEXT NOT NULL,
              owner_domain TEXT,
              task_risk_level TEXT NOT NULL,
              writable_mode TEXT NOT NULL,
              last_hash TEXT,
              schema_version TEXT NOT NULL,
              policy_version TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              exists_flag INTEGER NOT NULL
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_class ON file_catalog(file_class)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_mode ON file_catalog(writable_mode)')
        cur.execute('DELETE FROM file_catalog')
        cur.executemany('''
            INSERT INTO file_catalog
            (file_id, path, file_status, file_class, owner_domain, task_risk_level, writable_mode, last_hash, schema_version, policy_version, created_at, updated_at, exists_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        conn.commit()
    finally:
        conn.close()

    print(f'catalog_written={db_path} files={len(rows)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
