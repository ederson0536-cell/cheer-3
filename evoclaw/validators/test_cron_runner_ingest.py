#!/usr/bin/env python3
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from evoclaw import cron_runner
from evoclaw.sqlite_memory import SQLiteMemoryStore


class CronRunnerIngestTests(unittest.TestCase):
    def setUp(self):
        self._old_workspace = cron_runner.WORKSPACE
        self._old_store = cron_runner._MEMORY_STORE
        self._tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmpdir.name)
        cron_runner.WORKSPACE = self.workspace
        cron_runner._MEMORY_STORE = None

        (self.workspace / "evoclaw").mkdir(parents=True, exist_ok=True)
        (self.workspace / "memory/experiences").mkdir(parents=True, exist_ok=True)
        (self.workspace / "logs").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        cron_runner.WORKSPACE = self._old_workspace
        cron_runner._MEMORY_STORE = self._old_store
        self._tmpdir.cleanup()

    def _write_config(self, config):
        (self.workspace / "evoclaw/config.json").write_text(
            json.dumps(config, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_step1_ingest_rss_dedups_by_link_and_records_history(self):
        self._write_config(
            {
                "sources": {
                    "rss": {"enabled": True, "feeds": ["https://example.com/feed"]},
                    "conversation": {"enabled": True},
                }
            }
        )

        store = SQLiteMemoryStore(self.workspace / "memory/memory.db")
        store.init_schema()
        store.upsert_experience(
            {
                "id": "exp-existing",
                "type": "rss_active",
                "content": "existing",
                "source": "https://example.com/feed",
                "created_at": "2026-03-08T00:00:00",
                "updated_at": "2026-03-08T00:00:00",
                "metadata": {"link": "https://dup.example/item-1", "entry_id": "dup-1"},
            }
        )

        fake_feed = types.SimpleNamespace(
            entries=[
                {
                    "id": "dup-1",
                    "title": "dup",
                    "summary": "dup summary",
                    "link": "https://dup.example/item-1",
                },
                {
                    "id": "new-1",
                    "title": "new",
                    "summary": "new summary",
                    "link": "https://new.example/item-2",
                },
            ]
        )

        with patch.dict("sys.modules", {"feedparser": types.SimpleNamespace(parse=lambda _: fake_feed)}):
            created = cron_runner.step1_ingest()

        self.assertEqual(created, 1)
        rss_rows = store.query_experiences(exp_type="rss_active", limit=10)
        self.assertEqual(len(rss_rows), 2)
        links = {row["metadata"].get("link") for row in rss_rows}
        self.assertIn("https://dup.example/item-1", links)
        self.assertIn("https://new.example/item-2", links)

        state = json.loads((self.workspace / "memory/evoclaw-state.json").read_text(encoding="utf-8"))
        self.assertTrue(state.get("rss_last_fetched"))
        self.assertTrue(state.get("rss_fetch_history"))
        self.assertEqual(state["rss_fetch_history"][-1]["new_count"], 1)

    def test_step1_ingest_projects_task_runs_to_notebook_layers(self):
        self._write_config(
            {
                "sources": {
                    "rss": {"enabled": False, "feeds": []},
                    "conversation": {"enabled": True},
                }
            }
        )

        store = SQLiteMemoryStore(self.workspace / "memory/memory.db")
        store.init_schema()
        store.upsert_task_run(
            {
                "task_id": "task-satisfied",
                "task_name": "满意任务",
                "task_type": "conversation",
                "status": "completed",
                "success": True,
                "satisfaction": "satisfied",
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00",
                "metadata": {"message_id": "msg-1", "user_message": "第一条消息"},
            }
        )
        store.upsert_task_run(
            {
                "task_id": "task-unsatisfied",
                "task_name": "不满意任务",
                "task_type": "conversation",
                "status": "completed",
                "success": True,
                "satisfaction": "unsatisfied",
                "significance": "notable",
                "created_at": "2026-03-08T10:01:00",
                "updated_at": "2026-03-08T10:01:00",
                "metadata": {"message_id": "msg-2", "user_message": "第二条消息"},
            }
        )

        created = cron_runner.step1_ingest()
        self.assertEqual(created, 1)

        task_rows = store.query_experiences(exp_type="task_execution", source="task_runs", limit=10)
        self.assertEqual(len(task_rows), 1)
        self.assertEqual(task_rows[0]["metadata"].get("task_id"), "task-satisfied")

        nb_exp = store.query_notebook_experiences(limit=10)
        nb_ref = store.query_notebook_reflections(limit=10)
        nb_prop = store.query_notebook_proposals(limit=10)
        nb_rules = store.query_notebook_rules(limit=10)
        self.assertEqual(len(nb_exp), 2)
        self.assertEqual(len(nb_ref), 2)
        self.assertEqual(len(nb_prop), 2)
        self.assertEqual(len(nb_rules), 1)
        self.assertEqual(nb_rules[0]["notebook_rule_id"], "nbrule-task-unsatisfied")

        state = json.loads((self.workspace / "memory/evoclaw-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state.get("last_notebook_projection_counts", {}).get("notebook_experiences"), 2)
        self.assertEqual(state.get("last_notebook_projection_counts", {}).get("notebook_reflections"), 2)
        self.assertEqual(state.get("last_notebook_projection_counts", {}).get("notebook_proposals"), 2)
        self.assertEqual(state.get("last_notebook_projection_counts", {}).get("notebook_rules"), 1)

        created_again = cron_runner.step1_ingest()
        self.assertEqual(created_again, 0)


if __name__ == "__main__":
    unittest.main()
