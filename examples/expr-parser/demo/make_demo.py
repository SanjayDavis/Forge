#!/usr/bin/env python3
"""Fast terminal-style demo renderer for Proof #3 (local alternative to
tools/proof-render-demo.py, which is matplotlib-slow and fixed at 1.9s/line).

Reads the SAME real transcript as the canonical tool and renders a 960x540,
<=120s H.264 mp4 with a scrolling terminal window and blinking cursor.
Pacing is tighter (1.33s/line) so the full 66-line session fits the
conformance limit. Output: demo.mp4 (frames staged in demo/.frames).
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import matplotlib
from matplotlib import font_manager

BG = (12, 12, 12)
CMD = (126, 231, 135)
OUT = (216, 216, 216)
TITLE_C = (136, 136, 136)
CURSOR = (86, 182, 194)
W, H = 960, 540
FPS = 12
PER_LINE_SEC = 1.33
VIEWPORT = 16
FONTSIZE = 17


def get_font(path=None):
    if path:
        return ImageFont.truetype(path, FONTSIZE)
    fp = font_manager.findfont("DejaVu Sans Mono")
    return ImageFont.truetype(fp, FONTSIZE)


def humanize(raw):
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for ln in lines:
        out.append(ln.rstrip() if ln.strip() else "")
    while out and out[0] == "":
        out.pop(0)
    collapsed = []
    for ln in out:
        if ln == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(ln)
    return collapsed


def wrap_lines(lines, width=86):
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


def render_frame(draw, lines, idx, blink):
    draw.rectangle([0, 0, W, H], fill=BG)
    draw.text((24, 16), "Forge Proof demo — real terminal run  ·", font=FONT,
              fill=TITLE_C)
    start = max(0, idx - VIEWPORT)
    shown = lines[start:idx]
    y = 56
    for line in shown:
        color = CMD if line.startswith("$ ") else OUT
        draw.text((24, y), line, font=FONT, fill=color)
        y += 27
    if blink:
        draw.rectangle([24, y, 24 + 14, y + 26], fill=CURSOR)


def main(proof_dir, transcript_path, out_name="demo.mp4"):
    root = Path(proof_dir)
    lines = wrap_lines(humanize(Path(transcript_path).read_text(
        encoding="utf-8")))
    frames = root / "demo" / ".frames"
    frames.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    per_line = max(1, int(PER_LINE_SEC * FPS))
    total = len(lines)
    k = 0
    for blank in range(FPS):
        k += 1
        render_frame(draw, lines, 0, blink=(blank // 6) % 2 == 0)
        img.save(frames / f"f_{k:04d}.png")
    for i in range(1, total + 1):
        for step in range(per_line):
            k += 1
            n = i - 1 if step < int(per_line * 0.6) else i
            render_frame(draw, lines, n, blink=(step // 4) % 2 == 0)
            img.save(frames / f"f_{k:04d}.png")
    for step in range(int(2.0 * FPS)):
        k += 1
        render_frame(draw, lines, total, blink=False)
        img.save(frames / f"f_{k:04d}.png")

    seconds = k / FPS
    out = root / out_name
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
        "-i", str(frames / "f_%04d.png"), "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-profile:v", "baseline",
        "-movflags", "+faststart", "-vf", "scale=960:-2", str(out),
    ], check=True)
    print(f"wrote {out.name}: {total} lines, {seconds:.0f}s @ {W}x{H}, {k} frames")


FONT = get_font()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "demo.mp4")