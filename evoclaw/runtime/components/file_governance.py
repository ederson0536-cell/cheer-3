#!/usr/bin/env python3
"""Week5 file governance utilities.

- file catalog refresh
- catalog_precheck(file_scope)
- catalog_enforce(path, mode)
- patch-first transactional apply
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)
CATALOG_DB = WORKSPACE / "memory" / "file_catalog.sqlite"
ROOT_FILE_REGISTRY = WORKSPACE / "evoclaw" / "runtime" / "config" / "root_file_registry.json"
DEFAULT_EXCLUDES = {".git", ".venv", "__pycache__"}


class FileGovernance:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or CATALOG_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_file = WORKSPACE / "memory" / "governance" / "file_ops_audit.jsonl"
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        self.root_file_registry = self._load_root_file_registry()

    def _load_root_file_registry(self) -> dict[str, dict]:
        if not ROOT_FILE_REGISTRY.exists():
            return {}
        try:
            payload = json.loads(ROOT_FILE_REGISTRY.read_text(encoding="utf-8"))
            files = payload.get("files", [])
            return {item.get("path"): item for item in files if isinstance(item, dict) and item.get("path")}
        except Exception:
            return {}

    def _classify(self, rel_path: str) -> tuple[str, str, str, str, str, str, str]:
        root_row = self.root_file_registry.get(rel_path)
        if root_row:
            return (
                root_row.get("file_class", "CONTROLLED"),
                root_row.get("owner_domain", "governance"),
                root_row.get("task_risk_level", "medium"),
                root_row.get("writable_mode", "review-only"),
                root_row.get("file_status", "review_pending"),
                root_row.get("primary_function", ""),
                root_row.get("change_trigger", ""),
            )

        if rel_path in {"SOUL.md", "AGENTS.md"} or rel_path.startswith("evoclaw/runtime/"):
            return ("CORE", "system", "high", "review-only", "locked", "Runtime/core governance code.", "Change only with reviewed runtime governance updates")
        if rel_path.startswith("evoclaw/runtime/contracts/") or rel_path.startswith("evoclaw/runtime/config/"):
            return ("CONTROLLED", "contracts", "medium", "review-only", "review_pending", "Runtime contracts and policies.", "When schema/policy contracts are revised")
        if rel_path.startswith("docs/"):
            return ("WORKING", "docs", "low", "auto", "active", "Documentation and reports.", "When docs/reporting needs updates")
        if rel_path.startswith("memory/"):
            return ("GENERATED", "runtime-memory", "medium", "auto", "active", "Generated runtime memory artifacts.", "Managed by runtime pipeline outputs")
        return ("WORKING", "general", "medium", "auto", "active", "General workspace file.", "When implementation/tasks require update")

    def _iter_files(self):
        for dirpath, dirnames, filenames in os.walk(WORKSPACE):
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDES]
            for name in filenames:
                p = Path(dirpath) / name
                rel = p.relative_to(WORKSPACE).as_posix()
                yield p, rel

    def _hash(self, p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def refresh_catalog(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for p, rel in self._iter_files():
            fclass, domain, risk, mode, status, primary_function, change_trigger = self._classify(rel)
            digest = self._hash(p)
            path_digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()
            file_id = f"file_{path_digest[:24]}"
            rows.append((file_id, rel, status, fclass, domain, risk, mode, digest, primary_function, change_trigger, "v1", "v1", now, now, 1))

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS file_catalog (
                    file_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    file_status TEXT NOT NULL,
                    file_class TEXT NOT NULL,
                    owner_domain TEXT,
                    task_risk_level TEXT NOT NULL,
                    writable_mode TEXT NOT NULL,
                    last_hash TEXT,
                    primary_function TEXT NOT NULL DEFAULT "",
                    change_trigger TEXT NOT NULL DEFAULT "",
                    schema_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    exists_flag INTEGER NOT NULL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_file_catalog_path ON file_catalog(path)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_file_catalog_class ON file_catalog(file_class)")
            columns = {row[1] for row in cur.execute("PRAGMA table_info(file_catalog)").fetchall()}
            if "primary_function" not in columns:
                cur.execute("ALTER TABLE file_catalog ADD COLUMN primary_function TEXT NOT NULL DEFAULT ''")
            if "change_trigger" not in columns:
                cur.execute("ALTER TABLE file_catalog ADD COLUMN change_trigger TEXT NOT NULL DEFAULT ''")
            cur.execute("DELETE FROM file_catalog")
            cur.executemany(
                """
                INSERT INTO file_catalog (
                    file_id,path,file_status,file_class,owner_domain,task_risk_level,
                    writable_mode,last_hash,primary_function,change_trigger,schema_version,policy_version,created_at,updated_at,exists_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        return len(rows)

    def _get_file_row(self, path: str) -> Dict | None:
        rel = Path(path).as_posix()
        if not self.db_path.exists():
            self.refresh_catalog()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM file_catalog WHERE path = ?", (rel,)).fetchone()
            if row:
                return dict(row)
        # fallback on-the-fly classification
        fclass, domain, risk, mode, status, primary_function, change_trigger = self._classify(rel)
        return {
            "file_id": f"file_dynamic_{hash(rel) & 0xfffffff}",
            "path": rel,
            "file_status": status,
            "file_class": fclass,
            "owner_domain": domain,
            "task_risk_level": risk,
            "writable_mode": mode,
            "policy_version": "v1",
        }

    def catalog_precheck(self, file_scope: List[str], mode: str = "auto") -> Dict:
        blocked = []
        allowed = []
        for path in file_scope or []:
            row = self._get_file_row(path)
            if not row:
                continue
            if row["file_class"] == "CORE" and mode != "review-only":
                blocked.append({"path": row["path"], "reason": "core_requires_review_only"})
            else:
                allowed.append(row["path"])

        return {
            "pass": len(blocked) == 0,
            "blocked": blocked,
            "allowed": allowed,
            "policy_version": "v1",
        }

    def catalog_enforce(self, path: str, mode: str = "auto", operation: str = "direct_write") -> Dict:
        row = self._get_file_row(path)
        if not row:
            return {"allowed": False, "reason": "path_not_in_catalog"}

        file_class = row.get("file_class")
        writable_mode = row.get("writable_mode")

        if file_class == "CORE" and operation == "direct_write":
            return {"allowed": False, "reason": "patch_first_required_for_core", "row": row}
        if writable_mode == "review-only" and mode != "review-only":
            return {"allowed": False, "reason": "review_only_path", "row": row}

        return {"allowed": True, "reason": "ok", "row": row}

    def transactional_patch_apply(
        self,
        path: str,
        new_content: str,
        *,
        evidence_hash: str,
        policy_version: str = "v1",
    ) -> Dict:
        rel_path = Path(path)
        abs_path = (WORKSPACE / rel_path).resolve()

        guard = self.catalog_enforce(rel_path.as_posix(), mode="review-only", operation="patch_apply")
        if not guard.get("allowed"):
            return {"success": False, "reason": guard.get("reason"), "guard": guard}

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        backup_dir = WORKSPACE / "memory" / "recovery" / "patch_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{rel_path.as_posix().replace('/', '__')}.{ts}.bak"

        old_content = ""
        if abs_path.exists():
            old_content = abs_path.read_text(encoding="utf-8", errors="ignore")
            backup.write_text(old_content, encoding="utf-8")

        # atomic replace via temp file + rename
        try:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(abs_path.parent)) as tmp:
                tmp.write(new_content)
                tmp_path = Path(tmp.name)
            tmp_path.replace(abs_path)
            self._audit(
                {
                    "timestamp": datetime.now().isoformat(),
                    "path": rel_path.as_posix(),
                    "operation": "patch_apply",
                    "result": "success",
                    "policy_version": policy_version,
                    "evidence_hash": evidence_hash,
                }
            )
            return {"success": True, "path": rel_path.as_posix(), "backup": backup.as_posix() if backup.exists() else None}
        except Exception as exc:
            # rollback
            if backup.exists():
                backup.replace(abs_path)
            self._audit(
                {
                    "timestamp": datetime.now().isoformat(),
                    "path": rel_path.as_posix(),
                    "operation": "patch_apply",
                    "result": "rollback",
                    "policy_version": policy_version,
                    "evidence_hash": evidence_hash,
                    "error": str(exc),
                }
            )
            return {"success": False, "reason": str(exc), "rolled_back": True}

    def _audit(self, entry: Dict):
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


_governor = None


def get_file_governance() -> FileGovernance:
    global _governor
    if _governor is None:
        _governor = FileGovernance()
    return _governor
