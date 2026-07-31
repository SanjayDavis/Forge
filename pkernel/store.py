"""Event-log persistence for the Project Kernel.

The log is an append-only JSONL file. The graph is a projection: load =
read all events + fold. Undo = truncate + refold. Append is the only write
path, which keeps the log safe against partial crashes (a torn last line is
skipped on load).
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from .model import Graph, GraphError

EVENT_FILE = "events.log"


def _ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, directory: str) -> None:
        self.dir = os.path.abspath(directory)

    @property
    def path(self) -> str:
        return os.path.join(self.dir, EVENT_FILE)

    # ---------------------------------------------------------------- lifecycle
    def init(self) -> None:
        os.makedirs(self.dir, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    def exists(self) -> bool:
        return os.path.exists(self.path)

    # ---------------------------------------------------------------- I/O
    def read_events(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # torn line from a crash; skip it, log is append-only
        return events

    def append(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assign seq/ts, append lines, return the stamped events."""
        existing = self.read_events()
        seq = existing[-1]["seq"] + 1 if existing else 1
        out: list[dict[str, Any]] = []
        with open(self.path, "a", encoding="utf-8") as f:
            for ev in events:
                stamped = dict(ev)
                stamped["seq"] = seq
                stamped.setdefault("ts", _ts())
                f.write(json.dumps(stamped, ensure_ascii=False) + "\n")
                out.append(stamped)
                seq += 1
        return out

    def undo(self, n: int) -> list[dict[str, Any]]:
        """Truncate the last n events and return them."""
        if n < 1:
            raise GraphError("undo count must be >= 1")
        events = self.read_events()
        if not events:
            raise GraphError("nothing to undo")
        if n > len(events):
            raise GraphError(f"cannot undo {n}: only {len(events)} event(s) in the log")
        removed = events[-n:]
        kept = events[:-n]
        with open(self.path, "w", encoding="utf-8") as f:
            for ev in kept:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return removed


def load_project(directory: str) -> tuple[Store, Graph]:
    """Load (or lazily create) a project: read events, fold into a graph."""
    store = Store(directory)
    if not store.exists():
        store.init()
    graph = Graph.from_events(store.read_events())
    return store, graph
