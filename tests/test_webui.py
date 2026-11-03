"""Smoke tests for the Forge web UI (stdlib server)."""

import json
import threading
import time
import unittest
import urllib.request

from forge.kernel import Kernel
from forge.store import Store
from forge.webui import serve


class TestWebUI(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.d = tempfile.mkdtemp()
        Store(self.d).init()
        Kernel(self.d).create_task("Demo", "d", priority="high")
        self.port = 8817

    def _run_server(self):
        # serve blocks; run in thread
        import forge.webui as w
        k = __import__("forge.kernel", fromlist=["Kernel"]).Kernel(self.d)
        handler = lambda *a, **kw: w._Handler(*a, kernel=k, **kw)

        class S(w.socketserver.TCPServer):
            allow_reuse_address = True
        self.httpd = S(("127.0.0.1", self.port), handler)
        self.httpd.serve_forever()

    def test_index_and_api(self):
        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
                self.assertEqual(r.status, 200)
                self.assertIn(b"Forge Task Board", r.read())
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/data") as r:
                data = json.loads(r.read())
            self.assertEqual(len(data["tasks"]), 1)
            self.assertIn("progress", data)
        finally:
            self.httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
