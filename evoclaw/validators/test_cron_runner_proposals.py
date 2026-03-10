#!/usr/bin/env python3
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from evoclaw import cron_runner
from evoclaw.sqlite_memory import SQLiteMemoryStore


class CronRunnerProposalTests(unittest.TestCase):
    def setUp(self):
        self._old_workspace = cron_runner.WORKSPACE
        self._old_memory_store = cron_runner._MEMORY_STORE
        self._tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmpdir.name)
        cron_runner.WORKSPACE = self.workspace
        cron_runner._MEMORY_STORE = None

        (self.workspace / "evoclaw").mkdir(parents=True, exist_ok=True)
        (self.workspace / "memory/experiences").mkdir(parents=True, exist_ok=True)
        (self.workspace / "memory/proposals").mkdir(parents=True, exist_ok=True)
        (self.workspace / "evoclaw/config.json").write_text(
            json.dumps(
                {
                    "governance": {"level": "autonomous"},
                    "reflection": {"notable_batch_size": 2},
                }
            ),
            encoding="utf-8",
        )
        self.store = SQLiteMemoryStore(self.workspace / "memory/memory.db")
        self.store.init_schema()

    def tearDown(self):
        cron_runner.WORKSPACE = self._old_workspace
        cron_runner._MEMORY_STORE = self._old_memory_store
        self._tmpdir.cleanup()

    def _write_jsonl(self, path: Path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path):
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_step3_propose_dedups_similar_recent_learning_insight(self):
        now = datetime.now()
        self.store.upsert_experience(
            {
                "id": "exp-1",
                "type": "rss_active",
                "significance": "notable",
                "title": "AI release",
                "content": "AI release",
                "source": "test",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        self.store.upsert_experience(
            {
                "id": "exp-2",
                "type": "conversation",
                "significance": "notable",
                "content": "记住我的偏好",
                "source": "test",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        self.store.upsert_proposal(
            {
                "id": "prop-old",
                "timestamp": (now - timedelta(minutes=2)).isoformat(),
                "created_at": (now - timedelta(minutes=2)).isoformat(),
                "updated_at": now.isoformat(),
                "type": "learning_insight",
                "content": "从 2 条 Notable 经验中发现趋势 (主动: 1, 被动: 1)",
                "sources": {"active": 1, "passive": 1},
                "status": "pending",
                "priority": "medium",
            }
        )

        proposals = cron_runner.step3_propose(2)
        rows = self.store.query_proposals(status="pending", limit=10)

        self.assertEqual(proposals, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "prop-old")

    def test_step4_govern_only_approves_pending_without_duplicate_reapprove(self):
        now = datetime.now()
        self.store.upsert_proposal(
            {
                "id": "prop-approved-in-pending",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "type": "learning_insight",
                "content": "already approved",
                "status": "approved",
            }
        )
        self.store.upsert_proposal(
            {
                "id": "prop-dup",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "type": "learning_insight",
                "content": "duplicate id should not be re-appended",
                "status": "pending",
            }
        )
        self.store.upsert_proposal(
            {
                "id": "prop-new",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "type": "learning_insight",
                "content": "fresh pending",
                "status": "pending",
            }
        )
        self.store.upsert_proposal(
            {
                "id": "prop-dup",
                "timestamp": (now - timedelta(minutes=10)).isoformat(),
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "updated_at": (now - timedelta(minutes=10)).isoformat(),
                "type": "learning_insight",
                "content": "existing approved",
                "status": "approved",
            }
        )

        approved_count = cron_runner.step4_govern()
        approved_rows = self.store.query_proposals(status="approved", limit=20)
        pending_rows = self.store.query_proposals(status="pending", limit=20)

        self.assertEqual(approved_count, 1)
        self.assertEqual(sorted(r["id"] for r in approved_rows), ["prop-approved-in-pending", "prop-dup", "prop-new"])
        self.assertEqual(pending_rows, [])

    def test_apply_to_rules_generates_sqlite_and_active_json(self):
        now = datetime.now().isoformat()
        approved = [
            {
                "id": "prop-rule-1",
                "type": "task_rule",
                "status": "approved",
                "content": "执行前必须检查测试结果",
                "task_type": "coding",
                "priority_level": "P2",
                "approved_at": now,
            }
        ]

        applied = cron_runner._apply_to_rules(approved)
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["change_type"], "add_rule")

        rules = self.store.query_rules(enabled=True, source_proposal_id="prop-rule-1", limit=10)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "rule-prop-rule-1")
        self.assertEqual(rules[0]["content_json"]["priority"], "P2_TASK_TYPE")

        rule_file = self.workspace / "memory" / "rules" / "active" / "rule-prop-rule-1.json"
        self.assertTrue(rule_file.exists())


if __name__ == "__main__":
    unittest.main()
