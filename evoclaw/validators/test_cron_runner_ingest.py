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

    def test_step1_ingest_conversation_fallback_from_message_log(self):
        self._write_config(
            {
                "sources": {
                    "rss": {"enabled": False, "feeds": []},
                    "conversation": {"enabled": True},
                }
            }
        )
        (self.workspace / "memory/evoclaw-state.json").write_text(
            json.dumps({"last_conversation_check": "2026-03-07T00:00:00"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.workspace / "logs/message_handler.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-03-08T10:00:00",
                            "event": "receive",
                            "message": "第一条对话",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-03-08T10:05:00",
                            "event": "task_started",
                            "message": "ignored",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-03-08T10:06:00",
                            "event": "receive",
                            "message": "第二条对话",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        created = cron_runner.step1_ingest()
        self.assertEqual(created, 2)

        store = SQLiteMemoryStore(self.workspace / "memory/memory.db")
        conv_rows = store.query_experiences(exp_type="conversation", limit=10)
        self.assertEqual(len(conv_rows), 2)
        self.assertEqual({r["content"] for r in conv_rows}, {"第一条对话", "第二条对话"})
        self.assertEqual({r["source"] for r in conv_rows}, {"message_handler"})

        created_again = cron_runner.step1_ingest()
        self.assertEqual(created_again, 0)


if __name__ == "__main__":
    unittest.main()
