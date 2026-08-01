"""M5 — the MCP server plugin (SPEC Appendix A: plugins are clients of
the kernel API; MCP interfaces may evolve freely).

The Forge wire protocol in one file, stdlib-only: JSON-RPC 2.0 over
stdio, one JSON object per line (the MCP stdio framing), six tools —
forge_next, forge_context, forge_propose, forge_verify, forge_query,
forge_replay — each a thin pass-through to one SDK method. No business
logic: the server is a transport, and that is the whole point. The
kernel decides; the SDK exposes; this translates JSON-RPC to SDK calls
and back.

    python plugins/mcp/server.py -d PROJECT

Clients: any MCP client (Claude, Hermes, `mcp` SDK) speaks to it over
stdio. This reference server implements the protocol itself — no `mcp`
SDK dependency — so the plugin stays as boring as the roadmap promises.
It consumes ONLY the public SDK (forge.ForgeClient). No kernel
internals, no graph, no replay of its own: everything the tools return
comes from SDK methods.

Tool semantics (one SDK call each, nothing more):
  forge_next      -> ForgeClient.next()
  forge_context   -> ForgeClient.context(task_id)     (the YAML package)
  forge_propose   -> ForgeClient.propose(proposal)
  forge_verify    -> ForgeClient.verify(task_id)
  forge_query     -> ForgeClient.query(expr)
  forge_replay    -> ForgeClient.replay()

Errors: a tool that raises GraphError / ProposalError comes back as an
MCP tool error (isError result, message = the kernel's), never as a
JSON-RPC fault — the protocol layer itself only faults on protocol
violations (parse errors, unknown methods, missing arguments).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from forge import ForgeClient, GraphError, ProposalError

# The MCP protocol version this server speaks. Clients negotiate at
# initialize; we echo a known version back (2024-11-05 and later are
# wire-compatible for tools-only servers), defaulting to the newest.
PROTOCOL_VERSION = "2025-11-25"
KNOWN_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")

SERVER_INFO = {"name": "forge", "version": "0.1.0-alpha"}

JSON_RPC = "2.0"
# JSON-RPC error codes (the MCP spec reuses these verbatim).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MethodNotFound(Exception):
    """A JSON-RPC-level fault: the client called a method this server
    does not implement. Distinct from a tool that failed (isError)."""


class MissingArgument(Exception):
    """A tools/call request omitted a required inputSchema argument.
    A JSON-RPC fault (-32602), distinct from KeyErrors a tool handler
    may raise internally (those are tool failures, isError)."""


def _json_text(value: Any) -> str:
    """Tool results are JSON text; the context package is already YAML."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def _tool(name: str, description: str, props: dict[str, Any],
          required: list[str], fn: Callable[[ForgeClient, dict], str]) -> dict:
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props,
                            "required": required},
            "handler": fn}


TOOLS: list[dict[str, Any]] = [
    _tool(
        "forge_next",
        "The single next work item: highest priority, then creation "
        "order. Returns a task snapshot, or null when nothing is ready.",
        {}, [],
        lambda c, a: _json_text(c.next())),
    _tool(
        "forge_context",
        "The Context Contract package for TASK (Task / Description / "
        "Acceptance / Dependencies / Knowledge / Relevant Files / "
        "Evidence / Constraints), as the same YAML every client reads.",
        {"task_id": {"type": "string"}}, ["task_id"],
        lambda c, a: c.context(a["task_id"])),
    _tool(
        "forge_propose",
        "Commit a proposal atomically (SPEC §9): envelope validated, "
        "then the kernel validates and applies — whole or nothing. "
        "Takes the full proposal object (proposal_id, confidence, "
        "events) and returns the commit result.",
        {"proposal": {"type": "object"}}, ["proposal"],
        lambda c, a: _json_text(c.propose(a["proposal"]))),
    _tool(
        "forge_verify",
        "Run the verifier gate (I6) on TASK: only started tasks with "
        "all dependencies done can pass; the kernel decides done.",
        {"task_id": {"type": "string"}}, ["task_id"],
        lambda c, a: _json_text(c.verify(a["task_id"]))),
    _tool(
        "forge_query",
        "Run a query over the task graph (safe expression subset: "
        "status, priority, evidence_count, files, depends_on, and/or/"
        "not, comparison operators). Returns matching task ids.",
        {"expr": {"type": "string"}}, ["expr"],
        lambda c, a: _json_text(c.query(a["expr"]))),
    _tool(
        "forge_replay",
        "Replay the event log and report the project state: event "
        "count, task count, done count.",
        {}, [],
        lambda c, a: _json_text(c.replay())),
]


class ForgeMCPServer:
    """JSON-RPC 2.0 over stdio, one JSON object per line. Every request
    maps to exactly one SDK call; every result is a kernel verdict."""

    def __init__(self, directory: str = ".") -> None:
        self.client = ForgeClient(directory)
        self.tools = {t["name"]: t for t in TOOLS}

    # ------------------------------------------------------------------ wire
    def handle_line(self, line: str) -> str | None:
        """One incoming JSON-RPC message -> one response line (or None
        for notifications, which never get a response)."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return self._error(None, PARSE_ERROR, "parse error")
        if not isinstance(msg, dict) or msg.get("jsonrpc") != JSON_RPC:
            return self._error(msg.get("id") if isinstance(msg, dict) else None,
                               INVALID_REQUEST, "invalid request")
        method = msg.get("method")
        if not isinstance(method, str):
            return self._error(msg.get("id"), INVALID_REQUEST, "invalid request")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            return self._error(msg.get("id"), INVALID_PARAMS,
                               "params must be an object")
        is_notification = "id" not in msg

        try:
            result = self._dispatch(method, params)
        except MethodNotFound:
            return self._error(msg.get("id"), METHOD_NOT_FOUND,
                               f"method not found: {method}")
        except GraphError as exc:
            return self._tool_error(msg.get("id"), method, str(exc))
        except ProposalError as exc:
            return self._tool_error(msg.get("id"), method, str(exc))
        except MissingArgument as exc:
            return self._error(msg.get("id"), INVALID_PARAMS,
                               f"missing required argument: {exc}")
        except Exception as exc:  # tool failure, not a protocol fault
            return self._tool_error(msg.get("id"), method, str(exc))

        if is_notification:
            return None
        return self._result(msg["id"], result)

    def _dispatch(self, method: str, params: dict) -> Any:
        if method == "initialize":
            requested = params.get("protocolVersion")
            return {"protocolVersion": requested if requested in KNOWN_VERSIONS
                    else PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [{"name": t["name"],
                               "description": t["description"],
                               "inputSchema": t["inputSchema"]}
                              for t in TOOLS]}
        if method == "tools/call":
            name = params.get("name")
            tool = self.tools.get(name)
            if tool is None:
                raise GraphError(f"unknown tool: {name}")
            args = params.get("arguments") or {}
            if not isinstance(args, dict):
                raise MissingArgument("arguments (must be an object)")
            for req in tool["inputSchema"].get("required", []):
                if req not in args:
                    raise MissingArgument(req)
            text = tool["handler"](self.client, args)
            return {"content": [{"type": "text", "text": text}],
                    "isError": False}
        # notifications we accept silently
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        raise MethodNotFound(method)

    # ------------------------------------------------------------------ json
    @staticmethod
    def _result(msg_id: Any, result: Any) -> str:
        return json.dumps({"jsonrpc": JSON_RPC, "id": msg_id, "result": result},
                          ensure_ascii=False)

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> str:
        return json.dumps({"jsonrpc": JSON_RPC, "id": msg_id,
                           "error": {"code": code, "message": message}},
                          ensure_ascii=False)

    @staticmethod
    def _tool_error(msg_id: Any, method: str, message: str) -> str:
        """A tool that failed is a tool result (isError), not a JSON-RPC
        fault — the transport stays healthy; the kernel's verdict is
        the message."""
        return json.dumps({"jsonrpc": JSON_RPC, "id": msg_id,
                           "result": {"content": [{"type": "text",
                                                   "text": message}],
                                      "isError": True}},
                          ensure_ascii=False)

    # ------------------------------------------------------------------ loop
    def run(self) -> int:
        """Serve until EOF. One JSON object per line, per the MCP stdio
        framing. Errors go to stderr; stdout carries protocol only."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_line(line)
            if response is not None:
                print(response, flush=True)
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="forge-mcp",
        description="Forge MCP server: JSON-RPC 2.0 over stdio, six "
                    "tools, one SDK call each")
    ap.add_argument("-d", "--dir", default=".",
                    help="project directory (default: .)")
    args = ap.parse_args(argv)
    return ForgeMCPServer(args.dir).run()


if __name__ == "__main__":
    sys.exit(main())
