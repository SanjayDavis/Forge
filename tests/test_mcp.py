"""M5 MCP server test suite — the wire protocol, the six tools, the
boundary, and interop with the real `mcp` SDK client.

The MCP server is the roadmap's thin transport: JSON-RPC 2.0 over
stdio, six tools, one SDK call each, zero business logic. Tests cover:

  The wire:      initialize handshake, notifications, tools/list,
                 JSON-RPC faults (parse, method-not-found,
                 invalid-params), tool failures as isError results.
  The tools:     forge_next / forge_context / forge_propose /
                 forge_verify / forge_query / forge_replay — each
                 maps to exactly one SDK method.
  The boundary:  server.py consumes ONLY the public SDK — no kernel
                 internals, no `mcp` SDK dependency, no file writes,
                 no business logic.
  Interop:       the real `mcp` Python SDK client (if installed)
                 connects over stdio and drives all six tools — the
                 server is a genuine MCP server, not a lookalike.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "packages", "forge-planner"))

from forge import ForgeClient  # noqa: E402
from forge_planner import ReferencePlanner  # noqa: E402
from plugins.mcp import TOOLS, ForgeMCPServer  # noqa: E402

SERVER = os.path.join(REPO, "plugins", "mcp", "server.py")
MCP_CLIENT = os.path.join(REPO, "plugins", "mcp", "mcp_client.py")
TOOL_NAMES = ["forge_next", "forge_context", "forge_propose",
              "forge_verify", "forge_query", "forge_replay"]


def _proposed_project() -> tuple[ForgeClient, str]:
    d = tempfile.mkdtemp()
    client = ForgeClient(d)
    client.propose(ReferencePlanner().plan("Build a Snake game"))
    return client, d


class _Wire:
    """A minimal JSON-RPC client for talking to a spawned server over
    stdio — the same framing any MCP client uses."""

    def __init__(self, directory: str):
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
        self.p = subprocess.Popen(
            [sys.executable, SERVER, "-d", directory],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)
        self._mid = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._mid += 1
        payload = {"jsonrpc": "2.0", "id": self._mid, "method": method}
        if params is not None:
            payload["params"] = params
        assert self.p.stdin is not None and self.p.stdout is not None
        self.p.stdin.write(json.dumps(payload) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise AssertionError(
                f"server closed without answering {method}: "
                f"{self.p.stderr.read()}")
        return json.loads(line)

    def notify(self, method: str) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": method}) + "\n")
        self.p.stdin.flush()

    def tool(self, name: str, arguments: dict | None = None) -> dict:
        resp = self.call("tools/call", {"name": name,
                                        "arguments": arguments or {}})
        self.assert_ok(resp)
        return resp["result"]

    @staticmethod
    def assert_ok(resp: dict) -> None:
        assert "result" in resp, f"expected a result, got: {resp}"

    @staticmethod
    def text(resp: dict) -> str:
        return resp["result"]["content"][0]["text"]

    def close(self) -> None:
        assert self.p.stdin is not None
        self.p.stdin.close()
        self.p.wait(timeout=10)
        # close the read pipes too, or the wrappers leak (ResourceWarning)
        if self.p.stdout is not None:
            self.p.stdout.close()
        if self.p.stderr is not None:
            self.p.stderr.close()


def _handshake(w: _Wire) -> dict:
    resp = w.call("initialize", {"protocolVersion": "2025-11-25",
                                 "capabilities": {},
                                 "clientInfo": {"name": "test",
                                                "version": "0"}})
    w.notify("notifications/initialized")
    return resp


class TestWire(unittest.TestCase):
    """The JSON-RPC 2.0 layer: handshake, framing, faults."""

    def test_initialize_handshake(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = _handshake(w)
            result = resp["result"]
            self.assertEqual(result["serverInfo"]["name"], "forge")
            self.assertEqual(result["protocolVersion"], "2025-11-25")
            self.assertIn("tools", result["capabilities"])
        finally:
            w.close()

    def test_initialize_echoes_known_older_version(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = w.call("initialize", {"protocolVersion": "2024-11-05",
                                         "capabilities": {}})
            self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")
        finally:
            w.close()

    def test_notifications_get_no_response(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            w.notify("notifications/initialized")
            w.notify("notifications/cancelled")
            # the next real request must be answered immediately, proving
            # no response was buffered for the notifications
            resp = w.call("ping")
            self.assertEqual(resp["result"], {})
        finally:
            w.close()

    def test_tools_list_six_tools_with_schemas(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = w.call("tools/list")
            tools = resp["result"]["tools"]
            self.assertEqual([t["name"] for t in tools], TOOL_NAMES)
            for t in tools:
                self.assertIn("description", t)
                self.assertEqual(t["inputSchema"]["type"], "object")
        finally:
            w.close()

    def test_parse_error_is_32700(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            assert w.p.stdin is not None and w.p.stdout is not None
            w.p.stdin.write("this is not json\n")
            w.p.stdin.flush()
            resp = json.loads(w.p.stdout.readline())
            self.assertEqual(resp["error"]["code"], -32700)
        finally:
            w.close()

    def test_unknown_method_is_32601(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = w.call("bogus_method", {})
            self.assertEqual(resp["error"]["code"], -32601)
        finally:
            w.close()

    def test_missing_required_argument_is_32602(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = w.call("tools/call", {"name": "forge_context",
                                         "arguments": {}})
            self.assertEqual(resp["error"]["code"], -32602)
            self.assertIn("task_id", resp["error"]["message"])
        finally:
            w.close()

    def test_invalid_params_type_is_32602(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            resp = w.call("tools/call", {"name": "forge_context",
                                         "arguments": "nope"})
            self.assertEqual(resp["error"]["code"], -32602)
        finally:
            w.close()


class TestTools(unittest.TestCase):
    """Each tool is exactly one SDK call — and nothing else."""

    def test_forge_next_returns_snapshot(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            body = w.tool("forge_next")
            task = json.loads(body["content"][0]["text"])
            self.assertIn("id", task)
            self.assertIn("title", task)
            self.assertEqual(task["status"], "todo")
        finally:
            w.close()

    def test_forge_next_null_when_nothing_ready(self):
        d = tempfile.mkdtemp()
        ForgeClient(d)
        w = _Wire(d)
        try:
            _handshake(w)
            body = w.tool("forge_next")
            self.assertEqual(body["content"][0]["text"], "null")
        finally:
            w.close()

    def test_forge_context_returns_the_contract_package(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            nxt = json.loads(w.text(w.call("tools/call",
                                           {"name": "forge_next"})))
            body = w.tool("forge_context", {"task_id": nxt["id"]})
            yaml = body["content"][0]["text"]
            self.assertIn("Task:", yaml)
            self.assertIn("Acceptance:", yaml)
            self.assertIn("Evidence:", yaml)
        finally:
            w.close()

    def test_forge_propose_commits_atomically(self):
        d = tempfile.mkdtemp()
        ForgeClient(d)
        w = _Wire(d)
        try:
            _handshake(w)
            proposal = ReferencePlanner().plan("Write a stub")
            body = w.tool("forge_propose", {"proposal": proposal})
            info = json.loads(body["content"][0]["text"])
            self.assertGreaterEqual(info["committed"], 1)
            self.assertGreaterEqual(info["tasks"], 1)
            # the tasks are really there, committed through the kernel
            g = ForgeClient(d).kernel.graph
            self.assertEqual(len(g.tasks), info["tasks"])
        finally:
            w.close()

    def test_forge_propose_invalid_envelope_is_tool_error(self):
        d = tempfile.mkdtemp()
        ForgeClient(d)
        w = _Wire(d)
        try:
            _handshake(w)
            resp = w.call("tools/call", {"name": "forge_propose",
                                         "arguments": {
                                             "proposal": {"proposal_id": "x",
                                                          "confidence": "high",
                                                          "events": []}}})
            self.assertIn("result", resp)
            self.assertTrue(resp["result"]["isError"])
            self.assertIn("reason", resp["result"]["content"][0]["text"])
        finally:
            w.close()

    def test_forge_verify_refuses_unstarted_task(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            nxt = json.loads(w.text(w.call("tools/call",
                                           {"name": "forge_next"})))
            resp = w.call("tools/call", {"name": "forge_verify",
                                         "arguments": {"task_id": nxt["id"]}})
            self.assertTrue(resp["result"]["isError"])
            self.assertIn("in-progress", resp["result"]["content"][0]["text"])
        finally:
            w.close()

    def test_forge_verify_passes_after_start(self):
        client, d = _proposed_project()
        tid = client.next()["id"]
        client.start(tid)  # the test may; the server never does
        w = _Wire(d)
        try:
            _handshake(w)
            resp = w.call("tools/call", {"name": "forge_verify",
                                         "arguments": {"task_id": tid}})
            self.assertFalse(resp["result"]["isError"])
            info = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(info["id"], tid)
        finally:
            w.close()

    def test_forge_query_runs_the_query_grammar(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            body = w.tool("forge_query", {"expr": "status == todo"})
            ids = json.loads(body["content"][0]["text"])
            self.assertEqual(len(ids), 3)  # the three snake children
            body = w.tool("forge_query",
                          {"expr": "status == done and priority == high"})
            self.assertEqual(json.loads(body["content"][0]["text"]), [])
        finally:
            w.close()

    def test_forge_replay_reports_state(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            body = w.tool("forge_replay")
            rep = json.loads(body["content"][0]["text"])
            self.assertEqual(rep["tasks"], 4)  # root + three children
            self.assertGreaterEqual(rep["events"], 4)
            self.assertEqual(rep["done"], 0)
        finally:
            w.close()

    def test_unknown_tool_is_tool_error(self):
        client, d = _proposed_project()
        w = _Wire(d)
        try:
            _handshake(w)
            resp = w.call("tools/call", {"name": "forge_bogus",
                                         "arguments": {}})
            self.assertTrue(resp["result"]["isError"])
            self.assertIn("forge_bogus", resp["result"]["content"][0]["text"])
        finally:
            w.close()


class TestBoundary(unittest.TestCase):
    """The server is a transport: SDK only, stdlib only, no business
    logic, no file writes, no kernel internals."""

    @classmethod
    def setUpClass(cls):
        with open(SERVER, encoding="utf-8") as f:
            cls.src = f.read()

    def test_consumes_only_the_public_sdk(self):
        self.assertIn("from forge import ForgeClient", self.src)
        for banned in ("forge.kernel", "forge.model", "forge.store",
                       "forge.context", "from .", "import_events",
                       ".graph", "Store(", "Kernel(", ".kernel",
                       "plugins."):
            self.assertNotIn(banned, self.src,
                             f"server must not reference {banned!r}")

    def test_no_business_logic(self):
        # a tool is one SDK call; there is no orchestration here
        for banned in ("next_task(", "while True", "client.start(",
                       "attach_evidence", "verify_fail", "retry(",
                       "expand("):
            self.assertNotIn(banned, self.src,
                             f"server must not contain {banned!r}")

    def test_no_file_writes(self):
        for banned in ("open(", "os.write", "write_text", "write_bytes",
                       "Path(", "shutil", "tempfile"):
            self.assertNotIn(banned, self.src,
                             f"server must not write files ({banned!r})")

    def test_no_mcp_sdk_dependency(self):
        # the reference server implements the protocol itself; the only
        # imports are stdlib + the forge SDK
        for banned in ("import mcp", "from mcp", "fastmcp", "anyio",
                       "pydantic"):
            self.assertNotIn(banned, self.src)

    def test_plugin_imports_are_public(self):
        from plugins.mcp import (ForgeMCPServer, PROTOCOL_VERSION,  # noqa
                                 SERVER_INFO, TOOLS, main)
        self.assertEqual(len(TOOLS), 6)
        self.assertEqual(SERVER_INFO["name"], "forge")


class TestMCPServerClient(unittest.TestCase):
    """End to end: a planner proposal is committed, then the reference
    MCP client walks the six tools over the wire."""

    def test_client_walks_six_tools_over_stdio(self):
        d = tempfile.mkdtemp()
        env = dict(os.environ, PYTHONPATH=REPO)
        subprocess.run(["forge", "-d", d, "init"], check=True,
                       capture_output=True, env=env)
        prop = ReferencePlanner().plan("Build a Snake game")
        prop_path = os.path.join(d, "prop.json")
        with open(prop_path, "w", encoding="utf-8") as f:
            json.dump(prop, f)
        subprocess.run(["forge", "-d", d, "propose", prop_path],
                       check=True, capture_output=True, env=env)

        r = subprocess.run([sys.executable, MCP_CLIENT, "-d", d],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("server: forge 0.1.0-alpha", out)
        self.assertIn("tools: 6", out)
        self.assertIn("next: build-a-snake-game-foundation", out)
        self.assertIn("Task:", out)
        self.assertIn("verify: ERROR", out)  # not started — gate refuses
        self.assertIn("query: 1 in-progress task(s)", out)
        self.assertIn("replay:", out)


class TestInteropWithOfficialSDK(unittest.TestCase):
    """The real `mcp` Python SDK client connects to our hand-rolled
    server and drives all six tools. Skipped when the SDK is not
    installed — the canonical suite stays dependency-free."""

    def setUp(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("mcp SDK not installed")
        import anyio  # noqa: F401
        self.anyio = anyio

    def _drive(self, client: ForgeClient, d: str):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
        params = StdioServerParameters(command=sys.executable,
                                       args=[SERVER, "-d", d], env=env)

        async def run():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert [t.name for t in tools.tools] == TOOL_NAMES

                    nxt = await session.call_tool("forge_next", {})
                    text = nxt.content[0].text
                    task = json.loads(text)
                    assert task["status"] == "todo"

                    ctx = await session.call_tool(
                        "forge_context", {"task_id": task["id"]})
                    assert "Task:" in ctx.content[0].text

                    ver = await session.call_tool(
                        "forge_verify", {"task_id": task["id"]})
                    assert ver.isError is True
                    assert "in-progress" in ver.content[0].text

                    q = await session.call_tool(
                        "forge_query", {"expr": "status == todo"})
                    assert len(json.loads(q.content[0].text)) == 3

                    rp = await session.call_tool("forge_replay", {})
                    rep = json.loads(rp.content[0].text)
                    assert rep["tasks"] == 4

                    prop = await session.call_tool(
                        "forge_propose",
                        {"proposal": ReferencePlanner().plan("Write a stub")})
                    info = json.loads(prop.content[0].text)
                    assert info["committed"] > 0
            return True

        self.assertTrue(self.anyio.run(run))

    def _drive_empty(self, d: str):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
        params = StdioServerParameters(command=sys.executable,
                                       args=[SERVER, "-d", d], env=env)

        async def run():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert [t.name for t in tools.tools] == TOOL_NAMES
                    nxt = await session.call_tool("forge_next", {})
                    assert nxt.content[0].text == "null"
                    rp = await session.call_tool("forge_replay", {})
                    rep = json.loads(rp.content[0].text)
                    assert rep["tasks"] == 0
            return True

        self.assertTrue(self.anyio.run(run))

    def test_official_client_drives_all_six_tools(self):
        client, d = _proposed_project()
        self._drive(client, d)

    def test_official_client_on_empty_project(self):
        d = tempfile.mkdtemp()
        ForgeClient(d)
        self._drive_empty(d)


if __name__ == "__main__":
    unittest.main()
