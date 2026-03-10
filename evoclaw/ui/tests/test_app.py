import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from evoclaw.ui.app import create_app


class MemoryUiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self.tmpdir.name)
        (self.memory_dir / "experiences").mkdir(parents=True)
        (self.memory_dir / "experiences" / "sample.jsonl").write_text(
            '{"id":"1","type":"routine","content":"alpha note","created_at":"2026-03-07T01:00:00"}\n'
            '{"id":"2","type":"notable","content":"beta note","created_at":"2026-03-08T01:00:00"}\n'
            '{"id":"3","type":"notable","content":"gamma","created_at":"2026-03-06T01:00:00"}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "semantic").mkdir(parents=True)
        (self.memory_dir / "semantic" / "entry.jsonl").write_text(
            '{"id":"s1","type":"knowledge","content":"delta"}\n',
            encoding="utf-8",
        )
        (self.memory_dir / "state.json").write_text(
            json.dumps({"ok": True}, ensure_ascii=False),
            encoding="utf-8",
        )

        app = create_app(self.memory_dir)
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_index_lists_files(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("experiences/sample.jsonl", resp.get_data(as_text=True))

    def test_view_jsonl_renders_table(self):
        resp = self.client.get("/file/experiences/sample.jsonl")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<table", body)
        self.assertIn("routine", body)

    def test_index_supports_search_sort_and_pagination(self):
        resp = self.client.get("/?q=semantic&page=1&page_size=1&sort=path&order=asc")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("semantic/entry.jsonl", body)
        self.assertNotIn("experiences/sample.jsonl", body)

    def test_view_jsonl_supports_search_sort_and_pagination(self):
        rel = quote("experiences/sample.jsonl", safe="")
        resp = self.client.get(
            f"/file/{rel}?q=note&page=1&page_size=1&sort=created_at&order=desc"
        )
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("beta note", body)
        self.assertIn("共 2 条，当前第 1 / 2 页", body)

    def test_view_contains_manual_edit_form(self):
        rel = quote("experiences/sample.jsonl", safe="")
        resp = self.client.get(f"/file/{rel}")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<textarea", body)
        self.assertIn("/save/experiences/sample.jsonl", body)

    def test_save_json_updates_file(self):
        resp = self.client.post(
            "/save/state.json",
            data={"content": '{"ok": false, "count": 1}'},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        saved = (self.memory_dir / "state.json").read_text(encoding="utf-8")
        self.assertIn('"count": 1', saved)


if __name__ == "__main__":
    unittest.main()
