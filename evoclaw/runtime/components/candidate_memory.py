#!/usr/bin/env python3
"""
Candidate Memory System
SQLite-first implementation with legacy JSONL fallback.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Any, Dict, List, Optional

try:
    from evoclaw.sqlite_memory import SQLiteMemoryStore
except ModuleNotFoundError:
    WORKSPACE_ROOT = resolve_workspace(__file__)
    if str(WORKSPACE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_ROOT))
    from evoclaw.sqlite_memory import SQLiteMemoryStore

WORKSPACE = resolve_workspace(__file__)
CANDIDATE_PATH = WORKSPACE / "memory" / "candidate"
SEMANTIC_PATH = WORKSPACE / "memory" / "semantic"
MEMORY_DB = WORKSPACE / "memory" / "memory.db"


class CandidateMemory:
    """Candidate Memory Manager"""

    def __init__(self):
        CANDIDATE_PATH.mkdir(parents=True, exist_ok=True)
        SEMANTIC_PATH.mkdir(parents=True, exist_ok=True)

        self.candidates_file = CANDIDATE_PATH / "candidates.jsonl"
        self.validations_file = CANDIDATE_PATH / "validations.jsonl"
        self.store = SQLiteMemoryStore(MEMORY_DB)
        self.store.init_schema()

        if not self.candidates_file.exists():
            self.candidates_file.touch()
        if not self.validations_file.exists():
            self.validations_file.touch()

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _candidate_from_db_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}

        candidate_id = row.get("id") or raw.get("candidate_id") or metadata.get("candidate_id")
        knowledge = raw.get("knowledge") or metadata.get("knowledge") or ""
        context = raw.get("context") or metadata.get("context") or {}
        validations = raw.get("validations") or metadata.get("validations") or []
        occurrences = raw.get("occurrences") or metadata.get("occurrences")
        if occurrences is None:
            occurrences = max(1, len(validations))

        return {
            "candidate_id": candidate_id,
            "id": row.get("id"),
            "knowledge": knowledge,
            "context": context if isinstance(context, dict) else {},
            "validations": validations if isinstance(validations, list) else [],
            "occurrences": int(occurrences),
            "status": row.get("status", "candidate"),
            "source": row.get("source", ""),
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
            "skill_id": row.get("skill_id", ""),
            "task_type": row.get("task_type", ""),
            "score": float(row.get("score", 0) or 0),
            "metadata": metadata,
            "raw": raw,
        }

    def _legacy_candidates(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not self.candidates_file.exists():
            return results

        with open(self.candidates_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    continue
        return results

    def _persist_legacy_candidate(self, candidate: Dict[str, Any]) -> None:
        with open(self.candidates_file, "a") as f:
            f.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    def add_candidate(self, knowledge: str, source: str, context: Dict = None) -> str:
        """Add a new knowledge candidate"""
        now = self._now()
        candidate_id = f"cand_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ctx = context or {}

        candidate = {
            "candidate_id": candidate_id,
            "knowledge": knowledge,
            "source": source,
            "context": ctx,
            "status": "validating",
            "occurrences": 1,
            "validations": [],
            "created_at": now,
            "updated_at": now,
        }

        payload = {
            "id": candidate_id,
            "skill_id": str(ctx.get("skill_id") or ""),
            "task_type": str(ctx.get("task_type") or ""),
            "status": "validating",
            "source": source,
            "score": float(ctx.get("score") or 0),
            "created_at": now,
            "updated_at": now,
            "metadata": {
                "candidate_id": candidate_id,
                "knowledge": knowledge,
                "context": ctx,
                "occurrences": 1,
                "validations": [],
            },
            "raw": candidate,
        }
        self.store.upsert_candidate(payload)
        self._persist_legacy_candidate(candidate)
        return candidate_id

    def _save_candidate(self, candidate: Dict[str, Any]) -> None:
        now = self._now()
        context = candidate.get("context") if isinstance(candidate.get("context"), dict) else {}
        validations = candidate.get("validations") if isinstance(candidate.get("validations"), list) else []
        payload = {
            "id": candidate.get("candidate_id") or candidate.get("id"),
            "skill_id": str(candidate.get("skill_id") or context.get("skill_id") or ""),
            "task_type": str(candidate.get("task_type") or context.get("task_type") or ""),
            "status": str(candidate.get("status") or "candidate"),
            "source": str(candidate.get("source") or ""),
            "score": float(candidate.get("score") or 0),
            "created_at": str(candidate.get("created_at") or now),
            "updated_at": str(candidate.get("updated_at") or now),
            "metadata": {
                "candidate_id": candidate.get("candidate_id") or candidate.get("id"),
                "knowledge": candidate.get("knowledge", ""),
                "context": context,
                "occurrences": int(candidate.get("occurrences") or 1),
                "validations": validations,
            },
            "raw": candidate,
        }
        self.store.upsert_candidate(payload)

    def _get_candidate_by_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        rows = self.store.query_candidates(limit=2000)
        for row in rows:
            mapped = self._candidate_from_db_row(row)
            if mapped["candidate_id"] == candidate_id:
                return mapped

        for row in self._legacy_candidates():
            if row.get("candidate_id") == candidate_id:
                return row
        return None

    def record_validation(
        self,
        candidate_id: str,
        task_id: str,
        success: bool,
        feedback: str = None,
    ) -> bool:
        """Record validation result for a candidate"""
        validation = {
            "candidate_id": candidate_id,
            "task_id": task_id,
            "success": success,
            "feedback": feedback,
            "validated_at": self._now(),
        }

        with open(self.validations_file, "a") as f:
            f.write(json.dumps(validation, ensure_ascii=False) + "\n")

        self._update_candidate_validation(candidate_id, success)
        return True

    def _update_candidate_validation(self, candidate_id: str, success: bool):
        candidate = self._get_candidate_by_id(candidate_id)
        if not candidate:
            return

        validations = candidate.get("validations", [])
        validations.append({"success": success, "validated_at": self._now()})

        candidate["validations"] = validations
        candidate["occurrences"] = int(candidate.get("occurrences") or 0) + 1
        candidate["updated_at"] = self._now()

        if self._check_promotion_ready(candidate):
            candidate["status"] = "validated"

        self._save_candidate(candidate)

    def _check_promotion_ready(self, candidate: Dict) -> bool:
        validations = candidate.get("validations", [])
        if len(validations) < 3:
            return False

        success_count = sum(1 for v in validations if v.get("success"))
        success_rate = success_count / len(validations)
        return success_rate >= 0.7

    def get_candidates(
        self,
        status: str = None,
        task_type: str = None,
        min_score: float = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get candidates from SQLite, fallback to legacy JSONL."""
        rows = self.store.query_candidates(
            status=status,
            task_type=task_type,
            min_score=min_score,
            limit=limit,
        )
        mapped = [self._candidate_from_db_row(r) for r in rows]
        if mapped:
            return mapped

        legacy = self._legacy_candidates()
        result = []
        for c in legacy:
            if status is not None and c.get("status") != status:
                continue
            if task_type is not None and c.get("task_type") != task_type:
                continue
            if min_score is not None:
                try:
                    if float(c.get("score") or 0) < float(min_score):
                        continue
                except (TypeError, ValueError):
                    continue
            result.append(c)
        return result[:limit]

    def promote_to_semantic(self, candidate_id: str) -> bool:
        """Promote validated candidate to semantic memory"""
        candidate = self._get_candidate_by_id(candidate_id)
        if not candidate:
            return False
        if candidate.get("status") not in {"validated", "validating"}:
            return False

        semantic_entry = {
            "type": "knowledge",
            "content": candidate.get("knowledge", ""),
            "source": candidate.get("source", ""),
            "promoted_from": candidate_id,
            "promoted_at": self._now(),
            "validation_count": len(candidate.get("validations", [])),
        }

        semantic_file = SEMANTIC_PATH / f"{datetime.now().strftime('%Y-%m')}.jsonl"
        with open(semantic_file, "a") as f:
            f.write(json.dumps(semantic_entry, ensure_ascii=False) + "\n")

        candidate["status"] = "promoted"
        candidate["promoted_at"] = self._now()
        candidate["updated_at"] = self._now()
        self._save_candidate(candidate)
        return True

    def reject_candidate(self, candidate_id: str, reason: str) -> bool:
        """Reject a candidate"""
        candidate = self._get_candidate_by_id(candidate_id)
        if not candidate:
            return False

        candidate["status"] = "rejected"
        candidate["reject_reason"] = reason
        candidate["rejected_at"] = self._now()
        candidate["updated_at"] = self._now()
        self._save_candidate(candidate)
        return True

    def get_promotion_candidates(self) -> List[Dict]:
        """Get candidates ready for promotion"""
        return [
            c for c in self.get_candidates(status="validated", limit=1000)
            if len(c.get("validations", [])) >= 3
        ]

    def get_stats(self) -> Dict:
        """Get candidate memory statistics"""
        stats = {
            "total": 0,
            "by_status": defaultdict(int),
            "ready_for_promotion": 0,
        }

        for c in self.get_candidates(limit=2000):
            stats["total"] += 1
            stats["by_status"][c.get("status", "unknown")] += 1
            if c.get("status") == "validated":
                stats["ready_for_promotion"] += 1

        stats["by_status"] = dict(stats["by_status"])
        return stats

    def add_validation(self, candidate_id: str, success: bool, details: str = ""):
        """Compatibility wrapper used by ActiveLearning."""
        self.record_validation(
            candidate_id=candidate_id,
            task_id=f"validation-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            success=success,
            feedback=details,
        )


_candidate_memory = None


def get_candidate_memory() -> CandidateMemory:
    """Get global candidate memory instance"""
    global _candidate_memory
    if _candidate_memory is None:
        _candidate_memory = CandidateMemory()
    return _candidate_memory


if __name__ == "__main__":
    import sys

    cm = get_candidate_memory()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "stats":
            print(json.dumps(cm.get_stats(), indent=2, ensure_ascii=False))

        elif cmd == "list":
            status = sys.argv[2] if len(sys.argv) > 2 else None
            for c in cm.get_candidates(status=status, limit=200):
                cid = c.get("candidate_id")
                skill = c.get("skill_id") or "unknown"
                print(f"- {cid}: skill={skill} task={c.get('task_type')} score={c.get('score')} [{c.get('status')}]")

        elif cmd == "promote" and len(sys.argv) > 2:
            ok = cm.promote_to_semantic(sys.argv[2])
            print(f"Promoted: {sys.argv[2]} => {ok}")
    else:
        print("Usage: candidate_memory.py stats|list|promote <id>")
