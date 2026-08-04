"""Reference MCP client — the MCP slot, runnable.

Speaks the MCP wire protocol (JSON-RPC 2.0 over stdio) to a spawned
forge-mcp server, exactly like any MCP client would: initialize,
notifications/initialized, tools/list, then the six tools. This is the
roadmap's forge_next / forge_context / forge_propose / forge_verify /
forge_query / forge_replay surface, exercised over the wire instead of
through the SDK directly — proving the server is a real MCP server,
not a local helper.

    python -m forge_mcp.mcp_client -d PROJECT [--limit N]

A walk: propose (if given a proposal file), next, context, verify,
query, replay — the six tools in one pass over whatever is ready.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# This client may be run from a checkout (packages/forge-mcp) or from an
# installed package; either way the directory containing the `forge_mcp`
# package is the parent of this file, so `python -m forge_mcp.server`
# resolves whether the distribution is installed or not.
PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rpc(p: subprocess.Popen, msg_id: int, method: str,
        params: dict | None = None) -> dict:
    """Send one JSON-RPC request over stdio, read one response line."""
    payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    assert p.stdin is not None and p.stdout is not None
    p.stdin.write(json.dumps(payload) + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    if not line:
        raise RuntimeError("server closed the connection")
    return json.loads(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="mcp-client",
        description="reference MCP client: walk the six forge tools "
                    "over the wire")
    ap.add_argument("-d", "--dir", default=".",
                    help="project directory (default: .)")
    ap.add_argument("--proposal", default=None,
                    help="proposal JSON file to commit first (optional)")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    env["PYTHONPATH"] = PKG_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    server = [sys.executable, "-m", "forge_mcp.server", "-d", args.dir]
    p = subprocess.Popen(server,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", env=env)

    msg_id = [0]

    def call(method: str, params: dict | None = None) -> dict:
        msg_id[0] += 1
        return rpc(p, msg_id[0], method, params)

    # ---- handshake
    init = call("initialize", {"protocolVersion": "2025-11-25",
                               "capabilities": {},
                               "clientInfo": {"name": "mcp-client",
                                              "version": "0.1.0"}})
    print(f"server: {init['result']['serverInfo']['name']} "
          f"{init['result']['serverInfo']['version']} — protocol "
          f"{init['result']['protocolVersion']}")
    # notifications/initialized: no response expected
    p.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    p.stdin.flush()

    tools = call("tools/list")
    names = [t["name"] for t in tools["result"]["tools"]]
    print(f"tools: {len(names)} — {', '.join(names)}")

    # ---- optional proposal commit
    if args.proposal:
        with open(args.proposal, encoding="utf-8") as f:
            proposal = json.load(f)
        res = call("tools/call", {"name": "forge_propose",
                                  "arguments": {"proposal": proposal}})
        body = res["result"]
        if body.get("isError"):
            print(f"propose: ERROR — {body['content'][0]['text']}")
        else:
            info = json.loads(body["content"][0]["text"])
            print(f"propose: {info['committed']} events committed "
                  f"({len(info['tasks'])} tasks)")

    # ---- the six-tool walk
    nxt = call("tools/call", {"name": "forge_next", "arguments": {}})
    body = nxt["result"]
    if body.get("isError"):
        print(f"next: ERROR — {body['content'][0]['text']}")
    elif body["content"][0]["text"] == "null":
        print("next: none")
    else:
        task = json.loads(body["content"][0]["text"])
        print(f"next: {task['id']} — {task['title']} ({task['status']})")

        ctx = call("tools/call", {"name": "forge_context",
                                  "arguments": {"task_id": task["id"]}})
        print(f"context: {ctx['result']['content'][0]['text']}")

        ver = call("tools/call", {"name": "forge_verify",
                                  "arguments": {"task_id": task["id"]}})
        vbody = ver["result"]
        if vbody.get("isError"):
            print(f"verify: ERROR — {vbody['content'][0]['text']}")
        else:
            print(f"verify: {json.loads(vbody['content'][0]['text'])}")

    q = call("tools/call", {"name": "forge_query",
                            "arguments": {"expr": "status == in_progress"}})
    ids = json.loads(q["result"]["content"][0]["text"])
    print(f"query: {len(ids)} in-progress task(s)")

    rp = call("tools/call", {"name": "forge_replay", "arguments": {}})
    rep = json.loads(rp["result"]["content"][0]["text"])
    print(f"replay: {rep['events']} events, {rep['tasks']} tasks, "
          f"{rep['done']} done")

    p.stdin.close()
    p.wait(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
