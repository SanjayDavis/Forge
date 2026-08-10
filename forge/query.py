"""Query language for the graph.

A safe subset of Python expressions — parsed with `ast`, never eval()'d —
evaluated against each task. Attribute access, subscripts, lambdas and
arbitrary calls are rejected.

Filter form (lists matching task ids):
    status == needs_revision and priority == high
    priority > medium
    "snake" in title
    evidence_count >= 2 and not blocked
    id in children(renderer)
    container and status == in_progress

Call form (lists the result directly):
    blockers(renderer)     incomplete dependencies of renderer
    children(renderer)     ids of renderer's children
    deps(renderer)         same as children
    parents(renderer)      tasks waiting on renderer
    evidence(renderer)     evidence lines for renderer
    ready()                tasks ready to work on

Available per-task fields:
    id, title, status (effective), priority, blocked, container,
    evidence_count, files, notes, acceptance, depends_on, blocks, created_seq

Bare words (needs_revision, high, ...) evaluate to strings; priority
comparisons use low < medium < high. Unknown field names or enum values
are rejected with QueryError — a typo'd query never silently returns
(no matches).
"""

from __future__ import annotations

import ast

from .model import PRIORITY_WEIGHT, STATUS_DONE, VALID_STATUSES, Graph, GraphError
from .scheduler import blockers, ready_tasks

_ALLOWED_NODES = (
    ast.Expression, ast.Compare, ast.BoolOp, ast.UnaryOp,
    ast.Name, ast.Constant, ast.Call, ast.List, ast.Tuple,
    ast.Load, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn,
)

# F5: pathological nesting must fail as QueryError on every platform.
# The C parser's RecursionError depth is platform-dependent (Windows vs
# Linux differ), and with an empty graph the filter loop never evaluates
# — so a depth check here is the only deterministic guard.
_MAX_QUERY_DEPTH = 100


class QueryError(GraphError):
    pass


def _task_ctx(t, g: Graph) -> dict:
    eff = t.effective_status(g.tasks)
    return {
        "id": t.id, "title": t.title, "status": eff, "priority": t.priority,
        "blocked": eff != STATUS_DONE and any(
            g.tasks[d].effective_status(g.tasks) != STATUS_DONE for d in t.depends_on),
        "container": bool(t.composite and t.depends_on),
        "evidence_count": len(t.evidence),
        "files": list(t.files), "notes": list(t.notes), "acceptance": list(t.acceptance),
        "depends_on": list(t.depends_on),
        "blocks": sorted(x.id for x in g.tasks.values() if t.id in x.depends_on),
        "created_seq": t.created_seq,
    }


def _eval(node: ast.AST, ctx: dict):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return ctx[node.id]
        return node.id  # bare words like `needs_revision` are strings
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, ctx) for e in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval(node.operand, ctx)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not _eval(v, ctx):
                    return False
            return True
        for v in node.values:
            if _eval(v, ctx):
                return True
        return False
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, ctx)
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(left, str) and isinstance(right, str):
                ok = left.lower() in right.lower()
                if isinstance(op, ast.NotIn):
                    ok = not ok
                if not ok:
                    return False
                left = right
                continue
            left, right = _normalize(left, right)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.In):
                ok = left in right
            elif isinstance(op, ast.NotIn):
                ok = left not in right
            else:
                raise QueryError("unsupported comparison operator")
            if not ok:
                return False
            left = right  # chained comparisons
        return True
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name not in FUNCTIONS:
            raise QueryError(f"unknown function {name!r}")
        args = [_eval(a, {}) for a in node.args]
        return FUNCTIONS[name](*args)
    raise QueryError(f"unsupported expression element: {type(node).__name__}")


def _normalize(left, right):
    """Priority-aware comparison: 'high' > 'medium' numerically."""
    if isinstance(left, str) and isinstance(right, str):
        if left in PRIORITY_WEIGHT and right in PRIORITY_WEIGHT:
            return PRIORITY_WEIGHT[left], PRIORITY_WEIGHT[right]
    return left, right


def _check_tree(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise QueryError(f"unsupported expression element: {type(node).__name__}")


def _check_depth(tree: ast.AST) -> None:
    """Iterative max-depth check. Never recurses — recursion here would
    defeat the guard (pathological nesting must not overflow Python's
    stack either). Raises QueryError when the expression nests deeper
    than _MAX_QUERY_DEPTH."""
    max_depth = 0
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            max_depth = depth
            if max_depth > _MAX_QUERY_DEPTH:
                raise QueryError("query expression too deeply nested")
        for child in ast.iter_child_nodes(node):
            stack.append((child, depth + 1))


# Phase 1: a typo'd field or enum value must fail loudly, not silently
# return (no matches). Every bare word in a query is either a field name
# or an enum value — anything else is a typo.
_FIELDS = frozenset({
    "id", "title", "status", "priority", "blocked", "container",
    "evidence_count", "files", "notes", "acceptance", "depends_on",
    "blocks", "created_seq",
})
_STATUS_WORDS = frozenset(VALID_STATUSES)
_PRIORITY_WORDS = frozenset(PRIORITY_WEIGHT)
_ALL_WORDS = _FIELDS | _STATUS_WORDS | _PRIORITY_WORDS
_ENUM_FIELDS = {"status": _STATUS_WORDS, "priority": _PRIORITY_WORDS}


def _validate_names(tree: ast.AST) -> None:
    """Reject bare words that are neither a field nor an enum value.
    Call function names and their arguments are exempt: arguments are
    task ids, validated at runtime by the function itself."""
    stack: list[tuple[ast.AST, bool]] = [(tree, False)]
    while stack:
        node, is_arg = stack.pop()
        if isinstance(node, ast.Name):
            if is_arg:
                continue
            if node.id in _ALL_WORDS:
                continue
            raise QueryError(
                f"unknown field or value: {node.id!r} "
                f"(fields: {', '.join(sorted(_FIELDS))}; "
                f"values: {', '.join(sorted(_STATUS_WORDS | _PRIORITY_WORDS))})")
        if isinstance(node, ast.Call):
            stack.append((node.func, True))  # e.g. children( — not a field
            for a in node.args:
                stack.append((a, True))
            continue
        for child in ast.iter_child_nodes(node):
            stack.append((child, False))


def _validate_enums(tree: ast.AST) -> None:
    """Position-aware enum check: a status field compared against a bare
    word must use a status value; a priority field a priority value.
    `status == high` and `priority == done` are wrong-position typos."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for comp in node.comparators:
            for field_node, word_node in ((node.left, comp), (comp, node.left)):
                if (isinstance(field_node, ast.Name)
                        and field_node.id in _ENUM_FIELDS
                        and isinstance(word_node, ast.Name)
                        and word_node.id in _ALL_WORDS
                        and word_node.id not in _ENUM_FIELDS[field_node.id]):
                    field = field_node.id
                    raise QueryError(
                        f"{word_node.id!r} is not a valid {field} value "
                        f"(valid: {', '.join(sorted(_ENUM_FIELDS[field]))})")


FUNCTIONS: dict[str, callable] = {}


def run_query(g: Graph, expr: str):
    """Evaluate a query. Returns matching task ids (filter form) or the
    function result (call form)."""
    expr = expr.strip()
    if not expr:
        raise QueryError("empty query")
    _register_functions(g)
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, RecursionError, MemoryError) as e:
        raise QueryError(f"bad query: {e}") from e
    _check_tree(tree)
    _check_depth(tree)
    _validate_names(tree)
    _validate_enums(tree)
    body = tree.body

    # call form: a top-level function call (blockers(x), evidence(x), ready()...)
    if isinstance(body, ast.Call):
        name = body.func.id if isinstance(body.func, ast.Name) else None
        if name not in FUNCTIONS:
            raise QueryError(f"unknown function {name!r}")
        try:
            args = [_eval(a, {}) for a in body.args]
        except RecursionError as e:
            raise QueryError("query expression too deeply nested") from e
        return FUNCTIONS[name](*args)

    # filter form: evaluate the expression against every task
    out = []
    for tid, t in g.tasks.items():
        try:
            if _eval(body, _task_ctx(t, g)):
                out.append(tid)
        except QueryError:
            raise
        except Exception as e:
            raise QueryError(f"query error on task {tid!r}: {e}") from e
    out.sort(key=lambda tid: g.tasks[tid].created_seq)
    return out


def _register_functions(g: Graph) -> None:
    def _require(task: str) -> None:
        if task not in g.tasks:
            raise QueryError(f"no such task: {task}")

    def f_blockers(task: str):
        _require(task)
        return blockers(g, task)

    def f_children(task: str):
        _require(task)
        return list(g.tasks[task].depends_on)

    def f_parents(task: str):
        _require(task)
        return sorted(x.id for x in g.tasks.values() if task in x.depends_on)

    def f_evidence(task: str):
        _require(task)
        t = g.tasks[task]
        return [f"[{e.kind}] {e.source} — {e.detail} ({e.ts})" for e in t.evidence]

    def f_ready():
        return [t.id for t in ready_tasks(g)]

    FUNCTIONS.update({
        "blockers": f_blockers,
        "children": f_children,
        "deps": f_children,
        "parents": f_parents,
        "evidence": f_evidence,
        "ready": f_ready,
    })


_register_functions.__annotations__ = {}
