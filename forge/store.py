"""Event-log persistence for the Forge kernel.

The log is an append-only JSONL file. The graph is a projection: load =
read all events + fold. Undo = truncate + refold. Append is the only write
path, which keeps the log safe against partial crashes (a torn last line is
skipped on load; corruption anywhere else raises).

Concurrency: every write (append/undo) takes an OS file lock, so any number
of agent processes can emit events simultaneously. seq assignment happens
under the lock, so sequence numbers are unique across processes. All I/O
goes through the lock handle: on Windows, byte-range locks deny access to
the locked region from *other* handles, even readers.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from typing import Any

from .model import SCHEMA_VERSION, Graph, GraphError

EVENT_FILE = "events.log"
LOCK_FILE = "events.lock"

try:  # Windows
    import msvcrt

    def _lock(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        f.seek(0, 2)

    def _unlock(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        f.seek(0, 2)

except ImportError:  # POSIX
    import fcntl

    def _lock(f) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock(f) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class _FileLock:
    """Cross-process write lock. Locks a dedicated lock file (always at
    least one byte, so it is always lockable — an empty file has no byte
    range to lock on Windows). Exposes the locked handle; callers must do
    all event-log I/O through it (Windows byte-range locks deny access to
    the locked region from *other* handles, even readers)."""

    def __init__(self, path: str) -> None:
        self.path = path  # the lock file (separate from the event log)
        self.f = None
        self._locked = False

    def __enter__(self):
        self.f = open(self.path, "a+b")
        if os.fstat(self.f.fileno()).st_size == 0:
            self.f.write(b"\0")
            self.f.flush()
        _lock(self.f)
        self._locked = True
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._locked:
                _unlock(self.f)
        finally:
            self.f.close()


def _ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _recover_tail(f) -> int:
    """Return the seq of the last valid event, truncating any torn tail
    (partial line(s) after the last valid event) so the next append can
    never merge into garbage. Must be called under the write lock.

    A torn line is a partial write from a crash — it never made it into
    the log, so discarding it is safe (SPEC §12.5). Garbage *followed by
    valid events* is corruption and is not touched here; the read path
    raises on it. The tail window covers the last 64 KiB; if it contains
    no valid line (line longer than the window, or an all-garbage tail)
    the whole file is scanned before giving up."""
    f.seek(0, 2)
    size = f.tell()
    if size == 0:
        return 0
    start = max(0, size - 65536)
    f.seek(start)
    chunk = f.read().decode("utf-8", "replace")

    def scan(text: str, base: int):
        last_seq, valid_end = 0, None
        pos = 0
        for ln in text.split("\n"):
            pos += len(ln) + 1
            if not ln.strip():
                continue
            try:
                seq = int(json.loads(ln)["seq"])
            except (KeyError, ValueError, json.JSONDecodeError):
                continue  # torn line; keep scanning back
            last_seq = seq
            valid_end = base + pos
        return last_seq, valid_end

    last_seq, valid_end = scan(chunk, start)
    if valid_end is None and size > 65536:
        f.seek(0)
        last_seq, valid_end = scan(f.read().decode("utf-8", "replace"), 0)
    if valid_end is not None and valid_end < size:
        f.truncate(valid_end)  # discard the torn tail, keep the log valid
        f.flush()
    return last_seq


def _ensure_trailing_newline(f) -> None:
    """A crash can leave the last line without a newline; appending to it
    would merge two events into one line. Under the write lock, repair the
    boundary before writing."""
    f.seek(0, 2)
    if f.tell() > 0:
        f.seek(-1, 2)
        if f.read(1) != b"\n":
            f.write(b"\n")


class Store:
    # Serializes writers within one process; the OS file lock covers
    # cross-process writers. (Windows byte-range locks are per-handle and
    # can fail fast on same-process contention, so both layers are needed.)
    _thread_lock = threading.Lock()

    def __init__(self, directory: str) -> None:
        self.dir = os.path.abspath(directory)

    @property
    def path(self) -> str:
        return os.path.join(self.dir, EVENT_FILE)

    # ---------------------------------------------------------------- lifecycle
    def init(self) -> None:
        os.makedirs(self.dir, exist_ok=True)
        for fname in (EVENT_FILE, LOCK_FILE):
            if not os.path.exists(os.path.join(self.dir, fname)):
                with open(os.path.join(self.dir, fname), "w", encoding="utf-8") as f:
                    f.write("")

    def exists(self) -> bool:
        return os.path.exists(self.path)

    # ---------------------------------------------------------------- I/O
    def read_events(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        for i, line in enumerate(lines):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    continue  # torn tail from a crash; the log is append-only
                raise GraphError(f"corrupt event log at line {i + 1} of {self.path}")
        return events

    @property
    def lock_path(self) -> str:
        return os.path.join(self.dir, LOCK_FILE)

    def append(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assign seq/ts/schema-version, append lines, return stamped events."""
        out: list[dict[str, Any]] = []
        with self._thread_lock:
            with _FileLock(self.lock_path):
                with open(self.path, "a+b") as f:
                    _ensure_trailing_newline(f)
                    seq = _recover_tail(f) + 1
                    for ev in events:
                        stamped = dict(ev)
                        stamped["seq"] = seq
                        stamped.setdefault("ts", _ts())
                        stamped["v"] = SCHEMA_VERSION
                        f.write(json.dumps(stamped, ensure_ascii=False).encode("utf-8") + b"\n")
                        out.append(stamped)
                        seq += 1
                    f.flush()
        return out

    def undo(self, n: int) -> list[dict[str, Any]]:
        """Truncate the last n events and return them."""
        if n < 1:
            raise GraphError("undo count must be >= 1")
        with self._thread_lock:
            with _FileLock(self.lock_path):
                with open(self.path, "a+b") as f:
                    _ensure_trailing_newline(f)
                    events = self._read_all(f)
                    if not events:
                        raise GraphError("nothing to undo")
                    if n > len(events):
                        raise GraphError(f"cannot undo {n}: only {len(events)} event(s) in the log")
                    removed = events[-n:]
                    kept = events[:-n]
                    f.seek(0)
                    f.truncate()
                    for ev in kept:
                        f.write(json.dumps(ev, ensure_ascii=False).encode("utf-8") + b"\n")
                    f.flush()
        return removed

    @staticmethod
    def _read_all(f) -> list[dict[str, Any]]:
        f.seek(0)
        events: list[dict[str, Any]] = []
        lines = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    continue
                raise GraphError(f"corrupt event log at line {i + 1}")
        return events


def load_project(directory: str) -> tuple[Store, Graph]:
    """Load (or lazily create) a project: read events, fold into a graph."""
    store = Store(directory)
    if not store.exists():
        store.init()
    graph = Graph.from_events(store.read_events())
    return store, graph
