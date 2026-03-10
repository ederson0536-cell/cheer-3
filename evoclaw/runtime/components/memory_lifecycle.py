#!/usr/bin/env python3
"""
Week4 Memory Lifecycle
- ingest dedup + schema migration guard
- promotion guard (candidate cannot direct active)
- retention/archive skeleton
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)
MEMORY_DIR = WORKSPACE / "memory"
INGEST_DIR = MEMORY_DIR / "ingest"
ARCHIVE_DIR = MEMORY_DIR / "archive"


class MemoryLifecycle:
    def __init__(self):
        INGEST_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        self.events_file = INGEST_DIR / "events.jsonl"
        self.meta_file = INGEST_DIR / "ingest_meta.json"

        if not self.events_file.exists():
            self.events_file.touch()
        if not self.meta_file.exists():
            self._save_meta({"last_schema_version": "v1", "total_events": 0, "dedup_hits": 0})

    def _load_meta(self) -> Dict[str, Any]:
        try:
            with open(self.meta_file) as f:
                return json.load(f)
        except Exception:
            return {"last_schema_version": "v1", "total_events": 0, "dedup_hits": 0}

    def _save_meta(self, payload: Dict[str, Any]):
        payload["updated_at"] = datetime.now().isoformat()
        with open(self.meta_file, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _fingerprint(self, record: Dict[str, Any]) -> str:
        parts = [
            str(record.get("task_id", "")),
            str(record.get("subtask_id", "")),
            str(record.get("record_type", "")),
            str(record.get("content", ""))[:180],
        ]
        return "|".join(parts).strip().lower()

    def _iter_events(self):
        if not self.events_file.exists():
            return
        with open(self.events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def _schema_guard(self, record: Dict[str, Any]) -> tuple[bool, str]:
        schema_version = str(record.get("schema_version") or "v1")
        allowed = {"v1", "v2"}
        if schema_version not in allowed:
            return False, f"unsupported schema_version={schema_version}"

        # migration guard: v1 payloads need a minimum normalized shape
        if schema_version == "v1":
            if "record_type" not in record:
                return False, "missing record_type for schema v1"
        return True, ""

    def ingest(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append-only ingest with dedup + schema migration guard."""

        ok, reason = self._schema_guard(record)
        if not ok:
            return {"accepted": False, "reason": reason}

        fp = self._fingerprint(record)
        for existing in self._iter_events() or []:
            if existing.get("dedup_fingerprint") == fp:
                meta = self._load_meta()
                meta["dedup_hits"] = int(meta.get("dedup_hits", 0)) + 1
                self._save_meta(meta)
                return {
                    "accepted": True,
                    "deduped": True,
                    "event_id": existing.get("event_id"),
                }

        event_id = f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        entry = {
            "event_id": event_id,
            "record_type": record.get("record_type", "raw"),
            "memory_status": record.get("memory_status", "raw"),
            "schema_version": record.get("schema_version", "v1"),
            "policy_version": record.get("policy_version", "v1"),
            "task_id": record.get("task_id"),
            "subtask_id": record.get("subtask_id"),
            "content": record.get("content", ""),
            "source_hook": record.get("source_hook", "after_task"),
            "created_at": datetime.now().isoformat(),
            "dedup_fingerprint": fp,
            "raw": record,
        }

        with open(self.events_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        meta = self._load_meta()
        meta["total_events"] = int(meta.get("total_events", 0)) + 1
        meta["last_schema_version"] = entry["schema_version"]
        self._save_meta(meta)

        return {"accepted": True, "deduped": False, "event_id": event_id}

    def promotion_guard(self, source_status: str, target_status: str, reviewed: bool, confidence: float) -> Dict[str, Any]:
        """Guard promotion path. Candidate cannot direct active/semantic without review+threshold."""

        source = str(source_status or "").lower()
        target = str(target_status or "").lower()
        if source == "candidate" and target in {"active", "semantic"}:
            if (not reviewed) or float(confidence or 0) < 0.8:
                return {
                    "allowed": False,
                    "reason": "candidate promotion requires review=true and confidence>=0.8",
                }

        return {"allowed": True, "reason": "ok"}

    def run_retention(self, now: datetime | None = None) -> Dict[str, Any]:
        """Minimal retention/archive skeleton for Week4."""

        now = now or datetime.now()
        archived = 0

        # working/buffer expiration: move old files to archive snapshot
        for folder in [MEMORY_DIR / "working", MEMORY_DIR / "buffer"]:
            if not folder.exists():
                continue
            target = ARCHIVE_DIR / folder.name / now.strftime("%Y-%m-%d")
            target.mkdir(parents=True, exist_ok=True)
            for file_path in folder.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    age_hours = (now - mtime).total_seconds() / 3600.0
                    if age_hours >= 24:
                        file_path.rename(target / file_path.name)
                        archived += 1
                except Exception:
                    continue

        # recovery notes archive skeleton (copy monthly snapshot)
        recovery_dir = MEMORY_DIR / "recovery"
        if recovery_dir.exists():
            monthly = ARCHIVE_DIR / "recovery" / now.strftime("%Y-%m")
            monthly.mkdir(parents=True, exist_ok=True)
            for name in ["issues.jsonl", "solutions.jsonl"]:
                src = recovery_dir / name
                if src.exists():
                    dst = monthly / name
                    if not dst.exists():
                        dst.write_text(src.read_text())

        return {
            "retention_ran_at": now.isoformat(),
            "archived_files": archived,
            "append_only_event_preserved": True,
        }


_memory_lifecycle = None


def get_memory_lifecycle() -> MemoryLifecycle:
    global _memory_lifecycle
    if _memory_lifecycle is None:
        _memory_lifecycle = MemoryLifecycle()
    return _memory_lifecycle


if __name__ == "__main__":
    lifecycle = get_memory_lifecycle()
    print(json.dumps(lifecycle.run_retention(), ensure_ascii=False, indent=2))
