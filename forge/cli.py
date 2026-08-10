"""Forge CLI (`forge`).

A human can run an entire software project through this interface. LLM
clients (planner/executor/verifier agents) emit exactly the same events
through the same Kernel API.

Usage: forge <command> [args]  (run `forge --help` or `forge <command> --help`)
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .context import STATUS_ICON
from .kernel import Kernel
from .model import GraphError
from .scheduler import is_container
from .store import EVENT_FILE, Store


# --------------------------------------------------------------------------- helpers
def _setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _node_label(g: Graph, tid: str) -> str:
    t = g.tasks[tid]
    eff = t.effective_status(g.tasks)
    label = tid
    if t.title and t.title != tid:
        label += f" — {t.title}"
    if is_container(t):
        label += " (group)"
    return f"{label} {STATUS_ICON[eff]}"


def _print_tree(g: Graph, tid: str, prefix: str, is_last: bool, seen: set[str]) -> None:
    # seen holds the current ancestry path only. A repeat along the path is
    # a true cycle; a node re-printed under a different branch (a DAG with
    # multiple parents) is legitimate and must not be flagged.
    if tid in seen:
        print(prefix + ("└── " if is_last else "├── ") + f"{tid} (cycle!)")
        return
    seen.add(tid)
    print(prefix + ("└── " if is_last else "├── ") + _node_label(g, tid))
    kids = sorted((g.tasks[d] for d in g.tasks[tid].depends_on), key=lambda t: t.created_seq)
    child_prefix = prefix + ("    " if is_last else "│   ")
    for i, kid in enumerate(kids):
        _print_tree(g, kid.id, child_prefix, i == len(kids) - 1, seen)
    seen.remove(tid)


def _parse_child(spec: str) -> dict:
    """'Title', 'Title::desc', or 'Title::desc::acc1;acc2'."""
    parts = spec.split("::")
    title = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else ""
    acceptance = [a.strip() for a in parts[2].split(";") if a.strip()] if len(parts) > 2 else []
    return {"title": title, "description": desc, "acceptance": acceptance}


# --------------------------------------------------------------------------- demo seed
def _seed_demo(k: Kernel) -> None:
    k.create_task("Snake Game", "A terminal snake game built via Forge.",
                  acceptance=["game runs", "unit tests pass"], priority="high")
    k.expand("snake-game", [
        {"title": "Window", "description": "Terminal window setup", "acceptance": ["renders a frame"]},
        {"title": "Renderer", "description": "Draws the board state", "acceptance": ["renders snakes, food, score"]},
        {"title": "Input", "description": "Keyboard controls", "acceptance": ["arrow keys move the snake"]},
        {"title": "Snake Logic", "description": "Movement and growth", "acceptance": ["grows on food"]},
        {"title": "Food", "description": "Spawning and eating", "acceptance": ["spawns on empty cell"]},
        {"title": "Collision", "description": "Wall and self collision", "acceptance": ["game over on hit"]},
    ])
    k.expand("renderer", [
        {"title": "Camera", "description": "Viewport", "acceptance": ["follows the snake"]},
        {"title": "UI", "description": "Score and status bar", "acceptance": ["score updates"]},
        {"title": "Lighting", "description": "ASCII shading", "acceptance": ["depth shading"]},
        {"title": "Particle System", "description": "Death explosion", "acceptance": ["particles on game over"]},
    ])
    k.start("window")
    k.add_evidence("window", "hard", "unittest", "test_window passes (14 assertions)")
    k.verify_pass("window")
    k.start("input")
    k.verify_fail("input", "movement handler misses edge cases (diagonal input races)")
    k.add_evidence("input", "soft", "peer review", "logic otherwise sound; fix races then re-verify")
    k.retry("input")
    k.verify_pass("input")
    k.start("camera")
    k.add_evidence("camera", "hard", "unittest", "test_camera passes (9 assertions)")
    k.verify_pass("camera")
    k.start("ui")


# --------------------------------------------------------------------------- commands
def cmd_init(args) -> int:
    Store(args.dir).init()
    print(f"initialized project at {args.dir} ({EVENT_FILE})")
    return 0


def cmd_create(args, k: Kernel) -> int:
    ev = k.create_task(args.title, args.desc, args.acceptance, args.file, id=args.id,
                       priority=args.priority)
    print(ev["id"])
    return 0


def cmd_update(args, k: Kernel) -> int:
    changes = {}
    if args.title is not None: changes["title"] = args.title
    if args.desc is not None: changes["description"] = args.desc
    if args.acceptance is not None: changes["acceptance"] = args.acceptance
    if args.file is not None: changes["files"] = args.file
    if args.priority is not None: changes["priority"] = args.priority
    k.update_task(args.task, **changes)
    print(f"updated {args.task}")
    return 0


def cmd_dep(args, k: Kernel) -> int:
    if args.remove:
        k.remove_dependency(args.task, args.depends_on)
    else:
        k.add_dependency(args.task, args.depends_on)
    print(f"{'removed' if args.remove else 'added'} dependency: {args.task} -> {args.depends_on}")
    return 0


def cmd_expand(args, k: Kernel) -> int:
    children = [_parse_child(s) for s in args.child]
    ev = k.expand(args.task, children)
    print(f"expanded {args.task} into: {', '.join(c['id'] for c in ev['children'])}")
    return 0


def cmd_start(args, k: Kernel) -> int:
    k.start(args.task)
    print(f"{args.task} -> in_progress")
    return 0


def cmd_verify_pass(args, k: Kernel) -> int:
    k.verify_pass(args.task, force=args.force)
    print(f"{args.task} -> done")
    return 0


def cmd_verify_fail(args, k: Kernel) -> int:
    k.verify_fail(args.task, args.reason)
    print(f"{args.task} -> needs_revision")
    return 0


def cmd_retry(args, k: Kernel) -> int:
    k.retry(args.task)
    print(f"{args.task} -> in_progress")
    return 0


def cmd_reopen(args, k: Kernel) -> int:
    k.reopen(args.task)
    print(f"{args.task} -> in_progress")
    return 0


def cmd_evidence(args, k: Kernel) -> int:
    k.add_evidence(args.task, args.kind, args.source, args.detail)
    print(f"{args.task}: evidence [{args.kind}] {args.source}")
    return 0


def cmd_note(args, k: Kernel) -> int:
    k.add_note(args.task, args.text)
    print(f"{args.task}: note added")
    return 0


def cmd_delete(args, k: Kernel) -> int:
    k.delete(args.task)
    print(f"deleted {args.task}")
    return 0


def cmd_show(args, k: Kernel) -> int:
    print(k.context(args.task, "json" if args.json else "markdown"))
    return 0


def cmd_inspect(args, k: Kernel) -> int:
    info = k.inspect(args.task)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    g = k.graph
    print(f"{info['id']} — {info['title']}")
    print("-" * max(len(info["id"]) + len(info["title"]) + 3, 24))
    print(f"Status:     {STATUS_ICON[info['status']]} {info['status']}"
          + (" (container: completes when children do)" if info["container"] else ""))
    print(f"Priority:   {info['priority']}")
    print(f"Completion: {info['completion']}% ({info['completion_text']})")
    if info["children"]:
        print("Children:")
        for c in info["children"]:
            print(f"  {c['icon']} {c['id']} — {c['title']} ({c['status']})")
    if info["depends_on"]:
        print(f"Depends on: {', '.join(info['depends_on'])}")
    if info["blocks"]:
        print(f"Blocks:     {', '.join(info['blocks'])}")
    if info["acceptance"]:
        print("Acceptance:")
        for a in info["acceptance"]:
            print(f"  - {a}")
    if info["files"] or info["produces"]:
        print(f"Files:      {', '.join(info['files']) or '(none)'}")
        print(f"Produces:   {', '.join(info['produces']) or '(none)'}")
    if info["evidence"]:
        print("Evidence:")
        for e in info["evidence"]:
            print(f"  [{e['kind']}] {e['source']} — {e['detail']}")
    if info["notes"]:
        print("Notes:")
        for n in info["notes"]:
            print(f"  - {n}")
    print("History:")
    for h in info["history"]:
        extra = f" ({h['summary']})" if h["summary"] else ""
        print(f"  #{h['seq']:>4} {h['op']}{extra}")
    return 0


def cmd_query(args, k: Kernel) -> int:
    result = k.query(args.expr)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if isinstance(result, list) and result and isinstance(result[0], str):
        for item in result:
            print(item)
    elif isinstance(result, list) and not result:
        print("(no matches)")
    else:
        for item in result:
            print(item)
    return 0


def cmd_export(args, k: Kernel) -> int:
    payload = k.to_export_json()
    if args.file:
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(payload + "\n")
        print(f"exported {len(k.export_events())} events to {args.file}")
    else:
        print(payload)
    return 0


def cmd_import(args, k: Kernel) -> int:
    with open(args.file, encoding="utf-8") as f:
        events = json.load(f)
    result = k.import_events(events)
    print(f"imported {result['imported']} events -> project now has {result['tasks']} tasks")
    return 0


def cmd_graph(args, k: Kernel) -> int:
    g = k.graph
    if not g.tasks:
        print("(empty graph)")
        return 0
    if args.task is not None:
        if args.task not in g.tasks:
            print(f"no such task: {args.task}", file=sys.stderr)
            return 1
        _print_tree(g, args.task, "", True, set())
        return 0
    roots = g.roots()
    if not roots:
        roots = sorted(g.tasks.values(), key=lambda t: t.created_seq)[:1]
    for i, r in enumerate(roots):
        _print_tree(g, r.id, "", i == len(roots) - 1, set())
    return 0


def cmd_ready(args, k: Kernel) -> int:
    for tid in k.ready():
        print(tid)
    return 0


def cmd_next(args, k: Kernel) -> int:
    tid = k.next()
    if tid is None:
        print("nothing ready")
        return 1
    print(tid)
    return 0


def cmd_blockers(args, k: Kernel) -> int:
    result = k.blockers(args.task, chain=args.chain)
    if not result:
        print("none")
        return 0
    if args.chain:
        for path in result:
            print(" -> ".join(path))
    else:
        for b in result:
            print(b)
    return 0


def cmd_progress(args, k: Kernel) -> int:
    p = k.progress()
    print(f"done {p['done']}/{p['total']} ({p['percent']}%)")
    print(f"todo {p['todo']} | in_progress {p['in_progress']} | "
          f"needs_revision {p['needs_revision']} | done {p['done']}")
    return 0


def cmd_validate(args, k: Kernel) -> int:
    problems = k.graph.problems()
    if not problems:
        print(f"graph OK: {len(k.graph.tasks)} tasks, {k.graph.seq} events")
        return 0
    for p in problems:
        print(p, file=sys.stderr)
    return 1


def cmd_log(args, k: Kernel) -> int:
    events = k.store.read_events()
    tail = events[-args.tail:] if args.tail else events
    for ev in tail:
        op = ev["op"]
        target = ev.get("id") or ev.get("task") or ev.get("depends_on", "")
        print(f"#{ev['seq']:>4}  {op:<22} {target:<28} {ev.get('ts', '')}")
    return 0


def cmd_undo(args, k: Kernel) -> int:
    removed = k.undo(args.count)
    for ev in removed:
        op = ev["op"]
        target = ev.get("id") or ev.get("task") or ev.get("depends_on", "")
        print(f"undid #{ev['seq']} {op} ({target})")
    if k.graph.tasks:
        print(f"project now: {len(k.graph.tasks)} tasks")
    else:
        print("project now: empty")
    return 0


def cmd_replay(args, k: Kernel) -> int:
    stats = k.replay()
    print(f"replayed {stats['events']} events -> {stats['tasks']} tasks, "
          f"{stats['done']} done")
    return 0


def cmd_demo(args, k: Kernel) -> int:
    if k.graph.tasks:
        print("project is not empty; demo needs a fresh project", file=sys.stderr)
        return 1
    _seed_demo(k)
    print("seeded demo project (Snake Game)")
    return 0


def cmd_propose(args, k: Kernel) -> int:
    from .sdk import ForgeClient, ProposalError
    client = ForgeClient(args.dir)
    try:
        with open(args.file, encoding="utf-8") as f:
            proposal = json.load(f)
    except FileNotFoundError:
        print(f"error: proposal file not found: {args.file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: proposal file is not valid JSON: {e}", file=sys.stderr)
        return 1
    try:
        # envelope check + kernel verdict: whole or nothing
        result = client.propose(proposal)
    except ProposalError as e:
        print(f"proposal rejected (protocol): {e}", file=sys.stderr)
        return 1
    print(f"committed {result['committed']} events from {result['proposal_id']} "
          f"(confidence {result['confidence']}) -> project now has "
          f"{result['tasks']} tasks")
    return 0


def cmd_context(args, k: Kernel) -> int:
    from .sdk import ForgeClient
    client = ForgeClient(args.dir)
    print(client.context(args.task))
    return 0


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forge", description="Forge — a deterministic project kernel. "
                                "execution engine for autonomous software development. "
                                "Version " + __version__)
    p.add_argument("-d", "--dir", default=".", help="project directory (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a new project (events.log) in DIR")

    c = sub.add_parser("create", help="create a task")
    c.add_argument("title")
    c.add_argument("--id", help="explicit id (default: slug of title)")
    c.add_argument("--desc", default="")
    c.add_argument("-a", "--acceptance", action="append", default=[], help="repeatable")
    c.add_argument("-f", "--file", action="append", default=[], help="repeatable")
    c.add_argument("--priority", choices=["low", "medium", "high"], default="medium")

    c = sub.add_parser("update", help="update task fields")
    c.add_argument("task")
    c.add_argument("--title")
    c.add_argument("--desc")
    c.add_argument("-a", "--acceptance", action="append", help="replaces the list")
    c.add_argument("-f", "--file", action="append", help="replaces the list")
    c.add_argument("--priority", choices=["low", "medium", "high"])

    c = sub.add_parser("dep", help="add a dependency: TASK cannot finish until DEPENDS_ON is done")
    c.add_argument("task")
    c.add_argument("depends_on")
    c.add_argument("--remove", action="store_true", help="remove instead of add")

    c = sub.add_parser("expand", help="turn TASK into a container; it completes when children do")
    c.add_argument("task")
    c.add_argument("-c", "--child", action="append", required=True,
                   help="'Title' | 'Title::desc' | 'Title::desc::acc1;acc2' — repeatable")

    c = sub.add_parser("start", help="todo -> in_progress")
    c.add_argument("task")
    c = sub.add_parser("verify-pass", help="in_progress/needs_revision -> done (requires deps done)")
    c.add_argument("task")
    c.add_argument("--force", action="store_true", help="pass even with incomplete dependencies")
    c = sub.add_parser("verify-fail", help="in_progress -> needs_revision")
    c.add_argument("task")
    c.add_argument("--reason", required=True)
    c = sub.add_parser("retry", help="needs_revision -> in_progress")
    c.add_argument("task")
    c = sub.add_parser("reopen", help="done -> in_progress")
    c.add_argument("task")

    c = sub.add_parser("evidence", help="attach evidence to a task")
    c.add_argument("task")
    c.add_argument("--kind", required=True, choices=["hard", "soft"],
                   help="hard = tests/compile/benchmark, soft = LLM/human review")
    c.add_argument("--source", required=True)
    c.add_argument("--detail", default="")

    c = sub.add_parser("note", help="append a note to a task")
    c.add_argument("task")
    c.add_argument("text")

    c = sub.add_parser("delete", help="delete a task (no dependents, no children)")
    c.add_argument("task")

    c = sub.add_parser("show", help="task context package (what an LLM client sees)")
    c.add_argument("task")
    c.add_argument("--json", action="store_true")

    c = sub.add_parser("context", help="Context Contract package for TASK (YAML) — "
                       "the standard ~500-token handoff to any coding agent")
    c.add_argument("task")

    c = sub.add_parser("inspect", help="everything about one task: status, children, evidence, history")
    c.add_argument("task")
    c.add_argument("--json", action="store_true")

    c = sub.add_parser("query", help="query the graph: 'status == needs_revision and priority == high'")
    c.add_argument("expr", help="e.g. 'status == done', '\"snake\" in title', 'blockers(renderer)'")
    c.add_argument("--json", action="store_true")

    c = sub.add_parser("export", help="write the event log as portable JSON")
    c.add_argument("file", nargs="?", help="output file (default: stdout)")

    c = sub.add_parser("import", help="merge an exported event log into this project")
    c.add_argument("file")

    c = sub.add_parser("graph", help="render the task tree")
    c.add_argument("task", nargs="?", help="render subtree rooted at TASK")

    sub.add_parser("ready", help="list tasks ready to work on")
    sub.add_parser("next", help="print the single next task (priority, then creation order)")
    c = sub.add_parser("blockers", help="incomplete dependencies of TASK")
    c.add_argument("task")
    c.add_argument("--chain", action="store_true", help="show full root-cause paths")

    sub.add_parser("progress", help="project progress summary")
    sub.add_parser("validate", help="check graph consistency")
    c = sub.add_parser("log", help="show the event log")
    c.add_argument("--tail", type=int, help="only last N events")
    c = sub.add_parser("undo", help="truncate the last N events from the log")
    c.add_argument("count", nargs="?", type=int, default=1)
    sub.add_parser("replay", help="reconstruct the graph from the log")
    sub.add_parser("demo", help="seed a demo project (Snake Game)")

    c = sub.add_parser("propose", help="commit a proposal file: protocol check, then kernel commits or rejects whole")
    c.add_argument("file")

    # Ecosystem plugins contribute their own subparsers via the
    # forge.commands entry-point group (see forge/plugins.py). A known
    # command whose package is not installed gets a stub subparser with an
    # install hint instead of argparse's bare "invalid choice".
    from .plugins import discover, stub_for_ecosystem
    plugin_commands = discover(sub)
    plugin_commands.update(stub_for_ecosystem(sub, plugin_commands))
    p._forge_plugin_commands = plugin_commands

    return p


COMMANDS = {
    "init": cmd_init,
    "create": cmd_create,
    "update": cmd_update,
    "dep": cmd_dep,
    "expand": cmd_expand,
    "start": cmd_start,
    "verify-pass": cmd_verify_pass,
    "verify-fail": cmd_verify_fail,
    "retry": cmd_retry,
    "reopen": cmd_reopen,
    "evidence": cmd_evidence,
    "note": cmd_note,
    "delete": cmd_delete,
    "show": cmd_show,
    "context": cmd_context,
    "inspect": cmd_inspect,
    "query": cmd_query,
    "export": cmd_export,
    "import": cmd_import,
    "graph": cmd_graph,
    "ready": cmd_ready,
    "next": cmd_next,
    "blockers": cmd_blockers,
    "progress": cmd_progress,
    "validate": cmd_validate,
    "log": cmd_log,
    "undo": cmd_undo,
    "replay": cmd_replay,
    "demo": cmd_demo,
    "propose": cmd_propose,
}


def main(argv: list[str] | None = None) -> int:
    _setup_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = dict(COMMANDS)
    commands.update(getattr(parser, "_forge_plugin_commands", {}))
    try:
        if args.cmd == "init":
            return cmd_init(args)
        # Phase 1: a typo'd -d must never silently fork a new project —
        # only `init` creates one. Everything else requires an existing
        # project (kernel auto-init stays for SDK/MCP ergonomics).
        if not Store(args.dir).exists():
            print(f"error: {args.dir} is not a project (run: forge init {args.dir})",
                  file=sys.stderr)
            return 1
        k = Kernel(args.dir)
        return commands[args.cmd](args, k)
    except GraphError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"error: {args.dir} is not a project (run: forge init {args.dir})", file=sys.stderr)
        return 1
    except OSError as e:
        # e.g. -d pointing at a file (FileExistsError from store.init) or a
        # project whose events.log is a directory (PermissionError on open).
        # Clean error, never a traceback.
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
