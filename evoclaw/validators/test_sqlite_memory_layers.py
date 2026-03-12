#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from evoclaw.sqlite_memory import SQLiteMemoryStore


class SQLiteMemoryLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "memory.db"
        self.store = SQLiteMemoryStore(self.db_path)
        self.store.init_schema()

    def tearDown(self):
        self.tmp.cleanup()

    def test_layered_tables_have_minimal_dao_roundtrip(self):
        self.store.upsert_external_learning_event(
            {
                "event_id": "evt-1",
                "source_type": "rss",
                "source_name": "feed",
                "title": "t",
                "content": "c",
                "url": "u",
                "collected_at": "2026-03-12T00:00:00",
                "status": "new",
            }
        )
        self.assertTrue(self.store.mark_external_learning_event_status("evt-1", "processed"))
        events = self.store.query_external_learning_events(status="processed", limit=10)
        self.assertEqual(len(events), 1)

        self.store.upsert_task_run(
            {
                "task_id": "task-1",
                "task_name": "task",
                "task_type": "conversation",
                "status": "completed",
                "created_at": "2026-03-12T00:00:00",
                "updated_at": "2026-03-12T00:00:00",
            }
        )

        self.store.upsert_notebook_experience(
            {
                "notebook_exp_id": "nexp-1",
                "task_id": "task-1",
                "content": "task summary",
                "summary": "sum",
                "created_at": "2026-03-12T00:00:01",
            }
        )
        self.assertTrue(self.store.mark_notebook_experience_status("nexp-1", "projected"))
        exps = self.store.query_notebook_experiences(task_id="task-1", limit=10)
        self.assertEqual(len(exps), 1)

        self.store.upsert_notebook_reflection(
            {
                "notebook_reflection_id": "nref-1",
                "notebook_exp_id": "nexp-1",
                "trigger": "projection",
                "analysis": {"k": "v"},
            }
        )
        self.assertTrue(self.store.mark_notebook_reflection_status("nref-1", "reviewed"))
        refs = self.store.query_notebook_reflections(notebook_exp_id="nexp-1", limit=10)
        self.assertEqual(len(refs), 1)

        self.store.upsert_notebook_proposal(
            {
                "notebook_proposal_id": "nprop-1",
                "notebook_reflection_id": "nref-1",
                "proposal_type": "opt",
                "content": "proposal",
                "status": "pending",
            }
        )
        self.assertTrue(self.store.mark_notebook_proposal_status("nprop-1", "approved"))
        props = self.store.query_notebook_proposals(status="approved", limit=10)
        self.assertEqual(len(props), 1)

        self.store.upsert_notebook_rule(
            {
                "notebook_rule_id": "nrule-1",
                "notebook_proposal_id": "nprop-1",
                "rule_type": "guard",
                "content": "rule",
                "enabled": True,
            }
        )
        self.assertTrue(self.store.mark_notebook_rule_status("nrule-1", False))
        rules = self.store.query_notebook_rules(enabled=False, limit=10)
        self.assertEqual(len(rules), 1)

        self.store.upsert_entity(
            {
                "id": "entity-1",
                "entity_type": "topic",
                "properties": {"name": "topic"},
                "created_at": "2026-03-12T00:00:00",
            }
        )
        self.store.upsert_relation(
            {
                "id": "rel-1",
                "source_id": "entity-1",
                "target_id": "entity-1",
                "relation_type": "self",
                "properties": {},
                "created_at": "2026-03-12T00:00:00",
            }
        )
        self.store.upsert_semantic_knowledge(
            {
                "semantic_id": "sem-1",
                "entity_id": "entity-1",
                "relation_id": "rel-1",
                "content": "semantic",
                "source": "projection",
            }
        )
        self.assertTrue(self.store.mark_semantic_knowledge_status("sem-1", "indexed"))
        sem = self.store.query_semantic_knowledge(entity_id="entity-1", limit=10)
        self.assertEqual(len(sem), 1)


    def test_query_experiences_tolerates_invalid_json_payloads(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, category, type, content, source, created_at, updated_at,
                    significance, tags_json, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "exp-bad-json",
                    "experience",
                    "conversation",
                    "bad row",
                    "test",
                    "2026-03-12T00:00:00",
                    "2026-03-12T00:00:00",
                    "routine",
                    "[bad-json",
                    "{bad-json",
                    "",
                ),
            )

        rows = self.store.query_experiences(limit=5)
        self.assertEqual(rows[0]["id"], "exp-bad-json")
        self.assertEqual(rows[0]["tags"], [])
        self.assertEqual(rows[0]["metadata"], {})

        logs = self.store.query_system_logs(log_type="json_decode_warning", limit=10)
        self.assertTrue(logs)

    def test_relationship_consistency_check_reports_zero_for_clean_data(self):
        self.store.upsert_task_run(
            {
                "task_id": "task-clean",
                "task_name": "t",
                "task_type": "conversation",
                "status": "completed",
                "created_at": "2026-03-12T00:00:00",
                "updated_at": "2026-03-12T00:00:00",
            }
        )
        self.store.upsert_notebook_experience(
            {
                "notebook_exp_id": "nexp-clean",
                "task_id": "task-clean",
                "content": "c",
                "created_at": "2026-03-12T00:00:01",
                "updated_at": "2026-03-12T00:00:02",
            }
        )
        self.store.upsert_notebook_reflection(
            {
                "notebook_reflection_id": "nref-clean",
                "notebook_exp_id": "nexp-clean",
                "trigger": "projection",
            }
        )
        self.store.upsert_notebook_proposal(
            {
                "notebook_proposal_id": "nprop-clean",
                "notebook_reflection_id": "nref-clean",
                "proposal_type": "opt",
                "content": "p",
            }
        )
        self.store.upsert_notebook_rule(
            {
                "notebook_rule_id": "nrule-clean",
                "notebook_proposal_id": "nprop-clean",
                "rule_type": "guard",
                "content": "r",
            }
        )

        report = self.store.run_relationship_consistency_check()
        self.assertEqual(report.get("total_issues"), 0)



if __name__ == "__main__":
    unittest.main()
