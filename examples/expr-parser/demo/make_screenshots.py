#!/usr/bin/env python3
"""Render proof screenshots (screenshots/*.png) from REAL captured terminal output.

Not doctored: each screenshot renders an actual command/response pair captured
fresh from the proof's ./expr binary, styled like a terminal. Uses the same
theme as the demo renderer so screenshots and demo.mp4 are visually consistent.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG = "#0c0c0c"
CMD = "#7ee787"
OUT = "#d8d8d8"

FRAMES = [
    ("01-cli-single-shot.png", [
        ("$ ./expr \"2+3\"", True), ("5", False),
        ("$ ./expr \"2^3^2\"", True), ("512", False),
        ("$ ./expr \"-2^2\"", True), ("-4", False),
        ("$ ./expr \"sqrt(abs(-9))\"", True), ("3", False),
        ("$ ./expr \"pi*2\"", True), ("6.28318530718", False),
        ("$ ./expr \"1/0\"", True),
        ("division by zero", False),
    ]),
    ("02-repl-session.png", [
        ("$ ./expr", True),
        ("> 2+3", False), ("5", False),
        ("> sqrt(9)", False), ("3", False),
        ("> :ast 2+3*4", False), ("(+ 2 (* 3 4))", False),
        ("> 1/0", False), ("division by zero", False),
        ("> quit", False),
    ]),
]

W, H = 720, 300


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
        ax.text(0.03, y, text, color=color, fontsize=13,
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