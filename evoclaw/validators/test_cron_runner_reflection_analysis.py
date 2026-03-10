#!/usr/bin/env python3
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from evoclaw import cron_runner
from evoclaw.sqlite_memory import SQLiteMemoryStore


class CronRunnerReflectionAnalysisTests(unittest.TestCase):
    def setUp(self):
        self._old_workspace = cron_runner.WORKSPACE
        self._old_store = cron_runner._MEMORY_STORE
        self._tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmpdir.name)
        cron_runner.WORKSPACE = self.workspace
        cron_runner._MEMORY_STORE = None

        (self.workspace / "evoclaw").mkdir(parents=True, exist_ok=True)
        (self.workspace / "memory/experiences").mkdir(parents=True, exist_ok=True)
        (self.workspace / "memory/reflections").mkdir(parents=True, exist_ok=True)
        (self.workspace / "evoclaw/config.json").write_text(
            json.dumps(
                {
                    "reflection": {"notable_batch_size": 2},
                    "sources": {"rss": {"enabled": False}, "conversation": {"enabled": True}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.store = SQLiteMemoryStore(self.workspace / "memory/memory.db")
        self.store.init_schema()

    def tearDown(self):
        cron_runner.WORKSPACE = self._old_workspace
        cron_runner._MEMORY_STORE = self._old_store
        self._tmpdir.cleanup()

    def test_analyze_notable_experiences_extracts_content_trends(self):
        exps = [
            {
                "id": "exp-a",
                "type": "conversation",
                "significance": "notable",
                "content": "今天继续优化 AI 工具链，修复 Python 测试失败问题",
            },
            {
                "id": "exp-b",
                "type": "conversation",
                "significance": "notable",
                "content": "AI 模型评估流程需要自动化工具，增加测试覆盖",
            },
            {
                "id": "exp-c",
                "type": "rss_active",
                "significance": "notable",
                "content": "New AI coding tool release improves workflow automation",
            },
        ]

        analysis = cron_runner._analyze_notable_experiences(exps)

        self.assertEqual(analysis["sample_size"], 3)
        self.assertTrue(analysis["top_keywords"])
        self.assertIn("ai", analysis["theme_distribution"])
        self.assertGreaterEqual(analysis["theme_distribution"]["ai"], 2)
        self.assertTrue(analysis["patterns"])
        self.assertTrue(analysis["insights"])

    def test_step2_reflect_persists_structured_content_analysis(self):
        now = datetime.now().isoformat()
        self.store.upsert_experience(
            {
                "id": "exp-1",
                "type": "conversation",
                "significance": "notable",
                "content": "记录 AI 工具使用偏好，优化编程效率并修复测试",
                "source": "message_handler",
                "created_at": now,
                "updated_at": now,
            }
        )
        self.store.upsert_experience(
            {
                "id": "exp-2",
                "type": "rss_active",
                "significance": "notable",
                "title": "AI coding tool update",
                "summary": "new automation workflow for developers",
                "content": "AI tool update and coding workflow automation",
                "source": "rss",
                "created_at": now,
                "updated_at": now,
            }
        )

        notable_count = cron_runner.step2_reflect()
        self.assertEqual(notable_count, 2)

        rows = self.store.query_reflections(limit=5)
        self.assertTrue(rows)
        analysis = rows[0].get("analysis", {})
        self.assertIn("content_trends", analysis)
        content_trends = analysis["content_trends"]
        self.assertGreaterEqual(content_trends.get("sample_size", 0), 2)
        self.assertIn("top_keywords", content_trends)
        self.assertIn("theme_distribution", content_trends)
        self.assertIn("patterns", content_trends)
        self.assertIn("insights", content_trends)
        self.assertTrue(content_trends["insights"])


if __name__ == "__main__":
    unittest.main()
