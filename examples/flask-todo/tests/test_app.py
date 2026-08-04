"""End-to-end tests for the Flask task manager."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.db import init_db  # noqa: E402


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})

    def test_index_lists_tasks(self):
        self.client.post("/add", data={"title": "buy milk"})
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"buy milk", r.data)

    def test_add_redirects(self):
        r = self.client.post("/add", data={"title": "write tests"})
        self.assertEqual(r.status_code, 302)

    def test_done_is_idempotent(self):
        self.client.post("/add", data={"title": "finish task"})
        first = self.client.post("/done/1")
        second = self.client.post("/done/1")
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)  # regression: was 404

    def test_done_unknown_404(self):
        r = self.client.post("/done/999")
        self.assertEqual(r.status_code, 404)

    def test_delete(self):
        self.client.post("/add", data={"title": "remove me"})
        r = self.client.post("/delete/1")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn(b"remove me", self.client.get("/").data)

    def test_delete_unknown_404(self):
        r = self.client.post("/delete/999")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
