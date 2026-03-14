#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any


class SQLiteMemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _relation_type(self, conn: sqlite3.Connection, name: str) -> str | None:
        row = conn.execute(
            "SELECT type FROM sqlite_master WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return str(row["type"])

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [str(row["name"]) for row in rows]

    def _merge_or_rename_table(self, conn: sqlite3.Connection, old_name: str, new_name: str) -> None:
        old_exists = self._table_exists(conn, old_name)
        if not old_exists:
            return
        new_exists = self._table_exists(conn, new_name)
        if not new_exists:
            conn.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            return

        src_cols = set(self._table_columns(conn, old_name))
        dst_cols = self._table_columns(conn, new_name)
        common_cols = [col for col in dst_cols if col in src_cols]
        if common_cols:
            cols_sql = ", ".join(common_cols)
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {new_name} ({cols_sql})
                SELECT {cols_sql}
                FROM {old_name}
                """
            )
        conn.execute(f"DROP TABLE {old_name}")

    def _drop_relation_if_exists(self, conn: sqlite3.Connection, name: str) -> None:
        rel_type = self._relation_type(conn, name)
        if rel_type == "view":
            conn.execute(f"DROP VIEW IF EXISTS {name}")
        elif rel_type == "table":
            conn.execute(f"DROP TABLE IF EXISTS {name}")

    def _migrate_legacy_tables(self, conn: sqlite3.Connection) -> None:
        for old_name, new_name in (
            ("experience_events", "memories"),
            ("experience_rss", "memories_rss"),
            ("experience_conversations", "memories_conversation"),
            ("experience_knowledge", "memories_knowledge"),
            ("soul_changes", "soul_history"),
            ("entities", "graph_entities"),
            ("relations", "graph_relations"),
            ("state", "system_state"),
        ):
            self._merge_or_rename_table(conn, old_name, new_name)

        # feedback/misc tables are deprecated; keep category in memories only.
        conn.execute("DROP TABLE IF EXISTS experience_feedback")
        conn.execute("DROP TABLE IF EXISTS experience_misc")

    def _ensure_experiences_view(self, conn: sqlite3.Connection) -> None:
        rel_type = self._relation_type(conn, "experiences")
        if rel_type == "table":
            return
        conn.execute("DROP VIEW IF EXISTS experiences")
        conn.execute(
            """
            CREATE VIEW experiences AS
            SELECT
                id,
                type,
                content,
                source,
                created_at,
                updated_at,
                significance,
                tags_json,
                metadata_json,
                raw_json
            FROM memories
            """
        )

    def _ensure_memories_fts(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                source,
                type,
                significance,
                content='memories',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, source, type, significance)
                VALUES (new.rowid, new.content, new.source, new.type, new.significance);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, source, type, significance)
                VALUES ('delete', old.rowid, old.content, old.source, old.type, old.significance);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, source, type, significance)
                VALUES ('delete', old.rowid, old.content, old.source, old.type, old.significance);
                INSERT INTO memories_fts(rowid, content, source, type, significance)
                VALUES (new.rowid, new.content, new.source, new.type, new.significance);
            END;
            """
        )
        memories_count = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
        fts_count = conn.execute("SELECT COUNT(*) AS c FROM memories_fts").fetchone()["c"]
        if memories_count != fts_count:
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")

    def _migrate_feedback_hook_records(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "memories"):
            return
        if not self._table_exists(conn, "system_logs"):
            return

        conn.execute(
            """
            INSERT OR IGNORE INTO system_logs (
                id, log_type, source, content, created_at, updated_at,
                level, metadata_json, raw_json
            )
            SELECT
                id,
                'feedback_hook',
                source,
                content,
                created_at,
                updated_at,
                'info',
                metadata_json,
                raw_json
            FROM memories
            WHERE type = 'feedback_hook'
            """
        )
        conn.execute("DELETE FROM memories WHERE type = 'feedback_hook'")

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._migrate_legacy_tables(conn)
            self._drop_relation_if_exists(conn, "experiences")
            conn.execute("DROP TABLE IF EXISTS memories_rss")
            conn.execute("DROP TABLE IF EXISTS memories_conversation")
            conn.execute("DROP TABLE IF EXISTS memories_knowledge")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT 'other',
                    type TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    significance TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
                CREATE INDEX IF NOT EXISTS idx_memories_significance ON memories(significance);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);

                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT '',
                    approved_at TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
                CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at);

                CREATE TABLE IF NOT EXISTS reflections (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL DEFAULT '',
                    trigger TEXT NOT NULL DEFAULT '',
                    notable_count INTEGER NOT NULL DEFAULT 0,
                    analysis_json TEXT NOT NULL DEFAULT '{}',
                    proposals_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_reflections_timestamp ON reflections(timestamp);

                CREATE TABLE IF NOT EXISTS graph_entities (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL DEFAULT '',
                    properties_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_entities_entity_type ON graph_entities(entity_type);

                CREATE TABLE IF NOT EXISTS graph_relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL DEFAULT '',
                    target_id TEXT NOT NULL DEFAULT '',
                    relation_type TEXT NOT NULL DEFAULT '',
                    properties_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_relations_source_id ON graph_relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target_id ON graph_relations(target_id);
                CREATE INDEX IF NOT EXISTS idx_relations_relation_type ON graph_relations(relation_type);

                CREATE TABLE IF NOT EXISTS soul_history (
                    id TEXT PRIMARY KEY,
                    change_type TEXT NOT NULL DEFAULT '',
                    old_value TEXT NOT NULL DEFAULT '',
                    new_value TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    approved INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_soul_history_created_at ON soul_history(created_at);
                CREATE INDEX IF NOT EXISTS idx_soul_history_approved ON soul_history(approved);

                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL DEFAULT '',
                    source_proposal_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rules(enabled);
                CREATE INDEX IF NOT EXISTS idx_rules_created_at ON rules(created_at);
                CREATE INDEX IF NOT EXISTS idx_rules_source_proposal_id ON rules(source_proposal_id);

                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL DEFAULT '',
                    task_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'candidate',
                    source TEXT NOT NULL DEFAULT '',
                    score REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_candidates_skill_id ON candidates(skill_id);
                CREATE INDEX IF NOT EXISTS idx_candidates_task_type ON candidates(task_type);
                CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
                CREATE INDEX IF NOT EXISTS idx_candidates_updated_at ON candidates(updated_at);

                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS system_logs (
                    id TEXT PRIMARY KEY,
                    log_type TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_system_logs_log_type ON system_logs(log_type);
                CREATE INDEX IF NOT EXISTS idx_system_logs_source ON system_logs(source);
                CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
                CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);

                CREATE TABLE IF NOT EXISTS task_runs (
                    task_id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL DEFAULT '',
                    task_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    success INTEGER NOT NULL DEFAULT 1,
                    satisfaction TEXT NOT NULL DEFAULT 'satisfied',
                    significance TEXT NOT NULL DEFAULT 'routine',
                    skills_json TEXT NOT NULL DEFAULT '[]',
                    methods_json TEXT NOT NULL DEFAULT '[]',
                    execution_steps_json TEXT NOT NULL DEFAULT '[]',
                    thinking_json TEXT NOT NULL DEFAULT '[]',
                    output_summary TEXT NOT NULL DEFAULT '',
                    final_message TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_task_runs_created_at ON task_runs(created_at);
                CREATE INDEX IF NOT EXISTS idx_task_runs_success ON task_runs(success);
                CREATE INDEX IF NOT EXISTS idx_task_runs_satisfaction ON task_runs(satisfaction);
                CREATE INDEX IF NOT EXISTS idx_task_runs_significance ON task_runs(significance);
                CREATE INDEX IF NOT EXISTS idx_task_runs_task_type ON task_runs(task_type);


                CREATE TABLE IF NOT EXISTS external_learning_events (
                    event_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_name TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    collected_at TEXT NOT NULL DEFAULT '',
                    significance TEXT NOT NULL DEFAULT 'routine',
                    status TEXT NOT NULL DEFAULT 'new',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_external_learning_events_source_type ON external_learning_events(source_type);
                CREATE INDEX IF NOT EXISTS idx_external_learning_events_collected_at ON external_learning_events(collected_at);
                CREATE INDEX IF NOT EXISTS idx_external_learning_events_status ON external_learning_events(status);


                CREATE TABLE IF NOT EXISTS semantic_knowledge (
                    semantic_id TEXT PRIMARY KEY,
                    entity_id TEXT,
                    relation_id TEXT,
                    content TEXT NOT NULL DEFAULT '',
                    embedding_ref TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(entity_id) REFERENCES graph_entities(id) ON UPDATE CASCADE ON DELETE SET NULL,
                    FOREIGN KEY(relation_id) REFERENCES graph_relations(id) ON UPDATE CASCADE ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_semantic_knowledge_entity_id ON semantic_knowledge(entity_id);
                CREATE INDEX IF NOT EXISTS idx_semantic_knowledge_relation_id ON semantic_knowledge(relation_id);
                CREATE INDEX IF NOT EXISTS idx_semantic_knowledge_created_at ON semantic_knowledge(created_at);

                CREATE TABLE IF NOT EXISTS system_catalog (
                    object_key TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL DEFAULT '',
                    object_count INTEGER NOT NULL DEFAULT 0,
                    primary_function TEXT NOT NULL DEFAULT '',
                    change_trigger TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_system_catalog_object_type ON system_catalog(object_type);
                CREATE INDEX IF NOT EXISTS idx_system_catalog_updated_at ON system_catalog(updated_at);

                CREATE TABLE IF NOT EXISTS system_readable_checklist (
                    checklist_id TEXT PRIMARY KEY,
                    checklist_type TEXT NOT NULL DEFAULT '',
                    target_path TEXT NOT NULL DEFAULT '',
                    purpose TEXT NOT NULL DEFAULT '',
                    when_to_change TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_system_readable_checklist_type ON system_readable_checklist(checklist_type);
                CREATE INDEX IF NOT EXISTS idx_system_readable_checklist_target ON system_readable_checklist(target_path);
                """
            )
            self._ensure_memories_fts(conn)
            self._migrate_feedback_hook_records(conn)
            self._ensure_experiences_view(conn)

    def _record_json_decode_warning(self, *, context: str, raw_value: Any, error: Exception) -> None:
        now = datetime.now().isoformat()
        raw_preview = str(raw_value)
        if len(raw_preview) > 240:
            raw_preview = raw_preview[:240] + "..."
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM system_state WHERE key = ?", ("json_decode_warning_count",)).fetchone()
            count = 0
            if row and row[0]:
                try:
                    count = int(json.loads(row[0]).get("count", 0))
                except Exception:
                    count = 0
            count += 1
            conn.execute(
                "INSERT OR REPLACE INTO system_state (key, value_json, updated_at) VALUES (?, ?, ?)",
                ("json_decode_warning_count", json.dumps({"count": count}, ensure_ascii=False), now),
            )
            conn.execute(
                """
                INSERT INTO system_logs (
                    id, log_type, source, content, created_at, updated_at, level, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._stable_id("json_decode_warning", {"context": context, "time": now, "raw": raw_preview}),
                    "json_decode_warning",
                    "sqlite_memory",
                    str(error),
                    now,
                    now,
                    "warning",
                    self._json_dumps({"context": context}, {}),
                    self._json_dumps({"raw_preview": raw_preview}, {}),
                ),
            )

    def _safe_json_loads(self, raw: Any, default: Any, *, context: str = "") -> Any:
        if raw is None:
            return default
        if isinstance(raw, (dict, list)):
            return raw
        text = str(raw).strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception as error:
            self._record_json_decode_warning(context=context or "unknown", raw_value=text, error=error)
            return default

    def _json_dumps(self, value: Any, default: Any) -> str:
        if value is None:
            value = default
        if isinstance(default, dict) and not isinstance(value, dict):
            value = self._safe_json_loads(value, default, context="write_schema.dict")
            if not isinstance(value, dict):
                value = default
        elif isinstance(default, list) and not isinstance(value, list):
            value = self._safe_json_loads(value, default, context="write_schema.list")
            if not isinstance(value, list):
                value = default
        return json.dumps(value, ensure_ascii=False)

    def _stable_id(self, prefix: str, payload: Any) -> str:
        digest = sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"{prefix}-{digest}"

    def _normalized_row(self, exp: dict[str, Any]) -> dict[str, Any]:
        metadata = exp.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        tags = exp.get("tags")
        if not isinstance(tags, list):
            tags = []

        created_at = str(exp.get("created_at") or exp.get("timestamp") or "")
        updated_at = str(exp.get("updated_at") or created_at)
        content = exp.get("content") or exp.get("message") or ""
        significance = (
            exp.get("significance")
            or metadata.get("significance")
            or ""
        )
        message_id = str(exp.get("message_id") or metadata.get("message_id") or "")
        if message_id:
            row_id = str(exp.get("id") or self._stable_id("experience_message", {"message_id": message_id}))
        else:
            row_id = str(
                exp.get("id")
                or self._stable_id(
                    "experience",
                    {
                        "type": exp.get("type"),
                        "content": content,
                        "source": exp.get("source"),
                        "created_at": created_at,
                        "updated_at": updated_at,
                    },
                )
            )

        if message_id and "message_id" not in metadata:
            metadata["message_id"] = message_id

        return {
            "id": row_id,
            "type": str(exp.get("type") or ""),
            "content": str(content),
            "source": str(exp.get("source") or ""),
            "created_at": created_at,
            "updated_at": updated_at,
            "significance": str(significance),
            "tags_json": self._json_dumps(tags, []),
            "metadata_json": self._json_dumps(metadata, {}),
            "raw_json": self._json_dumps(exp, {}),
        }

    def _experience_category(self, exp_type: str, source: str) -> str:
        t = (exp_type or "").strip().lower()
        s = (source or "").strip().lower()
        if t == "conversation":
            return "conversation"
        if t == "knowledge":
            return "knowledge"
        if t.startswith("rss"):
            return "rss"
        if t.startswith("feedback"):
            return "feedback"
        if "://" in s and ("feed" in s or "rss" in s):
            return "rss"
        if s in {"proposal", "semantic", "significant"} and t in {"", "knowledge", "semantic"}:
            return "knowledge"
        return "other"

    def upsert_experience(self, exp: dict[str, Any]) -> None:
        row = self._normalized_row(exp)
        category = self._experience_category(row["type"], row["source"])
        row["category"] = category
        
        # Handle reflected fields
        reflected = 1 if exp.get("reflected") else 0
        reflection_id = exp.get("reflection_id") or ""
        reflected_at = exp.get("reflected_at") or ""
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, category, type, content, source, created_at, updated_at,
                    significance, tags_json, metadata_json, raw_json,
                    reflected, reflection_id, reflected_at
                ) VALUES (
                    :id, :category, :type, :content, :source, :created_at, :updated_at,
                    :significance, :tags_json, :metadata_json, :raw_json,
                    :reflected, :reflection_id, :reflected_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    category=excluded.category,
                    type=excluded.type,
                    content=excluded.content,
                    source=excluded.source,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    significance=excluded.significance,
                    tags_json=excluded.tags_json,
                    metadata_json=excluded.metadata_json,
                    raw_json=excluded.raw_json,
                    reflected=excluded.reflected,
                    reflection_id=excluded.reflection_id,
                    reflected_at=excluded.reflected_at
                """,
                {**row, "reflected": reflected, "reflection_id": reflection_id, "reflected_at": reflected_at},
            )

    def mark_experiences_reflected(self, experience_ids: list[str], reflection_id: str) -> int:
        """Mark multiple experiences as reflected"""
        if not experience_ids:
            return 0
        reflected_at = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memories 
                SET reflected = 1, reflection_id = :reflection_id, reflected_at = :reflected_at
                WHERE id IN (""" + ",".join([f"'{e}'" for e in experience_ids]) + """)
                """,
                {"reflection_id": reflection_id, "reflected_at": reflected_at},
            )
            conn.commit()
            return cursor.rowcount

    def get_unreflected_experiences(self, significance: str | None = None, limit: int = 100) -> list[dict]:
        """Get unreflected experiences, optionally filtered by significance"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM memories 
                WHERE reflected = 0""" + (f" AND significance = '{significance}'" if significance else "") + """
                ORDER BY created_at DESC LIMIT {limit}
                """.format(limit=limit)
            )
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    def count_unreflected_experiences(self, significance: str | None = None) -> dict:
        """Count unreflected experiences, optionally by significance"""
        with self._connect() as conn:
            if significance:
                row = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE reflected = 0 AND significance = ?",
                    (significance,),
                ).fetchone()
                return {"total": row[0] if row else 0, significance: row[0] if row else 0}
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE reflected = 0",
                ).fetchone()
                total = row[0] if row else 0
                notable_row = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE reflected = 0 AND significance = 'notable'",
                ).fetchone()
                routine_row = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE reflected = 0 AND significance = 'routine'",
                ).fetchone()
                return {
                    "total": total,
                    "notable": notable_row[0] if notable_row else 0,
                    "routine": routine_row[0] if routine_row else 0,
                }

    def _normalized_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        metadata = proposal.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        tags = proposal.get("tags")
        if not isinstance(tags, list):
            tags = []

        created_at = str(proposal.get("created_at") or proposal.get("timestamp") or "")
        updated_at = str(proposal.get("updated_at") or created_at)
        status = str(proposal.get("status") or metadata.get("status") or "")
        priority = str(proposal.get("priority") or metadata.get("priority") or "")
        approved_at = str(proposal.get("approved_at") or metadata.get("approved_at") or "")
        row_id = str(proposal.get("id") or self._stable_id("proposal", proposal))

        return {
            "id": row_id,
            "type": str(proposal.get("type") or ""),
            "content": str(proposal.get("content") or proposal.get("description") or ""),
            "source": str(proposal.get("source") or "proposals"),
            "created_at": created_at,
            "updated_at": updated_at,
            "status": status,
            "priority": priority,
            "approved_at": approved_at,
            "tags_json": self._json_dumps(tags, []),
            "metadata_json": self._json_dumps(metadata, {}),
        }

    def upsert_proposal(self, proposal: dict[str, Any]) -> None:
        row = self._normalized_proposal(proposal)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO proposals (
                    id, type, content, source, created_at, updated_at,
                    status, priority, approved_at, tags_json, metadata_json
                ) VALUES (
                    :id, :type, :content, :source, :created_at, :updated_at,
                    :status, :priority, :approved_at, :tags_json, :metadata_json
                )
                ON CONFLICT(id) DO UPDATE SET
                    type=excluded.type,
                    content=excluded.content,
                    source=excluded.source,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    priority=excluded.priority,
                    approved_at=excluded.approved_at,
                    tags_json=excluded.tags_json,
                    metadata_json=excluded.metadata_json
                """,
                row,
            )

    def _normalized_reflection(self, reflection: dict[str, Any]) -> dict[str, Any]:
        timestamp = str(reflection.get("timestamp") or "")
        created_at = str(reflection.get("created_at") or timestamp)
        row_id = str(reflection.get("id") or self._stable_id("reflection", reflection))
        analysis = reflection.get("analysis")
        if analysis is None:
            analysis = reflection.get("insights")
        proposals = reflection.get("proposals")
        if proposals is None:
            proposals = []
        notable_count = reflection.get("notable_count")
        if not isinstance(notable_count, int):
            try:
                notable_count = int(notable_count or 0)
            except (TypeError, ValueError):
                notable_count = 0

        return {
            "id": row_id,
            "timestamp": timestamp,
            "trigger": str(reflection.get("trigger") or ""),
            "notable_count": notable_count,
            "analysis_json": self._json_dumps(analysis, {}),
            "proposals_json": self._json_dumps(proposals, []),
            "created_at": created_at,
        }

    def upsert_reflection(self, reflection: dict[str, Any]) -> None:
        row = self._normalized_reflection(reflection)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reflections (
                    id, timestamp, trigger, notable_count,
                    analysis_json, proposals_json, created_at
                ) VALUES (
                    :id, :timestamp, :trigger, :notable_count,
                    :analysis_json, :proposals_json, :created_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    timestamp=excluded.timestamp,
                    trigger=excluded.trigger,
                    notable_count=excluded.notable_count,
                    analysis_json=excluded.analysis_json,
                    proposals_json=excluded.proposals_json,
                    created_at=excluded.created_at
                """,
                row,
            )

    def _normalized_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        row_id = str(entity.get("id") or self._stable_id("entity", entity))
        return {
            "id": row_id,
            "entity_type": str(entity.get("entity_type") or entity.get("type") or ""),
            "properties_json": self._json_dumps(entity.get("properties"), {}),
            "created_at": str(entity.get("created_at") or ""),
        }

    def upsert_entity(self, entity: dict[str, Any]) -> None:
        row = self._normalized_entity(entity)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_entities (id, entity_type, properties_json, created_at)
                VALUES (:id, :entity_type, :properties_json, :created_at)
                ON CONFLICT(id) DO UPDATE SET
                    entity_type=excluded.entity_type,
                    properties_json=excluded.properties_json,
                    created_at=excluded.created_at
                """,
                row,
            )

    def _normalized_relation(self, relation: dict[str, Any]) -> dict[str, Any]:
        source_id = str(relation.get("source_id") or relation.get("from") or "")
        target_id = str(relation.get("target_id") or relation.get("to") or "")
        relation_type = str(relation.get("relation_type") or relation.get("type") or "")
        created_at = str(relation.get("created_at") or "")
        row_id = str(
            relation.get("id")
            or self._stable_id(
                "relation",
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation_type": relation_type,
                    "created_at": created_at,
                    "properties": relation.get("properties"),
                },
            )
        )

        return {
            "id": row_id,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "properties_json": self._json_dumps(relation.get("properties"), {}),
            "created_at": created_at,
        }

    def upsert_relation(self, relation: dict[str, Any]) -> None:
        row = self._normalized_relation(relation)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_relations (
                    id, source_id, target_id, relation_type, properties_json, created_at
                ) VALUES (
                    :id, :source_id, :target_id, :relation_type, :properties_json, :created_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    target_id=excluded.target_id,
                    relation_type=excluded.relation_type,
                    properties_json=excluded.properties_json,
                    created_at=excluded.created_at
                """,
                row,
            )

    def _normalized_soul_change(self, change: dict[str, Any]) -> dict[str, Any]:
        created_at = str(change.get("created_at") or change.get("timestamp") or "")
        row_id = str(change.get("id") or self._stable_id("soul-change", change))
        approved_val = change.get("approved")
        approved = 0
        if isinstance(approved_val, bool):
            approved = 1 if approved_val else 0
        elif isinstance(approved_val, (int, float)):
            approved = 1 if int(approved_val) != 0 else 0
        elif isinstance(approved_val, str):
            approved = 1 if approved_val.strip().lower() in {"1", "true", "yes", "approved"} else 0

        return {
            "id": row_id,
            "change_type": str(change.get("change_type") or ""),
            "old_value": str(change.get("old_value") or ""),
            "new_value": str(change.get("new_value") or ""),
            "created_at": created_at,
            "approved": approved,
        }

    def upsert_soul_change(self, change: dict[str, Any]) -> None:
        row = self._normalized_soul_change(change)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO soul_history (
                    id, change_type, old_value, new_value, created_at, approved
                ) VALUES (
                    :id, :change_type, :old_value, :new_value, :created_at, :approved
                )
                ON CONFLICT(id) DO UPDATE SET
                    change_type=excluded.change_type,
                    old_value=excluded.old_value,
                    new_value=excluded.new_value,
                    created_at=excluded.created_at,
                    approved=excluded.approved
                """,
                row,
            )

    def _normalized_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        content = rule.get("content")
        if isinstance(content, str):
            content_str = content
        else:
            content_str = self._json_dumps(content, {})

        created_at = str(rule.get("created_at") or rule.get("timestamp") or "")
        row_id = str(rule.get("id") or self._stable_id("rule", rule))

        enabled_val = rule.get("enabled", True)
        enabled = 1
        if isinstance(enabled_val, bool):
            enabled = 1 if enabled_val else 0
        elif isinstance(enabled_val, (int, float)):
            enabled = 1 if int(enabled_val) != 0 else 0
        elif isinstance(enabled_val, str):
            enabled = 1 if enabled_val.strip().lower() in {"1", "true", "yes", "enabled"} else 0

        return {
            "id": row_id,
            "content": content_str,
            "source_proposal_id": str(
                rule.get("source_proposal_id")
                or rule.get("proposal_id")
                or ""
            ),
            "created_at": created_at,
            "enabled": enabled,
        }

    def upsert_rule(self, rule: dict[str, Any]) -> None:
        row = self._normalized_rule(rule)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rules (
                    id, content, source_proposal_id, created_at, enabled
                ) VALUES (
                    :id, :content, :source_proposal_id, :created_at, :enabled
                )
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content,
                    source_proposal_id=excluded.source_proposal_id,
                    created_at=excluded.created_at,
                    enabled=excluded.enabled
                """,
                row,
            )

    def _normalized_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        metadata = candidate.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        skill_id = str(candidate.get("skill_id") or metadata.get("skill_id") or "")
        task_type = str(candidate.get("task_type") or metadata.get("task_type") or "")
        source = str(candidate.get("source") or metadata.get("source") or "")
        status = str(candidate.get("status") or metadata.get("status") or "candidate")
        created_at = str(candidate.get("created_at") or candidate.get("timestamp") or "")
        updated_at = str(candidate.get("updated_at") or created_at)

        score = candidate.get("score", metadata.get("score", 0))
        try:
            score_val = float(score)
        except (TypeError, ValueError):
            score_val = 0.0

        row_id = str(
            candidate.get("id")
            or candidate.get("candidate_id")
            or self._stable_id(
                "candidate",
                {
                    "skill_id": skill_id,
                    "task_type": task_type,
                    "source": source,
                    "status": status,
                    "created_at": created_at,
                },
            )
        )

        return {
            "id": row_id,
            "skill_id": skill_id,
            "task_type": task_type,
            "status": status,
            "source": source,
            "score": score_val,
            "created_at": created_at,
            "updated_at": updated_at,
            "metadata_json": self._json_dumps(metadata, {}),
            "raw_json": self._json_dumps(candidate, {}),
        }

    def upsert_candidate(self, candidate: dict[str, Any]) -> None:
        row = self._normalized_candidate(candidate)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO candidates (
                    id, skill_id, task_type, status, source, score,
                    created_at, updated_at, metadata_json, raw_json
                ) VALUES (
                    :id, :skill_id, :task_type, :status, :source, :score,
                    :created_at, :updated_at, :metadata_json, :raw_json
                )
                ON CONFLICT(id) DO UPDATE SET
                    skill_id=excluded.skill_id,
                    task_type=excluded.task_type,
                    status=excluded.status,
                    source=excluded.source,
                    score=excluded.score,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    metadata_json=excluded.metadata_json,
                    raw_json=excluded.raw_json
                """,
                row,
            )

    def upsert_state(self, key: str, value: Any, updated_at: str) -> None:
        if not key:
            raise ValueError("system_state.key is required")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_state (key, value_json, updated_at)
                VALUES (:key, :value_json, :updated_at)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                {
                    "key": key,
                    "value_json": self._json_dumps(value, {}),
                    "updated_at": updated_at or "",
                },
            )

    def _normalized_task_run(self, task_run: dict[str, Any]) -> dict[str, Any]:
        created_at = str(task_run.get("created_at") or task_run.get("timestamp") or "")
        updated_at = str(task_run.get("updated_at") or created_at)
        task_id = str(task_run.get("task_id") or self._stable_id("task_run", task_run))
        return {
            "task_id": task_id,
            "task_name": str(task_run.get("task_name") or ""),
            "user_message": str(task_run.get("user_message") or ""),
            "task_type": str(task_run.get("task_type") or ""),
            "analysis_json": self._json_dumps(task_run.get("analysis_json"), {}),
            "status": str(task_run.get("status") or ""),
            "success": 1 if bool(task_run.get("success", True)) else 0,
            "satisfaction": str(task_run.get("satisfaction") or "satisfied"),
            "significance": str(task_run.get("significance") or "routine"),
            "skills_json": self._json_dumps(task_run.get("skills"), []),
            "methods_json": self._json_dumps(task_run.get("methods"), []),
            "execution_steps_json": self._json_dumps(task_run.get("execution_steps"), []),
            "thinking_json": self._json_dumps(task_run.get("thinking"), []),
            "output_summary": str(task_run.get("output_summary") or ""),
            "final_message": str(task_run.get("final_message") or ""),
            "source": str(task_run.get("source") or "message_handler"),
            "created_at": created_at,
            "updated_at": updated_at,
            "metadata_json": self._json_dumps(task_run.get("metadata"), {}),
        }

    def upsert_task_run(self, task_run: dict[str, Any]) -> None:
        row = self._normalized_task_run(task_run)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_runs (
                    task_id, task_name, user_message, task_type, analysis_json, status, success, satisfaction, significance,
                    skills_json, methods_json, execution_steps_json, thinking_json,
                    output_summary, final_message, source, created_at, updated_at, metadata_json
                ) VALUES (
                    :task_id, :task_name, :user_message, :task_type, :analysis_json, :status, :success, :satisfaction, :significance,
                    :skills_json, :methods_json, :execution_steps_json, :thinking_json,
                    :output_summary, :final_message, :source, :created_at, :updated_at, :metadata_json
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    task_name=excluded.task_name,
                    user_message=excluded.user_message,
                    task_type=excluded.task_type,
                    analysis_json=excluded.analysis_json,
                    status=excluded.status,
                    success=excluded.success,
                    satisfaction=excluded.satisfaction,
                    significance=excluded.significance,
                    skills_json=excluded.skills_json,
                    methods_json=excluded.methods_json,
                    execution_steps_json=excluded.execution_steps_json,
                    thinking_json=excluded.thinking_json,
                    output_summary=excluded.output_summary,
                    final_message=excluded.final_message,
                    source=excluded.source,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    metadata_json=excluded.metadata_json
                """,
                row,
            )

    def query_task_runs(
        self,
        *,
        task_type: str | None = None,
        satisfaction: str | None = None,
        significance: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": max(1, int(limit)), "offset": max(0, int(offset))}
        if task_type:
            where.append("task_type = :task_type")
            params["task_type"] = task_type
        if satisfaction:
            where.append("satisfaction = :satisfaction")
            params["satisfaction"] = satisfaction
        if significance:
            where.append("significance = :significance")
            params["significance"] = significance
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT task_id, task_name, task_type, status, success, satisfaction, significance,
                       skills_json, methods_json, execution_steps_json, thinking_json,
                       output_summary, final_message, source, created_at, updated_at, metadata_json
                FROM task_runs
                {where_clause}
                ORDER BY created_at DESC, task_id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append({
                "task_id": row["task_id"],
                "task_name": row["task_name"],
                "task_type": row["task_type"],
                "status": row["status"],
                "success": bool(row["success"]),
                "satisfaction": row["satisfaction"],
                "significance": row["significance"],
                "skills": self._safe_json_loads(row["skills_json"], [], context="task_runs.skills_json"),
                "methods": self._safe_json_loads(row["methods_json"], [], context="task_runs.methods_json"),
                "execution_steps": self._safe_json_loads(row["execution_steps_json"], [], context="task_runs.execution_steps_json"),
                "thinking": self._safe_json_loads(row["thinking_json"], [], context="task_runs.thinking_json"),
                "output_summary": row["output_summary"],
                "final_message": row["final_message"],
                "source": row["source"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json"),
            })
        return result


    def upsert_external_learning_event(self, event: dict[str, Any]) -> None:
        row = {
            "event_id": str(event.get("event_id") or self._stable_id("external_learning", event)),
            "source_type": str(event.get("source_type") or ""),
            "source_name": str(event.get("source_name") or ""),
            "title": str(event.get("title") or ""),
            "content": str(event.get("content") or ""),
            "url": str(event.get("url") or ""),
            "collected_at": str(event.get("collected_at") or event.get("created_at") or ""),
            "significance": str(event.get("significance") or "routine"),
            "status": str(event.get("status") or "new"),
            "metadata_json": self._json_dumps(event.get("metadata"), {}),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO external_learning_events (
                    event_id, source_type, source_name, title, content, url,
                    collected_at, significance, status, metadata_json
                ) VALUES (
                    :event_id, :source_type, :source_name, :title, :content, :url,
                    :collected_at, :significance, :status, :metadata_json
                )
                ON CONFLICT(event_id) DO UPDATE SET
                    source_type=excluded.source_type,
                    source_name=excluded.source_name,
                    title=excluded.title,
                    content=excluded.content,
                    url=excluded.url,
                    collected_at=excluded.collected_at,
                    significance=excluded.significance,
                    status=excluded.status,
                    metadata_json=excluded.metadata_json
                """,
                row,
            )

    def query_external_learning_events(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": max(1, int(limit)), "offset": max(0, int(offset))}
        if source_type:
            where.append("source_type = :source_type")
            params["source_type"] = source_type
        if status:
            where.append("status = :status")
            params["status"] = status
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, source_type, source_name, title, content, url,
                       collected_at, significance, status, metadata_json
                FROM external_learning_events
                {where_clause}
                ORDER BY collected_at DESC, event_id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "event_id": row["event_id"],
                    "source_type": row["source_type"],
                    "source_name": row["source_name"],
                    "title": row["title"],
                    "content": row["content"],
                    "url": row["url"],
                    "collected_at": row["collected_at"],
                    "significance": row["significance"],
                    "status": row["status"],
                    "metadata": self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json"),
                }
            )
        return result

    def mark_external_learning_event_status(self, event_id: str, status: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE external_learning_events SET status=:status WHERE event_id=:event_id",
                {"event_id": str(event_id), "status": str(status)},
            )
        return cur.rowcount > 0

    def upsert_semantic_knowledge(self, record: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        row = {
            "semantic_id": str(record.get("semantic_id") or self._stable_id("semantic_knowledge", record)),
            "entity_id": str(record.get("entity_id") or ""),
            "relation_id": str(record.get("relation_id") or ""),
            "content": str(record.get("content") or ""),
            "embedding_ref": str(record.get("embedding_ref") or ""),
            "source": str(record.get("source") or ""),
            "created_at": str(record.get("created_at") or now),
            "updated_at": str(record.get("updated_at") or now),
            "metadata_json": self._json_dumps(record.get("metadata"), {}),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_knowledge (
                    semantic_id, entity_id, relation_id, content, embedding_ref,
                    source, created_at, updated_at, metadata_json
                ) VALUES (
                    :semantic_id, :entity_id, :relation_id, :content, :embedding_ref,
                    :source, :created_at, :updated_at, :metadata_json
                )
                ON CONFLICT(semantic_id) DO UPDATE SET
                    entity_id=excluded.entity_id,
                    relation_id=excluded.relation_id,
                    content=excluded.content,
                    embedding_ref=excluded.embedding_ref,
                    source=excluded.source,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    metadata_json=excluded.metadata_json
                """,
                row,
            )

    def query_semantic_knowledge(self, *, entity_id: str | None = None, relation_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": max(1, int(limit)), "offset": max(0, int(offset))}
        if entity_id:
            where.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if relation_id:
            where.append("relation_id = :relation_id")
            params["relation_id"] = relation_id
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT semantic_id, entity_id, relation_id, content, embedding_ref,
                       source, created_at, updated_at, metadata_json
                FROM semantic_knowledge
                {where_clause}
                ORDER BY updated_at DESC, semantic_id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "semantic_id": row["semantic_id"],
                    "entity_id": row["entity_id"],
                    "relation_id": row["relation_id"],
                    "content": row["content"],
                    "embedding_ref": row["embedding_ref"],
                    "source": row["source"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json"),
                }
            )
        return out

    def mark_semantic_knowledge_status(self, semantic_id: str, status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT metadata_json FROM semantic_knowledge WHERE semantic_id=?", (str(semantic_id),)).fetchone()
            if row is None:
                return False
            md = self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json")
            md["status"] = str(status)
            md["status_updated_at"] = datetime.now().isoformat()
            conn.execute(
                "UPDATE semantic_knowledge SET metadata_json=:md, updated_at=:updated_at WHERE semantic_id=:id",
                {"id": str(semantic_id), "md": self._json_dumps(md, {}), "updated_at": datetime.now().isoformat()},
            )
        return True

    def run_relationship_consistency_check(self, *, limit: int = 500) -> dict[str, Any]:
        """Check cross-table relationship and timestamp consistency."""
        checks: dict[str, int] = {}
        with self._connect() as conn:
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            checks["foreign_key_violations"] = len(fk_violations)

        checks["total_issues"] = int(sum(v for v in checks.values()))
        checks["checked_at"] = datetime.now().isoformat()
        return checks

    def _normalized_system_log(self, log: dict[str, Any]) -> dict[str, Any]:
        metadata = log.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        content = log.get("content")
        if isinstance(content, str):
            content_text = content
        else:
            content_text = self._json_dumps(content, {})

        created_at = str(log.get("created_at") or log.get("timestamp") or "")
        updated_at = str(log.get("updated_at") or created_at)
        log_type = str(log.get("log_type") or log.get("type") or "")
        source = str(log.get("source") or "")
        level = str(log.get("level") or metadata.get("level") or "")

        row_id = str(
            log.get("id")
            or self._stable_id(
                "system-log",
                {
                    "log_type": log_type,
                    "source": source,
                    "created_at": created_at,
                    "content": content_text,
                },
            )
        )

        return {
            "id": row_id,
            "log_type": log_type,
            "source": source,
            "content": content_text,
            "created_at": created_at,
            "updated_at": updated_at,
            "level": level,
            "metadata_json": self._json_dumps(metadata, {}),
            "raw_json": self._json_dumps(log, {}),
        }

    def upsert_system_log(self, log: dict[str, Any]) -> None:
        row = self._normalized_system_log(log)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_logs (
                    id, log_type, source, content, created_at, updated_at,
                    level, metadata_json, raw_json
                ) VALUES (
                    :id, :log_type, :source, :content, :created_at, :updated_at,
                    :level, :metadata_json, :raw_json
                )
                ON CONFLICT(id) DO UPDATE SET
                    log_type=excluded.log_type,
                    source=excluded.source,
                    content=excluded.content,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    level=excluded.level,
                    metadata_json=excluded.metadata_json,
                    raw_json=excluded.raw_json
                """,
                row,
            )

    def get_state(self, key: str, default: Any | None = None) -> Any:
        if not key:
            raise ValueError("system_state.key is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM system_state WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        raw = row["value_json"]
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    def query_state(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value_json, updated_at FROM system_state ORDER BY key ASC"
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            value: Any = {}
            try:
                value = self._safe_json_loads(row["value_json"], {}, context="system_state.value_json")
            except (TypeError, ValueError, json.JSONDecodeError):
                value = {}
            result.append(
                {
                    "key": row["key"],
                    "value": value,
                    "updated_at": row["updated_at"],
                }
            )
        return result

    def query_system_logs(
        self,
        *,
        log_type: str | None = None,
        source: str | None = None,
        level: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": max(1, int(limit)), "offset": max(0, int(offset))}
        if log_type:
            where.append("log_type = :log_type")
            params["log_type"] = log_type
        if source:
            where.append("source = :source")
            params["source"] = source
        if level:
            where.append("level = :level")
            params["level"] = level
        if start_time:
            where.append("created_at >= :start_time")
            params["start_time"] = start_time
        if end_time:
            where.append("created_at <= :end_time")
            params["end_time"] = end_time

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id, log_type, source, content, created_at, updated_at,
                    level, metadata_json, raw_json
                FROM system_logs
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            metadata = self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json")
            raw = self._safe_json_loads(row["raw_json"], {}, context="row.raw_json")
            result.append(
                {
                    "id": row["id"],
                    "log_type": row["log_type"],
                    "source": row["source"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "level": row["level"],
                    "metadata": metadata,
                    "raw": raw,
                }
            )
        return result

    def query_experiences(
        self,
        *,
        text_query: str | None = None,
        exp_type: str | None = None,
        source: str | None = None,
        significance: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": max(1, int(limit)), "offset": max(0, int(offset))}

        if text_query:
            where.append("content LIKE :text_query")
            params["text_query"] = f"%{text_query}%"
        if exp_type:
            where.append("type = :exp_type")
            params["exp_type"] = exp_type
        if source:
            where.append("source = :source")
            params["source"] = source
        if significance:
            where.append("significance = :significance")
            params["significance"] = significance
        if start_time:
            where.append("created_at >= :start_time")
            params["start_time"] = start_time
        if end_time:
            where.append("created_at <= :end_time")
            params["end_time"] = end_time

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id, category, type, content, source, created_at, updated_at,
                    significance, tags_json, metadata_json, raw_json
                FROM memories
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            tags = self._safe_json_loads(row["tags_json"], [], context="memories.tags_json")
            metadata = self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json")
            raw = self._safe_json_loads(row["raw_json"], {}, context="row.raw_json")
            result.append(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "type": row["type"],
                    "content": row["content"],
                    "source": row["source"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "significance": row["significance"],
                    "tags": tags,
                    "metadata": metadata,
                    "raw": raw,
                }
            )
        return result

    # ========== Query Methods ==========

    def query_proposals(self, status=None, prop_type=None, limit=100):
        """Query proposals by status and/or type."""
        sql = "SELECT * FROM proposals WHERE 1=1"
        params = []
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        if prop_type is not None:
            sql += " AND type = ?"
            params.append(prop_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_reflections(self, limit=100):
        """Query recent reflections."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            # Deserialize JSON fields
            if d.get("analysis_json"):
                try:
                    d["analysis"] = self._safe_json_loads(d["analysis_json"], {}, context="reflections.analysis_json")
                except:
                    d["analysis"] = {}
            if d.get("proposals_json"):
                try:
                    d["proposals"] = self._safe_json_loads(d["proposals_json"], [], context="reflections.proposals_json")
                except:
                    d["proposals"] = []
            results.append(d)
        return results

    def query_soul_history(self, approved=None, limit=100):
        """Query soul changes by approval status."""
        sql = "SELECT * FROM soul_history WHERE 1=1"
        params = []
        if approved is not None:
            sql += " AND approved = ?"
            params.append(1 if approved else 0)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_soul_changes(self, approved=None, limit=100):
        return self.query_soul_history(approved=approved, limit=limit)

    def query_rules(self, enabled=None, source_proposal_id=None, limit=1000):
        """Query rules by enabled system_state and/or source proposal id."""
        sql = "SELECT * FROM rules WHERE 1=1"
        params = []
        if enabled is not None:
            sql += " AND enabled = ?"
            params.append(1 if enabled else 0)
        if source_proposal_id is not None:
            sql += " AND source_proposal_id = ?"
            params.append(source_proposal_id)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            raw_content = item.get("content")
            if raw_content:
                try:
                    item["content_json"] = self._safe_json_loads(raw_content, {}, context="rules.content")
                except (TypeError, ValueError, json.JSONDecodeError):
                    item["content_json"] = {}
            else:
                item["content_json"] = {}
            result.append(item)
        return result

    def query_candidates(
        self,
        *,
        skill_id: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        source: str | None = None,
        min_score: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {
            "limit": max(1, int(limit)),
            "offset": max(0, int(offset)),
        }
        if skill_id:
            where.append("skill_id = :skill_id")
            params["skill_id"] = skill_id
        if task_type:
            where.append("task_type = :task_type")
            params["task_type"] = task_type
        if status:
            where.append("status = :status")
            params["status"] = status
        if source:
            where.append("source = :source")
            params["source"] = source
        if min_score is not None:
            where.append("score >= :min_score")
            params["min_score"] = float(min_score)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id, skill_id, task_type, status, source, score,
                    created_at, updated_at, metadata_json, raw_json
                FROM candidates
                {where_clause}
                ORDER BY updated_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            metadata = self._safe_json_loads(row["metadata_json"], {}, context="row.metadata_json")
            raw = self._safe_json_loads(row["raw_json"], {}, context="row.raw_json")
            result.append(
                {
                    "id": row["id"],
                    "skill_id": row["skill_id"],
                    "task_type": row["task_type"],
                    "status": row["status"],
                    "source": row["source"],
                    "score": row["score"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": metadata,
                    "raw": raw,
                }
            )
        return result

    def query_recent_experiences(self, hours=24, limit=100):
        """Query experiences from recent hours."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit)
            ).fetchall()
        return [dict(r) for r in rows]


    def replace_system_catalog(self, rows: list[dict[str, Any]]) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM system_catalog")
            conn.executemany(
                """
                INSERT INTO system_catalog (
                    object_key, object_type, object_count,
                    primary_function, change_trigger, source,
                    metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(row.get("object_key") or ""),
                        str(row.get("object_type") or ""),
                        int(row.get("object_count") or 0),
                        str(row.get("primary_function") or ""),
                        str(row.get("change_trigger") or ""),
                        str(row.get("source") or ""),
                        self._json_dumps(row.get("metadata"), {}),
                        str(row.get("updated_at") or now),
                    )
                    for row in rows
                ],
            )

    def query_system_catalog(self, object_type: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        sql = "SELECT * FROM system_catalog"
        params: list[Any] = []
        if object_type:
            sql += " WHERE object_type = ?"
            params.append(object_type)
        sql += " ORDER BY object_key ASC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = self._safe_json_loads(item.get("metadata_json"), {}, context="system_catalog.metadata_json")
            result.append(item)
        return result


    def replace_readable_checklist(self, rows: list[dict[str, Any]]) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM system_readable_checklist")
            conn.executemany(
                """
                INSERT INTO system_readable_checklist (
                    checklist_id, checklist_type, target_path,
                    purpose, when_to_change, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(row.get("checklist_id") or ""),
                        str(row.get("checklist_type") or ""),
                        str(row.get("target_path") or ""),
                        str(row.get("purpose") or ""),
                        str(row.get("when_to_change") or ""),
                        str(row.get("source") or ""),
                        str(row.get("updated_at") or now),
                    )
                    for row in rows
                ],
            )

    def query_readable_checklist(self, checklist_type: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        sql = "SELECT * FROM system_readable_checklist"
        params: list[Any] = []
        if checklist_type:
            sql += " WHERE checklist_type = ?"
            params.append(checklist_type)
        sql += " ORDER BY checklist_id ASC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
