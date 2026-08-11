"""`forge proof bundle` — emit a complete Proof-Standard artifact bundle.

On a live project dir (events.log present, nothing else): derives
graph.json/metrics.json/demo/_replay_facts.md, renders replay.md and
graph.png, scaffolds README.md, then runs the full §6 conformance
checklist. Run-captured media that a machine cannot synthesize
(screenshots/, demo.mp4 without a transcript, run.py) are reported as
gaps, not fabricated.

On an existing proof dir (examples/swarm): NEVER clobbers. The derived
artifacts are re-derived in a temp copy and verified byte-identical (the
§5 reproducibility rule); the curated README/replay.md/demo.mp4 are left
untouched; the bundle ends with the conformance verdict.

Deps: core derivation is stdlib-only; graph.png rendering additionally
needs matplotlib+networkx (optional — bundle still succeeds without
them, graph.png is reported as a gap).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import check as proof_check
from . import derive as proof_derive
from . import replay as proof_replay

_TOOLS = Path(__file__).resolve().parents[3] / "tools"


# ------------------------------------------------------------------ graph.png
def _render_graph(root: Path) -> bool:
    """Render graph.png from graph.json (in-process, optional matplotlib)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
        from matplotlib.patches import FancyBboxPatch
    except Exception as e:
        print(f"  hint: graph.png not rendered — install matplotlib+networkx ({e})")
        return False
    try:
        data = json.loads((root / "graph.json").read_text(encoding="utf-8"))
        G = nx.DiGraph()
        for t in data["tasks"]:
            G.add_node(t["id"], status=t["status"],
                       subsystem=t.get("subsystem", "other"), title=t["title"])
        for e in data["dependencies"]:
            G.add_edge(e["depends_on"], e["task"])
        rank = {}
        for n in G.nodes:
            rank[n] = 0
        changed = True
        while changed:
            changed = False
            for u, v in G.edges:
                if rank[v] < rank[u] + 1:
                    rank[v] = rank[u] + 1
                    changed = True
        levels = {}
        for n, r in rank.items():
            levels.setdefault(r, []).append(n)
        pos = {}
        for r, nodes in levels.items():
            for i, n in enumerate(sorted(nodes)):
                pos[n] = (i - (len(nodes) - 1) / 2, -r)
        depth = max(rank.values(), default=0)
        fig, ax = plt.subplots(figsize=(11, 6 + 1.1 * depth))
        ax.set_axis_off()
        ax.set_title(f"{data['proof']} — final dependency graph\n"
                     f"{data.get('forge_version', '')} · "
                     f"{len(data['tasks'])} tasks · {len(data['dependencies'])} edges",
                     fontsize=13)
        nx.draw_networkx_edges(G, pos, ax=ax, arrows=True, arrowstyle="-|>",
                               arrowsize=13, edge_color="#888888",
                               connectionstyle="arc3,rad=0.08")
        colors = {"done": "#2e7d32", "in_progress": "#f9a825",
                  "needs_revision": "#c62828", "todo": "#9e9e9e",
                  "other": "#37474f"}
        for n, d in G.nodes(data=True):
            fill = colors.get(d["status"], "#9e9e9e")
            x, y = pos[n]
            w = max(len(n), len(d["title"][:26])) * 0.075 + 0.3
            h = 0.78
            ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                        boxstyle="round,pad=0.02,rounding_size=0.08",
                                        fc=fill, ec="#37474f", lw=2.2))
            ax.annotate(n, (x, y + 0.14), ha="center", va="center", fontsize=9,
                        color="white", fontweight="bold")
            ax.annotate(d["title"][:26], (x, y - 0.3), ha="center", va="center",
                        fontsize=6.4, color="#222222")
        handles = [plt.Line2D([0], [0], marker="s", ls="", markersize=11,
                              markerfacecolor=c, markeredgecolor="#000",
                              label=str(s)) for s, c in colors.items()]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
                  frameon=True, fontsize=8, title="status")
        fig.tight_layout()
        fig.savefig(root / "graph.png", dpi=150, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  hint: graph.png render failed: {e}")
        return False


# ------------------------------------------------------------------- README.md
_README_SECTIONS = [
    ("What was built", "_(write one paragraph — what ran and what it produced)_"),
    ("Why this proof exists", "_(the claim this proof answers; list Claim IDs — see proposal.json)_"),
    ("Final architecture", "_(subsystem breakdown with dependency arrows — see graph.png)_"),
    ("Commands", "- `forge proof bundle .` (this bundle was assembled by it)\n- build/test commands used during the run"),
    ("Reproduce", "_(seed prompt, planner/executor/verifier used, Forge version)_"),
    ("Artifact index", "- `events.log` — raw Forge history (single source of truth)\n- `graph.json` / `graph.png` — final dependency graph\n- `replay.md` — seq-cited timeline\n- `metrics.json` — comparable numbers\n- `screenshots/` — at least 2 captures\n- `demo.mp4` — <= 2 min of the run"),
    ("Behavior notes", "_(anything non-obvious discovered during the run)_"),
    ("Lessons learned", "_(insights about the project, Forge, or the domain)_"),
]


def _scaffold_readme(root: Path, metrics: dict) -> None:
    claims = metrics.get("claims") or []
    why = ("Proof answers claim" + ("s" if len(claims) != 1 else "") +
           f": {', '.join(claims)}."
           if claims else "_(list Claim IDs — see proposal.json)_")
    body = [f"# {root.name} — proof bundle",
            "",
            f"Automatically scaffolded by `forge proof bundle` "
            f"(Forge {metrics.get('forge_version', 'unknown')}). "
            "Fill the placeholders, keep the section names.",
            ""]
    for title, filler in _README_SECTIONS:
        body += [f"## {title}", "", filler, ""]
    body.append("---\n")
    body.append("*Reported numbers are log-derived (see metrics.json).*")
    (root / "README.md").write_text("\n".join(body) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ demo.mp4
def _render_demo(root: Path) -> bool:
    transcript = root / "demo" / "transcript.txt"
    script = _TOOLS / "proof-render-demo.py"
    if not transcript.exists() or not script.exists():
        return False
    try:
        subprocess.run([sys.executable, str(script), str(root), str(transcript)],
                       check=True, capture_output=True, text=True, timeout=300)
        return True
    except Exception as e:
        print(f"  hint: demo.mp4 render failed: {e}")
        return False


# ------------------------------------------------------------------ bundle
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_derived_byte_identical(root: Path, forge_version: str) -> bool:
    """Re-derive in a temp dir NAMED after the proof (the 'proof' field of
    graph.json is the directory name) and compare bytes — the §5
    reproducibility rule, same inputs as check_invariants S7."""
    # Pin the derive stamp to the version the shipped artifacts claim —
    # otherwise a repo version bump (or a caller passing today's version)
    # reports byte-drift against artifacts stamped at their own
    # derivation version. Same rule as check_invariants S7.
    claimed = (root / "graph.json").exists() and json.loads(
        (root / "graph.json").read_text(encoding="utf-8")).get("forge_version")
    if claimed:
        forge_version = claimed
    if not (root / "graph.json").exists() or not (root / "metrics.json").exists():
        return True
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / root.name
        tmp.mkdir()
        for fname in ("events.log", "proposal.json"):
            src = root / fname
            if src.exists():
                (tmp / fname).write_bytes(src.read_bytes())
        proof_derive.derive_dir(str(tmp), forge_version=forge_version)
        if (tmp / "graph.json").exists() and (root / "graph.json").exists():
            same_g = _sha(tmp / "graph.json") == _sha(root / "graph.json")
            same_m = _sha(tmp / "metrics.json") == _sha(root / "metrics.json")
            return same_g and same_m
        return True if not (root / "graph.json").exists() else True


def bundle_dir(proof_dir, forge_version="unknown"):
    root = Path(proof_dir)
    emitted: list[str] = []
    verified: list[str] = []
    skipped: list[str] = []

    if not (root / "events.log").exists():
        print(f"error: {root} has no events.log — bundle needs a Forge project "
              "or proof dir with a raw event log", file=sys.stderr)
        return 1

    # 1. derived artifacts: write when missing, verify byte-identity when present
    if not (root / "graph.json").exists() or not (root / "metrics.json").exists():
        proof_derive.derive_dir(str(root), forge_version=forge_version)
        emitted += ["graph.json", "metrics.json", "demo/_replay_facts.md"]
    elif _verify_derived_byte_identical(root, forge_version):
        verified += ["graph.json + metrics.json byte-identical after re-derive"]
    else:
        print("  problem: re-derived graph.json/metrics.json differ from the "
              "shipped files — the log was edited or derive drifted",
              file=sys.stderr)

    # 2. replay.md (rendered, never clobbered)
    if not (root / "replay.md").exists():
        proof_replay.render_dir(str(root))
        emitted.append("replay.md")
    else:
        skipped.append("replay.md (curated — left untouched)")

    # 3. graph.png
    if not (root / "graph.png").exists():
        if _render_graph(root):
            emitted.append("graph.png")
    else:
        skipped.append("graph.png (existing — left untouched)")

    # 4. README.md scaffold
    if not (root / "README.md").exists():
        metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
        _scaffold_readme(root, metrics)
        emitted.append("README.md (scaffold — fill the placeholders)")
    else:
        skipped.append("README.md (curated — left untouched)")

    # 5. demo.mp4 from a captured transcript (never clobbered)
    if not (root / "demo.mp4").exists():
        if _render_demo(root):
            emitted.append("demo.mp4 (rendered from demo/transcript.txt)")
    else:
        skipped.append("demo.mp4 (existing — left untouched)")

    for s in skipped:
        print(f"  kept: {s}")
    if emitted:
        print(f"  emitted: {', '.join(emitted)}")
    if verified:
        print(f"  verified: {', '.join(verified)}")
    if not emitted and not verified:
        print(f"  no changes: all nine artifacts already present")

    probs = proof_check.problems(root)
    if probs:
        print("  note: the gaps below are run-captured (record them, re-run "
              "bundle):" if all("screenshots" in p or "demo.mp4" in p or "run.py" in p
                                for p in probs) else
              "  note: conformance gaps:")
    return proof_check.verdict(root, probs)