#!/usr/bin/env python3
"""Render a Proof's graph.json into graph.png (layered DAG).

Status-colored nodes (done=green, in_progress=amber, needs_revision=red,
todo=grey), subsystem-tagged, top-to-bottom, with a visible legend.

Usage:
    python tools/proof-render-graph.py examples/<name>
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

STATUS_COLOR = {
    "done": "#2e7d32",
    "in_progress": "#f9a825",
    "needs_revision": "#c62828",
    "todo": "#9e9e9e",
}
SYSTEM_COLOR = {
    "core": "#1565c0", "web": "#6a1b9a", "qa": "#00695c", "docs": "#5d4037", "other": "#37474f",
    # Proof #5 `swarm` subsystems (border colors, matched to graph.json)
    "foundation": "#1e88e5", "contract": "#7b1fa2", "storage": "#00897b",
    "auth": "#c62828", "gateway": "#ef6c00", "worker": "#2e7d32",
    "cli": "#5d4037", "observe": "#546e7a", "integration": "#6d4c41",
}


def layered_pos(g):
    """Top-to-bottom layered layout via longest-path ranking from roots."""
    rank = {}
    for n in g.nodes:
        rank[n] = 0
    # longest-path propagation
    changed = True
    while changed:
        changed = False
        for u, v in g.edges:
            if rank[v] < rank[u] + 1:
                rank[v] = rank[u] + 1
                changed = True
    levels = {}
    for n, r in rank.items():
        levels.setdefault(r, []).append(n)
    pos = {}
    for r, nodes in levels.items():
        nodes = sorted(nodes)
        for i, n in enumerate(nodes):
            pos[n] = (i - (len(nodes) - 1) / 2, -r)
    return pos, rank


def main(proof_dir):
    root = Path(proof_dir)
    data = json.loads((root / "graph.json").read_text(encoding="utf-8"))
    G = nx.DiGraph()
    for t in data["tasks"]:
        G.add_node(t["id"], status=t["status"], subsystem=t.get("subsystem", "other"),
                   title=t["title"])
    for e in data["dependencies"]:
        G.add_edge(e["depends_on"], e["task"])

    pos, rank = layered_pos(G)
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

    # nodes as text-sized rounded rectangles (ids never clip)
    from matplotlib.patches import FancyBboxPatch
    for n, d in G.nodes(data=True):
        fill = STATUS_COLOR.get(d["status"], "#9e9e9e")
        ec = SYSTEM_COLOR.get(d["subsystem"], "#37474f")
        x, y = pos[n]
        w = max(len(n), len(d["title"][:26])) * 0.075 + 0.3
        h = 0.78
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=fill, ec=ec, lw=2.2))
        ax.annotate(n, (x, y + 0.14), ha="center", va="center", fontsize=9,
                    color="white", fontweight="bold")
        ax.annotate(d["title"][:26], (x, y - 0.3), ha="center", va="center",
                    fontsize=6.4, color="#222222")

    # legend
    handles = [plt.Line2D([0], [0], marker="s", ls="", markersize=11,
                          markerfacecolor=c, markeredgecolor="#000",
                          label=f"{s}") for s, c in STATUS_COLOR.items()]
    sys_handles = [plt.Line2D([0], [0], marker="s", ls="", markersize=9,
                              markerfacecolor="#ffffff", markeredgewidth=2.2,
                              markeredgecolor=c, label=s) for s, c in SYSTEM_COLOR.items()
                   if s != "other"]
    ax.legend(handles=handles + sys_handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
              frameon=True, fontsize=8, title="status · subsystem border")

    fig.tight_layout()
    out = root / "graph.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"wrote {out} ({len(data['tasks'])} nodes, depth {depth})")


if __name__ == "__main__":
    main(sys.argv[1])