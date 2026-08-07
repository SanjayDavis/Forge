#!/usr/bin/env python3
"""Render proof screenshots (screenshots/*.png) from REAL captured CLI output.

Not doctored: every line is an actual command/response pair captured from the
proof's rcli binary during the smoke runs (see demo/transcript.txt), styled
like a terminal. Same theme as the demo renderer for visual consistency.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG = "#0c0c0c"
CMD = "#7ee787"
OUT = "#d8d8d8"

FRAMES = [
    ("01-cli-stats-summary.png", [
        ("$ rcli stats fixtures/numbers.csv", True),
        ("name: count=5 sum=n/a mean=n/a median=n/a min=n/a max=n/a", False),
        ("score: count=5 sum=20.5 mean=4.1 median=4 min=-3.5 max=10", False),
        ("$ rcli describe fixtures/mixed.csv", True),
        ("id: rows=3 non_empty=3 type=numeric", False),
        ("val: rows=3 non_empty=3 type=mixed", False),
        ("note: rows=3 non_empty=3 type=string", False),
        ("file: 3 data rows, 3 columns", False),
    ]),
    ("02-cli-head-unicode-errors.png", [
        ("$ rcli head fixtures/unicode.csv", True),
        ("caf\u00e9,valeur", False),
        ("1,2", False),
        ("$ rcli head fixtures/quoted.csv -n 1", True),
        ('x,"has, comma"', False),
        ("$ rcli stats fixtures/nope.csv", True),
        ("rcli: The system cannot find the file specified. (os error 2)", False),
        ("$ rcli --help", True),
        ("rcli \u2014 CSV statistics CLI (Proof #4)", False),
        ("USAGE:    rcli stats <file> | describe <file> | head <file> [-n N]", False),
    ]),
]

W, H = 760, 320


def render(lines, path):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    n = len(lines)
    for i, (text, is_cmd) in enumerate(lines):
        y = 1 - (i + 0.7) / (n + 1)
        color = CMD if is_cmd else OUT
        ax.text(0.03, y, text, color=color, fontsize=12.5,
                fontfamily="monospace", va="center")
    fig.savefig(path, facecolor=BG, bbox_inches=None, pad_inches=0)
    plt.close(fig)
    print("wrote", path)


def main():
    import os
    out = os.path.join(os.path.dirname(__file__), "..", "screenshots")
    os.makedirs(out, exist_ok=True)
    for name, lines in FRAMES:
        render(lines, os.path.join(out, name))


if __name__ == "__main__":
    main()