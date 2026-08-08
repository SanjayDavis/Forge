#!/usr/bin/env python3
"""demo/shots.py — render REAL captured terminals into screenshots/*.png.

Each PNG is rendered from the actual captured output in demo/record/*.txt
(the commands behind those transcripts were really executed; the captures
are their raw stdout). Same terminal look as tools/proof-render-demo.py:
command lines green, output grey-white, scrolling viewport, blinking-free
final capture.

Usage:
    python examples/swarm/demo/shots.py [examples/swarm]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG = "#0c0c0c"
CMD = "#7ee787"
OUT = "#d8d8d8"
TITLE_COLOR = "#888888"
W, H = 960, 540
VIEWPORT = 22

JOBS = [
    ("01-demo.txt", "01-run.png", "swarm platform: jobs in -> drained"),
    ("02-tests.txt", "02-tests.png", "swarm test suite: 197 tests"),
    ("03-invariants.txt", "03-invariants.png", "S1..S10 invariant verdict"),
    ("04-conformance.txt", "04-conformance.png", "proof-check conformance"),
]


def normalize(text):
    """Normalize line endings, strip trailing ws, collapse blank runs."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for ln in lines:
        if not ln.strip():
            if out and out[-1]:
                out.append("")
            continue
        out.append(ln.rstrip())
    while out and out[0] == "":
        out.pop(0)
    return out


def wrap_lines(lines, width=86):
    import textwrap
    out = []
    for ln in lines:
        if len(ln) <= width:
            out.append(ln)
            continue
        is_cmd = ln.startswith("$ ")
        body = ln[2:] if is_cmd else ln
        chunks = textwrap.wrap(body, width=width, break_long_words=True)
        out.append(("$ " if is_cmd else "") + chunks[0])
        for c in chunks[1:]:
            out.append("    " + c)
    return out


def render(transcript, out, title):
    lines = wrap_lines(normalize(transcript.read_text(encoding="utf-8")))
    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    ax.axis("off")
    y = 0.94
    ax.text(0.04, y, "%-44s %s" % (title, "Proof #5 — swarm"),
            transform=ax.transAxes, family="DejaVu Sans Mono", fontsize=13,
            color=TITLE_COLOR, va="top", ha="left")
    y -= 0.055
    for line in lines[-VIEWPORT:]:
        color = CMD if line.startswith("$ ") else OUT
        ax.text(0.04, y, line, transform=ax.transAxes, family="DejaVu Sans Mono",
                fontsize=17, color=color, va="top", ha="left")
        y -= 0.055
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    print(f"wrote {out.name} ({len(lines[-VIEWPORT:])} lines)")


def main(root):
    root = Path(root)
    rec = root / "demo" / "record"
    shots = root / "screenshots"
    shots.mkdir(exist_ok=True)
    for src, dst, title in JOBS:
        if (rec / src).exists():
            render(rec / src, shots / dst, title)
        else:
            print(f"skip {src} (not recorded)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])