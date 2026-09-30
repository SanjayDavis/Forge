#!/usr/bin/env python3
"""Build a README-sized animated GIF from a proof's rendered frames.

The proofs already ship a demo.mp4 (720p, 1-3 MB) built by
tools/proof-render-demo.py from the PNG frames under demo/.frames/.
GitHub will not autoplay an mp4 in a README, so this downsamples those
same frames into a compact GIF for the README hero.

    python tools/make-readme-gif.py examples/chip8/demo/.frames assets/demo-chip8.gif

Frames are sampled evenly across the run and written as an optimized
palette GIF, so the output is a few hundred KB rather than several MB.
Deterministic: the same frames in produce the same GIF out, which is
what lets it be a committed artifact rather than a build step.
"""
import sys
from pathlib import Path

from PIL import Image

# GitHub renders a README GIF at a width the reader controls; anything
# past ~900px is wasted bytes. 640 keeps text legible at typical column
# widths while staying small.
WIDTH = 640
# Terminal-style frames are mostly static between "line appears" steps.
# Sampling every Nth frame keeps the perceived motion and drops the rest.
DEFAULT_STRIDE = 12
MAX_FRAMES = 90
DURATION_MS = 90
# Terminal frames are flat-shaded on a near-black background, so a small
# adaptive palette is visually lossless and roughly halves the file. A
# README GIF is downloaded by every visitor: 640px wide, <=256 colors.
PALETTE_COLORS = 128


def build(frames_dir: Path, out_path: Path, width: int = WIDTH,
          stride: int = DEFAULT_STRIDE) -> dict:
    src = sorted(frames_dir.glob("*.png"))
    if not src:
        raise SystemExit(f"no frames in {frames_dir}")

    # Always keep the first and last frame: the run's start and its
    # result are the two states worth showing.
    picked = src[::stride]
    if picked[-1] != src[-1]:
        picked.append(src[-1])
    if len(picked) > MAX_FRAMES:
        step = len(picked) / MAX_FRAMES
        picked = [picked[int(i * step)] for i in range(MAX_FRAMES)]

    frames = []
    for p in picked:
        im = Image.open(p).convert("RGB")
        h = round(im.height * width / im.width)
        frames.append(im.resize((width, h), Image.LANCZOS))

    # Quantize every frame against ONE shared palette, built from the
    # first frame. Per-frame adaptive palettes churn between frames and
    # are the main reason naive GIF exports are large; a shared palette
    # plus disposal=1 keeps consecutive frames diffing cleanly.
    palette = frames[0].convert("RGB").quantize(
        colors=PALETTE_COLORS, method=Image.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.NONE)
                 for f in frames]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        out_path, save_all=True, append_images=quantized[1:],
        duration=DURATION_MS, loop=0, optimize=True, disposal=1,
    )
    return {
        "frames_in": len(src), "frames_used": len(frames),
        "size": (frames[0].width, frames[0].height),
        "bytes": out_path.stat().st_size,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    frames = Path(sys.argv[1])
    out = Path(sys.argv[2])
    info = build(frames, out)
    kb = info["bytes"] / 1024
    print(f"{out}: {info['frames_used']}/{info['frames_in']} frames, "
          f"{info['size'][0]}x{info['size'][1]}, {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
