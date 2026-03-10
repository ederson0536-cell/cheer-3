import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class UnifyMemorySchemaScriptTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self.tmpdir.name)
        for dirname in ("experiences", "significant", "semantic", "candidate", "proposals"):
            (self.memory_dir / dirname).mkdir(parents=True, exist_ok=True)

        (self.memory_dir / "experiences" / "2026-03-08.jsonl").write_text(
            '{"timestamp":"2026-03-08T01:00:00","type":"conversation","message":"hello","source":"chat","tags":["a"]}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "significant" / "significant.jsonl").write_text(
            '{"task_id":"t1","timestamp":"2026-03-08T02:00:00","significance":"notable","message":"sig"}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "semantic" / "2026-03.jsonl").write_text(
            '{"content":"knowledge","promoted_at":"2026-03-08T03:00:00","source":"proposal"}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "candidate" / "candidates.jsonl").write_text(
            '{"candidate_id":"c1","knowledge":"candidate","created_at":"2026-03-08T04:00:00","updated_at":"2026-03-08T05:00:00","context":{"tags":["x"]}}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "proposals" / "approved.jsonl").write_text(
            '{"id":"p1","type":"insight","content":"approved","source":"rss","timestamp":"2026-03-08T06:00:00","status":"approved"}\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run_script(self, *args):
        return subprocess.run(
            ["python3", "scripts/unify_memory_schema.py", "--memory-root", str(self.memory_dir), *args],
            check=False,
            text=True,
            capture_output=True,
        )

    def test_dry_run_does_not_modify_files(self):
        before = (self.memory_dir / "experiences" / "2026-03-08.jsonl").read_text(encoding="utf-8")
        result = self._run_script()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        after = (self.memory_dir / "experiences" / "2026-03-08.jsonl").read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertIn('"dry_run": true', result.stdout)

    def test_apply_converts_records_to_unified_schema(self):
        result = self._run_script("--apply")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        sample_files = [
            self.memory_dir / "experiences" / "2026-03-08.jsonl",
            self.memory_dir / "significant" / "significant.jsonl",
            self.memory_dir / "semantic" / "2026-03.jsonl",
            self.memory_dir / "candidate" / "candidates.jsonl",
            self.memory_dir / "proposals" / "approved.jsonl",
        ]
        required_keys = {
            "id",
            "type",
            "content",
            "source",
            "created_at",
            "updated_at",
            "tags",
            "metadata",
        }

        for file_path in sample_files:
            lines = [line for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreater(len(lines), 0)
            row = json.loads(lines[0])
            self.assertEqual(set(row.keys()), required_keys)
            self.assertIsInstance(row["tags"], list)
            self.assertIsInstance(row["metadata"], dict)

        backup_files = list(self.memory_dir.rglob("*.bak"))
        self.assertGreater(len(backup_files), 0)


if __name__ == "__main__":
    unittest.main()
