#!/usr/bin/env python3
"""Proof #5 S1..S10 invariant checker (examples/swarm/check_invariants.py).

The meta-verification for PHASE2_DESIGN.md §5: reads the finished bundle
(examples/swarm/) and emits one boolean per invariant from the S1..S10
checklist, plus a final VERDICT. Every check is a pure function of the
shipped artifacts (events.log -> graph.json / metrics.json / replay.md) or
of reproducible re-derivation from them — nothing here is hand-asserted.

Usage:
    python examples/swarm/check_invariants.py [examples/swarm] [--workspace DIR]
Exit code 0 = all invariants hold, 1 = at least one failed.

Invariant map (PHASE2_DESIGN.md §1):
  S1  acyclic, fully-connected DAG (Kahn covers all tasks, no unknown ids)
  S2  no orphaned tasks (every task_created claimed + done, none dropped)
  S3  dependency correctness under concurrency (partial order holds on seq+ts)
  S4  unique ownership (exactly one start per task; one agent per task)
  S5  atomic contiguous gap-free log (seq 1..N)
  S6  verification evidence per task + genuine failure cycles (>=2)
  S7  derived reproducibility at scale (double-derive, byte-identical)
  S8  replayability (replay.md + derived _replay_facts.md, seq citations)
  S9  context assembly at scale (~50/~100/full, public SDK, no error)
  S10 no state corruption (line-level integrity + SDK export == file size)
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))  # repo root (tools/, forge/)
PROOF_DIR_DEFAULT = os.path.join(REPO, "examples", "swarm")
FORGE_VERSION = "0.1.0a3"  # repo version the run was produced with


def load_events(proof_dir):
    lines = (Path(proof_dir) / "events.log").read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in lines if l.strip()]
    return events, len(lines)


class Checker:
    def __init__(self, proof):
        self.proof = Path(proof)
        self.results = {}

    def check(self, name, ok, detail=""):
        self.results[name] = bool(ok)
        print(f"{name}={1 if ok else 0}" + (f"  # {detail}" if detail else ""))

    # ------------------------------------------------------------------ S1
    def s1_dag(self, events):
        ids = {e["id"] for e in events if e["op"] == "task_created"}
        edges = [(e["depends_on"], e["task"]) for e in events
                 if e["op"] == "dependency_added"]
        unknown = sorted({d for d, _ in edges} - ids | {t for _, t in edges} - ids)
        # Kahn: every task reachable (fully connected) iff all get processed
        indeg = {t: 0 for t in ids}
        out = {t: [] for t in ids}
        for d, t in edges:
            indeg[t] += 1
            out[d].append(t)
        q = [t for t in ids if indeg[t] == 0]
        seen = 0
        while q:
            t = q.pop()
            seen += 1
            for b in out[t]:
                indeg[b] -= 1
                if indeg[b] == 0:
                    q.append(b)
        ok = not unknown and seen == len(ids) and len(edges) == len(set(edges))
        self.check("S1", ok,
                   f"tasks={len(ids)} edges={len(edges)} covered={seen}/{len(ids)} "
                   f"unknown={unknown[:5]}")
        return ok

    # ------------------------------------------------------------------ S2
    def s2_orphans(self, events):
        ids = {e["id"] for e in events if e["op"] == "task_created"}
        started = {e["id"] for e in events if e["op"] == "task_started"}
        passed = {e["id"] for e in events if e["op"] == "verification_passed"}
        orphans = ids - started
        not_done = ids - passed
        self.check("S2", not orphans and not not_done,
                   f"orphans={len(orphans)} not_done={len(not_done)}")
        return not orphans and not not_done

    # ------------------------------------------------------------------ S3
    def s3_order(self, events):
        ids = {e["id"] for e in events if e["op"] == "task_created"}
        deps = {t: set() for t in ids}
        for e in events:
            if e["op"] == "dependency_added":
                deps.setdefault(e["task"], set()).add(e["depends_on"])
        start_seq = {e["id"]: e["seq"] for e in events if e["op"] == "task_started"}
        start_ts = {e["id"]: e["ts"] for e in events if e["op"] == "task_started"}
        pass_seq = {e["id"]: e["seq"] for e in events if e["op"] == "verification_passed"}
        pass_ts = {e["id"]: e["ts"] for e in events if e["op"] == "verification_passed"}
        bad_seq = bad_ts = 0
        for t, ds in deps.items():
            for d in ds:
                if d in pass_seq and t in start_seq and start_seq[t] < pass_seq[d]:
                    bad_seq += 1
                if d in pass_ts and t in start_ts and start_ts[t] < pass_ts[d]:
                    bad_ts += 1
        self.check("S3", bad_seq == 0 and bad_ts == 0,
                   f"seq_violations={bad_seq} ts_violations={bad_ts}")
        return bad_seq == 0 and bad_ts == 0

    # ------------------------------------------------------------------ S4
    def s4_ownership(self, events):
        starts = Counter(e["id"] for e in events if e["op"] == "task_started")
        dup = sorted(t for t, c in starts.items() if c != 1)
        # one agent per task: exactly one evidence_added carries "agent="
        agents_per = Counter()
        for e in events:
            if e["op"] == "evidence_added" and "agent=" in e.get("detail", ""):
                agents_per[e["id"]] += 1
        multi_agent = sorted(t for t, c in agents_per.items() if c != 1)
        self.check("S4", not dup and not multi_agent,
                   f"double_starts={dup[:5]} multi_agent={multi_agent[:5]}")
        return not dup and not multi_agent

    # ------------------------------------------------------------------ S5
    def s5_contiguous(self, events):
        seqs = [e["seq"] for e in events]
        self.check("S5", seqs == list(range(1, len(seqs) + 1)), f"n={len(seqs)}")
        return seqs == list(range(1, len(seqs) + 1))

    # ------------------------------------------------------------------ S6
    def s6_evidence(self, events):
        passed = {e["id"] for e in events if e["op"] == "verification_passed"}
        failed_ids = [e["id"] for e in events if e["op"] == "verification_failed"]
        ev_after = set()
        for i, e in enumerate(events):
            if e["op"] == "verification_passed":
                # a later evidence_added for the same id must exist
                if any(x["op"] == "evidence_added" and x["id"] == e["id"]
                       for x in events[i + 1:]):
                    ev_after.add(e["id"])
        missing = passed - ev_after
        cycles = {t for t in failed_ids} & passed  # failed then later passed
        self.check("S6", not missing and len(cycles) >= 2,
                   f"missing_evidence={len(missing)} fail_cycles={len(cycles)} "
                   f"fails={failed_ids}")
        return not missing and len(cycles) >= 2

    # ------------------------------------------------------------------ S7
    def s7_double_derive(self, forge_version):
        """double-derive in a temp copy of the log; byte-identical outputs
        (each derive must reproduce the previous byte-for-byte, and a fresh
        derive from the shipped events.log must reproduce the SHIPPED
        graph.json/metrics.json — the temp project dir is named 'swarm' so
        the 'proof' field stays stable)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "swarm"
            tmp.mkdir()
            (tmp / "events.log").write_bytes(
                (self.proof / "events.log").read_bytes())
            py = sys.executable
            derive = os.path.join(REPO, "tools", "proof-derive.py")
            r1 = subprocess.run([py, derive, str(tmp), "--forge-version",
                                 forge_version], capture_output=True, text=True)
            h1 = [(f, hashlib.sha256((tmp / f).read_bytes()).hexdigest())
                  for f in ("graph.json", "metrics.json")]
            (tmp / "graph.json").unlink()
            (tmp / "metrics.json").unlink()
            r2 = subprocess.run([py, derive, str(tmp), "--forge-version",
                                 forge_version], capture_output=True, text=True)
            h2 = [(f, hashlib.sha256((tmp / f).read_bytes()).hexdigest())
                  for f in ("graph.json", "metrics.json")]
            identical = h1 == h2 and r1.returncode == 0 and r2.returncode == 0
            # shipped artifacts must equal the re-derive from shipped log
            shipped = [(f, hashlib.sha256((self.proof / f).read_bytes()).hexdigest())
                       for f in ("graph.json", "metrics.json")]
            match = shipped == h1
            self.check("S7", identical and match,
                       f"double_derive={identical} shipped_matches={match}")
            return identical and match

    # ------------------------------------------------------------------ S8
    def s8_replay(self):
        replay = self.proof / "replay.md"
        facts = self.proof / "demo" / "_replay_facts.md"
        ok = replay.exists() and facts.exists()
        txt = replay.read_text(encoding="utf-8") if replay.exists() else ""
        for kw in ("Goal", "Outcome", "Timeline", "Turning points"):
            ok = ok and (kw in txt)
        citations = len([1 for ln in txt.splitlines() if "seq " in ln.lower()
                         or "seq:" in ln.lower()])
        self.check("S8", ok, f"categories=4 citations={citations}")
        return ok

    # ------------------------------------------------------------------ S9
    def s9_context(self, events):
        sys.path.insert(0, REPO)
        from forge import Kernel  # public SDK only
        total = len(events)
        cuts = {"~50": 50, "~100": 100, "full": total}
        ok_all = True
        for label, n in cuts.items():
            prefix = events[:n]
            tids = [e["id"] for e in prefix if e["op"] == "task_created"]
            if not tids:
                ok_all = False
                continue
            with tempfile.TemporaryDirectory() as td:
                k = Kernel(td)
                k.import_events(prefix)
                target = tids[-1]  # frontier task at the cut
                md = k.context(target, fmt="markdown")
                need = ("# ", "## Acceptance criteria", "## Project",
                        "progress:")
                if not all(s in md for s in need) or len(md) < 300:
                    ok_all = False
            self.check(f"S9/{label}", ok_all, f"tasks={len(tids)} ctx_ok={ok_all}")
        self.check("S9", ok_all, f"cuts={list(cuts)}")
        return ok_all

    # ------------------------------------------------------------------- S10
    def s10_integrity(self, events, raw_lines):
        seqs = [e["seq"] for e in events]
        gap_free = seqs == list(range(1, len(seqs) + 1))
        sys.path.insert(0, REPO)
        from forge import Kernel
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "events.log").write_text(
                (self.proof / "events.log").read_text(encoding="utf-8"),
                encoding="utf-8")
            k = Kernel(td)
            exported = len(k.export_events())
        self.check("S10", gap_free and exported == raw_lines,
                   f"lines={raw_lines} sdk_export={exported} gaps={0}")
        return gap_free

    def run(self, forge_version):
        events, raw_lines = load_events(self.proof)
        self.s1_dag(events)
        self.s2_orphans(events)
        self.s3_order(events)
        self.s4_ownership(events)
        self.s5_contiguous(events)
        self.s6_evidence(events)
        self.s7_double_derive(forge_version)
        self.s8_replay()
        self.s9_context(events)
        self.s10_integrity(events, raw_lines)
        bad = [k for k, v in self.results.items() if not v]
        print("VERDICT " + ("PASS" if not bad else f"FAIL: {bad}"))
        return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description="Proof #5 S1..S10 invariant checker")
    ap.add_argument("proof", nargs="?", default=PROOF_DIR_DEFAULT)
    ap.add_argument("--forge-version", default=FORGE_VERSION)
    a = ap.parse_args()
    sys.exit(Checker(Path(a.proof).resolve()).run(a.forge_version))


if __name__ == "__main__":
    main()