#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from evoclaw.sqlite_memory import SQLiteMemoryStore


class SQLiteMemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmpdir.name) / "memory"
        (self.memory_root / "experiences").mkdir(parents=True, exist_ok=True)
        self.db_path = self.memory_root / "memory.db"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_init_and_query_experiences(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        store.upsert_experience(
            {
                "id": "exp-1",
                "type": "conversation",
                "content": "hello world",
                "source": "trump",
                "created_at": "2026-03-08T00:00:00",
                "updated_at": "2026-03-08T00:00:00",
                "significance": "routine",
                "tags": ["test"],
                "metadata": {"lang": "zh"},
            }
        )

        rows = store.query_experiences(text_query="hello", limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "exp-1")
        self.assertEqual(rows[0]["metadata"]["lang"], "zh")

    def test_upsert_experience_without_id_generates_stable_id(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        payload = {
            "type": "conversation",
            "content": "no explicit id",
            "source": "tester",
            "created_at": "2026-03-08T00:00:01",
            "updated_at": "2026-03-08T00:00:01",
        }
        store.upsert_experience(payload)
        store.upsert_experience(payload)

        with store._connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM experiences").fetchone()["c"]
        self.assertEqual(count, 1)

    def test_init_schema_creates_all_tables(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        with store._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            views = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
            ).fetchall()
        tables = {row["name"] for row in rows}
        view_names = {row["name"] for row in views}
        self.assertTrue(
            {
                "memories",
                "proposals",
                "reflections",
                "graph_entities",
                "graph_relations",
                "soul_history",
                "rules",
                "candidates",
                "system_state",
                "system_logs",
            }.issubset(tables)
        )
        self.assertIn("experiences", view_names)

    def test_init_schema_migrates_feedback_hook_out_of_memories(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        store.upsert_experience(
            {
                "id": "legacy-feedback-1",
                "type": "feedback_hook",
                "content": '{"hook":"after_task"}',
                "source": "feedback_system",
                "created_at": "2026-03-08T05:00:00",
                "updated_at": "2026-03-08T05:00:00",
                "metadata": {"feedback": {"hook": "after_task"}},
            }
        )

        store.init_schema()
        with store._connect() as conn:
            legacy_in_memories = conn.execute(
                "SELECT COUNT(*) AS c FROM memories WHERE type='feedback_hook'"
            ).fetchone()["c"]
            logs = conn.execute(
                "SELECT COUNT(*) AS c FROM system_logs WHERE log_type='feedback_hook'"
            ).fetchone()["c"]
        self.assertEqual(legacy_in_memories, 0)
        self.assertEqual(logs, 1)

    def test_init_schema_creates_memories_fts_and_triggers(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        with store._connect() as conn:
            fts_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
            ).fetchone()
            trigger_rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='trigger' AND name IN ('memories_ai', 'memories_ad', 'memories_au')
                ORDER BY name
                """
            ).fetchall()
        self.assertIsNotNone(fts_table)
        self.assertEqual([r["name"] for r in trigger_rows], ["memories_ad", "memories_ai", "memories_au"])

    def test_memories_fts_syncs_on_upsert_without_manual_rebuild(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()
        store.upsert_experience(
            {
                "id": "exp-fts-1",
                "type": "conversation",
                "content": "alpha token present",
                "source": "tester",
                "created_at": "2026-03-08T02:00:00",
                "updated_at": "2026-03-08T02:00:00",
                "significance": "routine",
            }
        )
        with store._connect() as conn:
            alpha = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM memories_fts
                WHERE memories_fts MATCH 'alpha'
                """
            ).fetchone()["c"]
        self.assertEqual(alpha, 1)

        store.upsert_experience(
            {
                "id": "exp-fts-1",
                "type": "conversation",
                "content": "beta token present",
                "source": "tester",
                "created_at": "2026-03-08T02:00:00",
                "updated_at": "2026-03-08T02:01:00",
                "significance": "routine",
            }
        )
        with store._connect() as conn:
            alpha_after_update = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM memories_fts
                WHERE memories_fts MATCH 'alpha'
                """
            ).fetchone()["c"]
            beta_after_update = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM memories_fts
                WHERE memories_fts MATCH 'beta'
                """
            ).fetchone()["c"]
        self.assertEqual(alpha_after_update, 0)
        self.assertEqual(beta_after_update, 1)

    def test_upsert_non_experience_records(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()

        store.upsert_proposal(
            {
                "id": "prop-1",
                "type": "insight",
                "content": "content",
                "source": "rss",
                "created_at": "2026-03-08T01:00:00",
                "updated_at": "2026-03-08T01:00:00",
                "status": "approved",
                "priority": "medium",
                "approved_at": "2026-03-08T01:01:00",
                "tags": ["approved"],
                "metadata": {"a": 1},
            }
        )
        store.upsert_reflection(
            {
                "id": "ref-1",
                "timestamp": "2026-03-08T01:02:00",
                "trigger": "manual",
                "notable_count": 2,
                "analysis": {"insights": ["x"]},
                "proposals": [{"id": "prop-1"}],
            }
        )
        store.upsert_entity(
            {
                "id": "entity-1",
                "type": "Skill",
                "properties": {"name": "web_fetch"},
                "created_at": "2026-03-08T01:03:00",
            }
        )
        store.upsert_relation(
            {
                "id": "rel-1",
                "source_id": "entity-1",
                "target_id": "entity-1",
                "relation_type": "depends_on",
                "properties": {"weight": 1},
                "created_at": "2026-03-08T01:04:00",
            }
        )
        store.upsert_soul_change(
            {
                "id": "chg-1",
                "change_type": "add_knowledge",
                "old_value": "a",
                "new_value": "b",
                "created_at": "2026-03-08T01:05:00",
                "approved": True,
            }
        )
        store.upsert_state("evoclaw_state", {"ok": True}, "2026-03-08T01:06:00")
        store.upsert_system_log(
            {
                "id": "syslog-1",
                "log_type": "feedback_hook",
                "source": "feedback_system",
                "content": "{\"hook\":\"before_task\"}",
                "created_at": "2026-03-08T01:06:30",
                "updated_at": "2026-03-08T01:06:30",
                "level": "info",
                "metadata": {"hook": "before_task"},
            }
        )
        store.upsert_rule(
            {
                "id": "rule-1",
                "content": {"text": "必须先备份", "priority": "P2_TASK_TYPE"},
                "source_proposal_id": "prop-1",
                "created_at": "2026-03-08T01:07:00",
                "enabled": True,
            }
        )

        with store._connect() as conn:
            p = conn.execute("SELECT COUNT(*) AS c FROM proposals").fetchone()["c"]
            r = conn.execute("SELECT COUNT(*) AS c FROM reflections").fetchone()["c"]
            e = conn.execute("SELECT COUNT(*) AS c FROM graph_entities").fetchone()["c"]
            rel = conn.execute("SELECT COUNT(*) AS c FROM graph_relations").fetchone()["c"]
            chg = conn.execute("SELECT COUNT(*) AS c FROM soul_history").fetchone()["c"]
            rules = conn.execute("SELECT COUNT(*) AS c FROM rules").fetchone()["c"]
            st = conn.execute("SELECT COUNT(*) AS c FROM system_state").fetchone()["c"]
            logs = conn.execute("SELECT COUNT(*) AS c FROM system_logs").fetchone()["c"]
        self.assertEqual(p, 1)
        self.assertEqual(r, 1)
        self.assertEqual(e, 1)
        self.assertEqual(rel, 1)
        self.assertEqual(chg, 1)
        self.assertEqual(rules, 1)
        self.assertEqual(st, 1)
        self.assertEqual(logs, 1)

    def test_migration_script_imports_jsonl(self):
        src = self.memory_root / "experiences" / "2026-03-08.jsonl"
        src.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "id": "exp-a",
                            "type": "conversation",
                            "content": "第一条",
                            "source": "trump",
                            "created_at": "2026-03-08T01:00:00",
                            "updated_at": "2026-03-08T01:00:00",
                            "tags": ["routine"],
                            "metadata": {"significance": "routine"},
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "id": "exp-b",
                            "type": "rss",
                            "message": "第二条",
                            "source": "feed",
                            "timestamp": "2026-03-08T01:01:00",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "python3",
                "scripts/migrate_experiences_to_sqlite.py",
                "--memory-root",
                str(self.memory_root),
                "--db-path",
                str(self.db_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        store = SQLiteMemoryStore(self.db_path)
        rows = store.query_experiences(limit=10)
        self.assertEqual(len(rows), 2)
        ids = {row["id"] for row in rows}
        self.assertEqual(ids, {"exp-a", "exp-b"})

    def test_migrate_all_script_imports_all_tables(self):
        (self.memory_root / "semantic").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "significant").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "proposals").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "reflections").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "graph").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "skill_performance").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "tasks").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "working").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "feedback").mkdir(parents=True, exist_ok=True)

        (self.memory_root / "experiences" / "2026-03-08.jsonl").write_text(
            json.dumps(
                {
                    "id": "exp-1",
                    "type": "conversation",
                    "content": "hello",
                    "source": "trump",
                    "created_at": "2026-03-08T00:00:00",
                    "updated_at": "2026-03-08T00:00:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "semantic" / "2026-03.jsonl").write_text(
            json.dumps(
                {
                    "id": "sem-1",
                    "type": "knowledge",
                    "content": "k",
                    "source": "semantic",
                    "created_at": "2026-03-08T00:01:00",
                    "updated_at": "2026-03-08T00:01:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "significant" / "significant.jsonl").write_text(
            json.dumps(
                {
                    "id": "sig-1",
                    "type": "notable",
                    "content": "s",
                    "source": "significant",
                    "created_at": "2026-03-08T00:02:00",
                    "updated_at": "2026-03-08T00:02:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "proposals" / "approved.jsonl").write_text(
            json.dumps(
                {
                    "id": "prop-1",
                    "type": "insight",
                    "content": "p",
                    "source": "rss",
                    "created_at": "2026-03-08T00:03:00",
                    "updated_at": "2026-03-08T00:03:00",
                    "metadata": {"status": "approved", "priority": "high"},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "reflections" / "REF-1.json").write_text(
            json.dumps(
                {
                    "id": "REF-1",
                    "timestamp": "2026-03-08T00:04:00",
                    "trigger": "manual",
                    "notable_count": 1,
                    "analysis": {"a": 1},
                    "proposals": [{"id": "prop-1"}],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "graph" / "entities.jsonl").write_text(
            json.dumps(
                {
                    "id": "ent-1",
                    "type": "Skill",
                    "properties": {"x": 1},
                    "created_at": "2026-03-08T00:05:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "graph" / "relations.jsonl").write_text(
            json.dumps(
                {
                    "id": "rel-1",
                    "source_id": "ent-1",
                    "target_id": "ent-1",
                    "relation_type": "uses",
                    "properties": {"y": 2},
                    "created_at": "2026-03-08T00:06:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "soul_changes.jsonl").write_text(
            json.dumps(
                {
                    "id": "chg-1",
                    "change_type": "add",
                    "old_value": "",
                    "new_value": "v",
                    "created_at": "2026-03-08T00:07:00",
                    "approved": True,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "evoclaw-state.json").write_text(
            json.dumps({"last_reflection_at": "2026-03-08T00:08:00"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.memory_root / "tasks" / "2026-03-08.jsonl").write_text(
            json.dumps({"task_id": "t-1", "event": "started"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "working" / "t-1.json").write_text(
            json.dumps({"task_id": "t-1", "state": "active"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.memory_root / "feedback" / "2026-03-08.jsonl").write_text(
            json.dumps({"hook": "before_task"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.memory_root / "skill_performance" / "performance.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "skill_id": "web_fetch_skill",
                            "task_type": "research",
                            "success": True,
                            "latency_ms": 120.0,
                            "rework": False,
                            "error": None,
                            "timestamp": "2026-03-08T01:00:00",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "skill_id": "web_fetch_skill",
                            "task_type": "research",
                            "success": False,
                            "latency_ms": 240.0,
                            "rework": True,
                            "error": "timeout",
                            "timestamp": "2026-03-08T01:10:00",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "python3",
                "scripts/migrate_all_to_sqlite.py",
                "--memory-root",
                str(self.memory_root),
                "--db-path",
                str(self.db_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        store = SQLiteMemoryStore(self.db_path)
        with store._connect() as conn:
            experiences = conn.execute("SELECT COUNT(*) AS c FROM experiences").fetchone()["c"]
            proposals = conn.execute("SELECT COUNT(*) AS c FROM proposals").fetchone()["c"]
            reflections = conn.execute("SELECT COUNT(*) AS c FROM reflections").fetchone()["c"]
            graph_entities = conn.execute("SELECT COUNT(*) AS c FROM graph_entities").fetchone()["c"]
            graph_relations = conn.execute("SELECT COUNT(*) AS c FROM graph_relations").fetchone()["c"]
            soul_history = conn.execute("SELECT COUNT(*) AS c FROM soul_history").fetchone()["c"]
            candidates = conn.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"]
            states = conn.execute("SELECT COUNT(*) AS c FROM system_state").fetchone()["c"]

        self.assertEqual(experiences, 3)
        self.assertEqual(proposals, 1)
        self.assertEqual(reflections, 1)
        self.assertEqual(graph_entities, 1)
        self.assertEqual(graph_relations, 1)
        self.assertEqual(soul_history, 1)
        self.assertEqual(candidates, 1)
        self.assertGreaterEqual(states, 4)

    def test_migrate_experience_schema_v2_from_legacy_table(self):
        with SQLiteMemoryStore(self.db_path)._connect() as conn:
            conn.execute(
                """
                CREATE TABLE experiences (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    significance TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO experiences (
                    id, type, content, source, created_at, updated_at,
                    significance, tags_json, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-exp-1",
                    "conversation",
                    "hello",
                    "trump",
                    "2026-03-08T00:00:00",
                    "2026-03-08T00:00:00",
                    "routine",
                    json.dumps(["x"], ensure_ascii=False),
                    json.dumps({"channel": "telegram"}, ensure_ascii=False),
                    json.dumps({"id": "legacy-exp-1", "type": "conversation", "content": "hello"}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                INSERT INTO experiences (
                    id, type, content, source, created_at, updated_at,
                    significance, tags_json, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-exp-2",
                    "rss_active",
                    "rss content",
                    "https://hnrss.org/frontpage",
                    "2026-03-08T00:01:00",
                    "2026-03-08T00:01:00",
                    "notable",
                    "[]",
                    json.dumps({"title": "rss title", "link": "https://example.com"}, ensure_ascii=False),
                    json.dumps({"id": "legacy-exp-2", "type": "rss_active", "content": "rss content"}, ensure_ascii=False),
                ),
            )

        result = subprocess.run(
            [
                "python3",
                "scripts/migrate_experience_schema_v2.py",
                "--db-path",
                str(self.db_path),
                "--no-backup",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        store = SQLiteMemoryStore(self.db_path)
        rows = store.query_experiences(limit=10)
        self.assertEqual(len(rows), 2)
        ids = {row["id"] for row in rows}
        self.assertEqual(ids, {"legacy-exp-1", "legacy-exp-2"})

        with store._connect() as conn:
            legacy_exists = conn.execute(
                "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name='experiences_legacy'"
            ).fetchone()["c"]
            view_exists = conn.execute(
                "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='view' AND name='experiences'"
            ).fetchone()["c"]
            conv_count = conn.execute("SELECT COUNT(*) AS c FROM memories_conversation").fetchone()["c"]
            rss_count = conn.execute("SELECT COUNT(*) AS c FROM memories_rss").fetchone()["c"]
        self.assertEqual(legacy_exists, 1)
        self.assertEqual(view_exists, 1)
        self.assertEqual(conv_count, 1)
        self.assertEqual(rss_count, 1)

    def test_query_helpers_for_proposals_reflections_soul_history_and_recent_experiences(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()

        store.upsert_proposal(
            {
                "id": "prop-pending",
                "type": "learning_insight",
                "content": "pending proposal",
                "source": "cron",
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00",
                "status": "pending",
                "metadata": {"k": "v"},
            }
        )
        store.upsert_proposal(
            {
                "id": "prop-approved",
                "type": "rule",
                "content": "approved proposal",
                "source": "cron",
                "created_at": "2026-03-08T11:00:00",
                "updated_at": "2026-03-08T11:00:00",
                "status": "approved",
            }
        )

        store.upsert_reflection(
            {
                "id": "ref-older",
                "timestamp": "2026-03-08T09:00:00",
                "trigger": "manual",
                "notable_count": 1,
                "analysis": {"a": 1},
                "proposals": [],
                "created_at": "2026-03-08T09:00:00",
            }
        )
        store.upsert_reflection(
            {
                "id": "ref-newer",
                "timestamp": "2026-03-08T12:00:00",
                "trigger": "cron",
                "notable_count": 2,
                "analysis": {"b": 2},
                "proposals": [{"id": "prop-approved"}],
                "created_at": "2026-03-08T12:00:00",
            }
        )

        store.upsert_soul_change(
            {
                "id": "chg-no",
                "change_type": "modify",
                "old_value": "a",
                "new_value": "b",
                "created_at": "2026-03-08T08:00:00",
                "approved": False,
            }
        )
        store.upsert_soul_change(
            {
                "id": "chg-yes",
                "change_type": "add",
                "old_value": "",
                "new_value": "c",
                "created_at": "2026-03-08T13:00:00",
                "approved": True,
            }
        )

        store.upsert_experience(
            {
                "id": "exp-recent",
                "type": "conversation",
                "content": "recent",
                "source": "tester",
                "created_at": "2099-01-01T00:00:00",
                "updated_at": "2099-01-01T00:00:00",
            }
        )
        store.upsert_experience(
            {
                "id": "exp-old",
                "type": "conversation",
                "content": "old",
                "source": "tester",
                "created_at": "2000-01-01T00:00:00",
                "updated_at": "2000-01-01T00:00:00",
            }
        )

        pending = store.query_proposals(status="pending", limit=10)
        self.assertEqual([r["id"] for r in pending], ["prop-pending"])

        rule_type = store.query_proposals(prop_type="rule", limit=10)
        self.assertEqual([r["id"] for r in rule_type], ["prop-approved"])

        reflections = store.query_reflections(limit=1)
        self.assertEqual(len(reflections), 1)
        self.assertEqual(reflections[0]["id"], "ref-newer")
        self.assertEqual(reflections[0]["analysis"]["b"], 2)

        approved_changes = store.query_soul_history(approved=True, limit=10)
        self.assertEqual([r["id"] for r in approved_changes], ["chg-yes"])
        unapproved_changes = store.query_soul_history(approved=False, limit=10)
        self.assertEqual([r["id"] for r in unapproved_changes], ["chg-no"])

        store.upsert_rule(
            {
                "id": "rule-enabled",
                "content": {"text": "只读模式", "priority": "P1_GOVERNANCE"},
                "source_proposal_id": "prop-approved",
                "created_at": "2026-03-08T13:10:00",
                "enabled": True,
            }
        )
        store.upsert_rule(
            {
                "id": "rule-disabled",
                "content": {"text": "禁用规则"},
                "source_proposal_id": "prop-pending",
                "created_at": "2026-03-08T13:11:00",
                "enabled": False,
            }
        )
        active_rules = store.query_rules(enabled=True, limit=10)
        self.assertEqual([r["id"] for r in active_rules], ["rule-enabled"])
        self.assertEqual(active_rules[0]["content_json"]["text"], "只读模式")

        recent = store.query_recent_experiences(hours=24, limit=10)
        self.assertEqual([r["id"] for r in recent], ["exp-recent"])

    def test_upsert_and_query_candidates(self):
        store = SQLiteMemoryStore(self.db_path)
        store.init_schema()

        store.upsert_candidate(
            {
                "candidate_id": "cand-1",
                "skill_id": "web_fetch_skill",
                "task_type": "research",
                "status": "candidate",
                "source": "skill_performance",
                "score": 0.92,
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00",
                "metadata": {"success_rate": 0.9, "sample_size": 10},
            }
        )

        store.upsert_candidate(
            {
                "candidate_id": "cand-2",
                "skill_id": "notion_api",
                "task_type": "writing",
                "status": "validated",
                "source": "manual",
                "score": 0.8,
                "created_at": "2026-03-08T11:00:00",
                "updated_at": "2026-03-08T11:00:00",
                "metadata": {"success_rate": 0.75, "sample_size": 8},
            }
        )

        candidates = store.query_candidates(status="candidate", limit=10)
        self.assertEqual([c["id"] for c in candidates], ["cand-1"])
        self.assertEqual(candidates[0]["metadata"]["success_rate"], 0.9)

        by_skill = store.query_candidates(skill_id="notion_api", limit=10)
        self.assertEqual([c["id"] for c in by_skill], ["cand-2"])


if __name__ == "__main__":
    unittest.main()
