#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TARGET_DIRS = ("experiences", "significant", "semantic", "candidate", "proposals")
CANONICAL_FIELDS = (
    "id",
    "type",
    "content",
    "source",
    "created_at",
    "updated_at",
    "tags",
    "metadata",
)


@dataclass
class FileResult:
    path: str
    records: int
    changed: bool
    errors: int


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def first_non_empty(record: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def normalize_tags(record: dict) -> list[str]:
    tags: list[str] = []
    candidates = [record.get("tags"), record.get("context", {}).get("tags") if isinstance(record.get("context"), dict) else None]
    for raw in candidates:
        if isinstance(raw, list):
            tags.extend(str(item).strip() for item in raw if str(item).strip())
        elif isinstance(raw, str) and raw.strip():
            tags.extend(part.strip() for part in raw.split(",") if part.strip())
    for extra_key in ("significance", "status"):
        raw = record.get(extra_key)
        if isinstance(raw, str) and raw.strip():
            tags.append(raw.strip())
    deduped: list[str] = []
    seen = set()
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return deduped


def choose_type(record: dict, directory: str) -> str:
    chosen = first_non_empty(record, ("type", "status", "significance", "category"))
    if chosen:
        return chosen
    return f"{directory}_entry"


def choose_content(record: dict) -> str:
    chosen = first_non_empty(
        record,
        (
            "content",
            "message",
            "summary",
            "knowledge",
            "title",
            "description",
            "proposed_change",
            "current_content",
            "outcome",
        ),
    )
    if chosen:
        return chosen
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def choose_source(record: dict, directory: str) -> str:
    source = record.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    if isinstance(source, (dict, list)):
        return json.dumps(source, ensure_ascii=False, sort_keys=True)
    return directory


def choose_id(record: dict, directory: str, relative_path: str, line_no: int) -> str:
    existing = first_non_empty(
        record,
        ("id", "candidate_id", "task_id", "proposal_id", "reflection_id", "source_id"),
    )
    if existing:
        return existing
    digest = hashlib.sha1(
        f"{directory}:{relative_path}:{line_no}:{json.dumps(record, ensure_ascii=False, sort_keys=True)}".encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    return f"{directory}-{digest}"


def choose_created_at(record: dict) -> str:
    created = first_non_empty(
        record,
        ("created_at", "timestamp", "promoted_at", "applied_at", "approved_at", "resolved_at"),
    )
    return created or iso_now()


def choose_updated_at(record: dict, created_at: str) -> str:
    updated = first_non_empty(record, ("updated_at", "modified_at", "resolved_at", "applied_at", "approved_at"))
    return updated or created_at


def canonicalize(record: dict, directory: str, relative_path: str, line_no: int) -> dict:
    created_at = choose_created_at(record)
    normalized = {
        "id": choose_id(record, directory, relative_path, line_no),
        "type": choose_type(record, directory),
        "content": choose_content(record),
        "source": choose_source(record, directory),
        "created_at": created_at,
        "updated_at": choose_updated_at(record, created_at),
        "tags": normalize_tags(record),
        "metadata": {
            key: value
            for key, value in record.items()
            if key not in CANONICAL_FIELDS
        },
    }
    return normalized


def parse_jsonl(path: Path) -> tuple[list[dict], int]:
    records: list[dict] = []
    errors = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            records.append({"value": payload})
    return records, errors


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def convert_file(memory_root: Path, path: Path, apply_changes: bool) -> FileResult:
    relative = path.relative_to(memory_root).as_posix()
    directory = relative.split("/", 1)[0]
    if path.suffix != ".jsonl":
        return FileResult(path=relative, records=0, changed=False, errors=0)

    source_rows, errors = parse_jsonl(path)
    converted_rows = [
        canonicalize(row, directory, relative, line_no=index)
        for index, row in enumerate(source_rows, start=1)
    ]
    changed = converted_rows != source_rows
    if apply_changes and changed:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        dump_jsonl(path, converted_rows)
    return FileResult(path=relative, records=len(source_rows), changed=changed, errors=errors)


def iter_target_files(memory_root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in TARGET_DIRS:
        root = memory_root / directory
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def run(memory_root: Path, apply_changes: bool) -> dict:
    memory_root = memory_root.resolve()
    results: list[FileResult] = []
    for path in iter_target_files(memory_root):
        results.append(convert_file(memory_root, path, apply_changes))
    return {
        "memory_root": str(memory_root),
        "dry_run": not apply_changes,
        "files_scanned": len(results),
        "files_changed": sum(1 for item in results if item.changed),
        "records_converted": sum(item.records for item in results),
        "parse_errors": sum(item.errors for item in results),
        "details": [item.__dict__ for item in results if item.records or item.errors],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Unify EvoClaw memory JSONL records to one schema.")
    parser.add_argument("--memory-root", default="memory", help="Memory root directory. Default: ./memory")
    parser.add_argument("--apply", action="store_true", help="Write converted records back to disk.")
    args = parser.parse_args()

    summary = run(Path(args.memory_root), args.apply)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
