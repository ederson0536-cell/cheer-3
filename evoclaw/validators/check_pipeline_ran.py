#!/usr/bin/env python3
"""
EvoClaw Pipeline Completeness Checker (DB-first).

Usage:
  python3 evoclaw/validators/check_pipeline_ran.py <memory_dir> [--since-minutes 30]

Checks:
  1. memory.db exists and was modified recently
  2. notable/pivotal counts for today are queryable from DB
  3. reflections/proposals/state have expected freshness
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, date, timedelta, timezone


def file_modified_since(filepath, cutoff_dt):
    if not os.path.exists(filepath):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
    return mtime > cutoff_dt


def last_modified(filepath):
    if not os.path.exists(filepath):
        return 'DOES NOT EXIST'
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
    return mtime.isoformat()


def _count_significance_today(db_path, sig_level, start_iso, end_iso):
    if not os.path.exists(db_path):
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM memories
            WHERE significance = ? AND created_at >= ? AND created_at < ?
            """,
            (sig_level, start_iso, end_iso),
        ).fetchone()
    return int(row[0]) if row else 0


def _count_recent_reflections(db_path, cutoff_iso):
    if not os.path.exists(db_path):
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM reflections WHERE created_at >= ?",
            (cutoff_iso,),
        ).fetchone()
    return int(row[0]) if row else 0


def _count_pending_proposals(db_path):
    if not os.path.exists(db_path):
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE status = 'pending'"
        ).fetchone()
    return int(row[0]) if row else 0


def validate(memory_dir, since_minutes=30):
    errors = []
    warnings = []
    findings = {}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=since_minutes)
    today = date.today()
    start_iso = datetime.combine(today, datetime.min.time()).isoformat()
    end_iso = (datetime.combine(today, datetime.min.time()) + timedelta(days=1)).isoformat()

    db_path = os.path.join(memory_dir, 'memory.db')

    # 1. Canonical DB write happened
    if not os.path.exists(db_path):
        errors.append({
            'check': 'memory_db',
            'message': f"Canonical DB missing: {db_path}. Runtime must write to memory.db.",
        })
        findings['memory_db'] = 'MISSING'
    else:
        findings['memory_db'] = last_modified(db_path)
        if not file_modified_since(db_path, cutoff):
            warnings.append({
                'check': 'memory_db',
                'message': f"memory.db exists but wasn't modified in the last {since_minutes}m. Last modified: {last_modified(db_path)}",
            })

    # 2. Significance coverage from DB
    notable_count = _count_significance_today(db_path, 'notable', start_iso, end_iso)
    pivotal_count = _count_significance_today(db_path, 'pivotal', start_iso, end_iso)
    findings['notable_today'] = notable_count
    findings['pivotal_today'] = pivotal_count

    # 3. Reflection activity signal
    cutoff_iso = cutoff.replace(tzinfo=None).isoformat()
    recent_reflections = _count_recent_reflections(db_path, cutoff_iso)
    findings['recent_reflections'] = recent_reflections
    if (notable_count + pivotal_count) > 0 and recent_reflections == 0:
        warnings.append({
            'check': 'reflection_activity',
            'message': f"Found {notable_count} notable + {pivotal_count} pivotal today, but no reflection row in last {since_minutes}m.",
        })

    # 4. State freshness
    state_file = os.path.join(memory_dir, 'evoclaw-state.json')
    findings['state_file'] = last_modified(state_file)
    if not os.path.exists(state_file):
        errors.append({'check': 'state_file', 'message': f"Missing state file: {state_file}"})
    elif not file_modified_since(state_file, cutoff):
        warnings.append({
            'check': 'state_file',
            'message': f"State file not updated in last {since_minutes}m. Last modified: {last_modified(state_file)}",
        })

    # 5. Pending proposal consistency (state vs DB)
    pending_in_db = _count_pending_proposals(db_path)
    findings['pending_in_db'] = pending_in_db
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            claimed_pending = state.get('pending_proposals', 0)
            findings['claimed_pending'] = claimed_pending
            if isinstance(claimed_pending, int) and claimed_pending != pending_in_db:
                warnings.append({
                    'check': 'pending_proposals',
                    'message': f"state.pending_proposals={claimed_pending} but DB has {pending_in_db} pending proposals",
                })
        except Exception:
            warnings.append({'check': 'state_file', 'message': 'Could not parse state file JSON'})

    status = 'FAIL' if errors else 'PASS'
    return {
        'status': status,
        'file': memory_dir,
        'checked_at': now.isoformat(),
        'since_minutes': since_minutes,
        'errors': errors,
        'warnings': warnings,
        'findings': findings,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: check_pipeline_ran.py <memory_dir> [--since-minutes 30]', file=sys.stderr)
        sys.exit(2)

    memory_dir = sys.argv[1]
    since_minutes = 30
    if '--since-minutes' in sys.argv:
        idx = sys.argv.index('--since-minutes')
        if idx + 1 < len(sys.argv):
            try:
                since_minutes = int(sys.argv[idx + 1])
            except ValueError:
                pass

    result = validate(memory_dir, since_minutes)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result['status'] == 'PASS' else 1)
