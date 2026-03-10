#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDES = {'.git', '.venv', '__pycache__'}


def classify(path: str) -> tuple[str, str, str, str]:
    if path in {'SOUL.md', 'AGENTS.md'} or path.startswith('evoclaw/runtime/'):
        return ('CORE', 'system', 'high', 'review-only')
    if path.startswith('evoclaw/runtime/contracts/') or path.startswith('evoclaw/runtime/config/'):
        return ('CONTROLLED', 'contracts', 'medium', 'review-only')
    if path.startswith('docs/'):
        return ('WORKING', 'docs', 'low', 'auto')
    return ('WORKING', 'general', 'medium', 'auto')


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
        fclass, domain, risk, mode = classify(rel)
        digest = file_hash(p)
        rows.append((rel, fclass, domain, risk, mode, digest, now, 1))

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
              path TEXT PRIMARY KEY,
              file_class TEXT NOT NULL,
              owner_domain TEXT,
              risk_level TEXT NOT NULL,
              writable_mode TEXT NOT NULL,
              last_hash TEXT,
              last_indexed_at TEXT NOT NULL,
              exists_flag INTEGER NOT NULL
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_class ON file_catalog(file_class)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_file_catalog_mode ON file_catalog(writable_mode)')
        cur.execute('DELETE FROM file_catalog')
        cur.executemany('''
            INSERT INTO file_catalog
            (path, file_class, owner_domain, risk_level, writable_mode, last_hash, last_indexed_at, exists_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        conn.commit()
    finally:
        conn.close()

    print(f'catalog_written={db_path} files={len(rows)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
