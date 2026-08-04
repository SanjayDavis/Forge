#!/usr/bin/env python3
"""Render a shell transcript into a proof's demo.mp4 (terminal-style video).

Reads a transcript and produces a 720p-class H.264 mp4 of the lines appearing
progressively, like a terminal session, with a blinking cursor. Keeps the raw
transcript and intermediate frames under demo/ (not part of the artifact bundle).

Usage:
    python tools/proof-render-demo.py examples/<name> examples/<name>/demo/transcript.txt
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FPS = 12
SECONDS_PER_LINE = 1.9
CMD_COLOR = "#7ee787"     # command echoes (green, like a terminal prompt)
OUT_COLOR = "#d8d8d8"     # program output (grey-white)
TITLE = "Forge Proof demo — real terminal run"
BG = "#0c0c0c"
W, H = 960, 540


def humanize(raw):
    """Normalize \r\n, drop stray blank dupes from tee, strip ansi-free lines."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for ln in lines:
        if not ln.strip():
            out.append("")
            continue
        out.append(ln.rstrip())
    # trim leading blank lines
    while out and out[0] == "":
        out.pop(0)
    # collapse runs of blank lines to a single blank
    collapsed = []
    for ln in out:
        if ln == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(ln)
    return collapsed


VIEWPORT = 16  # content lines visible before the terminal scrolls


def wrap_lines(lines, width=86):
    """Wrap long lines to fit the frame; keep the '$ ' shell prefix on the first chunk."""
    import textwrap
    out = []
    for ln in lines:
        if len(ln) <= width:
            out.append(ln)
            continue
        cont = "    "
        is_cmd = ln.startswith("$ ")
        body = ln[2:] if is_cmd else ln
        chunks = textwrap.wrap(body, width=width - 4, break_long_words=True)
        out.append(("$ " if is_cmd else "") + chunks[0])
        for c in chunks[1:]:
            out.append(cont + c)
    return out


def render_frame(fig, ax, lines, idx, blink):
    ax.clear()
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    ax.axis("off")
    # scroll: show a fixed-height window that always ends at the newest line
    start = max(0, idx - VIEWPORT)
    shown = lines[start:idx]
    text = "\n".join(shown) if shown else " "
    y = 0.94
    scrollbar = "▸" if start > 0 else "·"
    ax.text(0.04, 0.98, "%-34s %s" % (TITLE, scrollbar), transform=ax.transAxes,
            family="DejaVu Sans Mono", fontsize=13, color="#888888", va="top", ha="left")
    y -= 0.055
    for line in shown:
        color = CMD_COLOR if line.startswith("$ ") else OUT_COLOR
        ax.text(0.04, y, line, transform=ax.transAxes, family="DejaVu Sans Mono",
                fontsize=17, color=color, va="top", ha="left")
        y -= 0.055
    # cursor block at first blank line below content
    if blink:
        ax.add_patch(plt.Rectangle((0.04, y - 0.03), 0.014, 0.05,
                                   transform=ax.transAxes, color="#56b6c2"))


def main(proof_dir, transcript_path, out_name="demo.mp4"):
    root = Path(proof_dir)
    lines = wrap_lines(humanize(Path(transcript_path).read_text(encoding="utf-8")))
    demo = root / "demo"
    frames = demo / ".frames"
    frames.mkdir(parents=True, exist_ok=True)

    per_line = int(SECONDS_PER_LINE * FPS)
    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)

    total = len(lines)
    k = 0
    reveal = 0
    # intro: blank for 24 frames, then reveal lines
    for blank in range(FPS):
        k += 1
        render_frame(fig, ax, lines, 0, blink=(blank // 6) % 2 == 0)
        fig.savefig(frames / f"f_{k:04d}.png")
    for i in range(1, total + 1):
        for step in range(per_line):
            k += 1
            n = i - 1 if step < int(per_line * 0.6) else i
            render_frame(fig, ax, lines, n, blink=(step // 4) % 2 == 0)
            fig.savefig(frames / f"f_{k:04d}.png")
    # hold final frame
    hold = int(2.0 * FPS)
    for step in range(hold):
        k += 1
        render_frame(fig, ax, lines, total, blink=False)
        fig.savefig(frames / f"f_{k:04d}.png")

    import subprocess
    seconds = k / FPS
    out = root / out_name
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(FPS), "-i", str(frames / "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "baseline",
        "-movflags", "+faststart", "-vf", "scale=960:-2", str(out),
    ], check=True)
    print(f"wrote {out.name}: {total} lines, {seconds:.0f}s @ {W}x{H}, {k} frames")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "demo.mp4")