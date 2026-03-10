#!/usr/bin/env python3
"""
EvoClaw Experience Validator (SQLite-first).

Usage:
  python3 evoclaw/validators/validate_experience.py <db_or_jsonl> [--config evoclaw/config.json] [--date YYYY-MM-DD]
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

VALID_SIGNIFICANCE = {"routine", "notable", "pivotal"}
BUILTIN_SOURCES = {"conversation", "moltbook", "x", "heartbeat", "flush_harvest", "other"}
LEGACY_ID_PATTERN = re.compile(r"^EXP-\d{8}-\d{4}$")
MODERN_ID_PATTERN = re.compile(r"^exp-[a-f0-9]{16}$")


def load_config_sources(config_path):
    extra = set()
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            for key in cfg.get("sources", {}):
                extra.add(key)
        except Exception:
            pass
    return BUILTIN_SOURCES | extra


def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_db_path(path):
    return str(path).endswith(".db")


def _load_rows_from_db(db_path, date_filter=None):
    rows = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        params = []
        where = ""
        if date_filter:
            start = datetime.fromisoformat(f"{date_filter}T00:00:00")
            end = start + timedelta(days=1)
            where = "WHERE created_at >= ? AND created_at < ?"
            params.extend([start.isoformat(), end.isoformat()])
        sql = (
            "SELECT id, type, content, source, created_at, updated_at, significance, raw_json "
            f"FROM experiences {where} ORDER BY created_at DESC, id DESC LIMIT 50000"
        )
        for row in conn.execute(sql, params).fetchall():
            entry = {}
            if row["raw_json"]:
                try:
                    raw = json.loads(row["raw_json"])
                    if isinstance(raw, dict):
                        entry = dict(raw)
                except Exception:
                    entry = {}
            entry.setdefault("id", row["id"])
            entry.setdefault("type", row["type"])
            entry.setdefault("content", row["content"])
            entry.setdefault("source", row["source"])
            entry.setdefault("created_at", row["created_at"])
            entry.setdefault("updated_at", row["updated_at"])
            entry.setdefault("timestamp", row["created_at"])
            entry.setdefault("significance", row["significance"] or "routine")
            rows.append(entry)
    return rows


def _load_rows_from_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if isinstance(entry, dict):
                    entry["_line_num"] = line_num
                    rows.append(entry)
            except json.JSONDecodeError:
                rows.append({"_parse_error": f"Invalid JSON at line {line_num}", "_line_num": line_num})
    return rows


def validate(target, config_path=None, date_filter=None):
    errors = []
    warnings = []
    valid_sources = load_config_sources(config_path)
    seen_ids = set()

    if not os.path.exists(target):
        return {
            "status": "FAIL",
            "file": target,
            "errors": [{"line": None, "field": None, "message": f"Input not found: {target}"}],
            "warnings": [],
            "stats": {},
        }

    rows = _load_rows_from_db(target, date_filter) if _is_db_path(target) else _load_rows_from_jsonl(target)

    notable_pivotal_ids = []
    for idx, entry in enumerate(rows, 1):
        line_num = entry.get("_line_num", idx)
        if entry.get("_parse_error"):
            errors.append({"line": line_num, "field": None, "message": entry["_parse_error"]})
            continue

        eid = str(entry.get("id") or "")
        if not eid:
            errors.append({"line": line_num, "field": "id", "message": "Missing id"})
        elif not (LEGACY_ID_PATTERN.match(eid) or MODERN_ID_PATTERN.match(eid) or eid.startswith("experience-")):
            warnings.append({"line": line_num, "message": f"Unrecognized id format: {eid}"})
        if eid in seen_ids:
            errors.append({"line": line_num, "field": "id", "message": f"Duplicate ID: {eid}"})
        seen_ids.add(eid)

        ts = entry.get("timestamp") or entry.get("created_at")
        dt = parse_iso(ts)
        if ts and dt is None:
            errors.append({"line": line_num, "field": "timestamp", "message": f"Invalid ISO-8601 timestamp: {ts}"})
        elif dt and dt.tzinfo and dt > datetime.now(timezone.utc):
            warnings.append({"line": line_num, "message": f"Timestamp is in the future: {ts}"})

        source = str(entry.get("source") or "")
        if not source:
            errors.append({"line": line_num, "field": "source", "message": "source is required"})
        elif source not in valid_sources and "://" not in source:
            warnings.append({"line": line_num, "message": f"Unknown source '{source}' (accepted as custom source)"})

        sig = str(entry.get("significance") or "")
        if sig and sig not in VALID_SIGNIFICANCE:
            errors.append({"line": line_num, "field": "significance", "message": f"Invalid significance: {sig}"})
        if sig in {"notable", "pivotal"}:
            notable_pivotal_ids.append(eid)

        content = entry.get("content", "")
        if not isinstance(content, str) or not content.strip():
            errors.append({"line": line_num, "field": "content", "message": "Content is empty"})

    status = "FAIL" if errors else "PASS"
    return {
        "status": status,
        "file": target,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "total_entries": len(rows),
            "unique_ids": len(seen_ids),
            "notable_pivotal_count": len(notable_pivotal_ids),
            "notable_pivotal_ids": notable_pivotal_ids,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_experience.py <db_or_jsonl> [--config config.json] [--date YYYY-MM-DD]", file=sys.stderr)
        sys.exit(2)

    target = sys.argv[1]
    config_path = None
    date_filter = None
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            config_path = sys.argv[idx + 1]
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            date_filter = sys.argv[idx + 1]

    result = validate(target, config_path, date_filter)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] == "PASS" else 1)
