#!/usr/bin/env python3
"""Compile an ASCII animation (.anim) into an animated SVG for the README.

    tools/anim2svg.py                       dist/bio.anim -> dist/bio.svg
    tools/anim2svg.py --check               validate only, write nothing
    tools/anim2svg.py in.anim -o out.svg

GitHub strips <script> from READMEs, so JS animation is impossible. CSS
animations inside an SVG loaded via <img> do still run, and that is the hook
this uses: every frame becomes a <g> that is opaque for one slice of the cycle
and transparent for the rest, staggered by animation-delay.

Rows that are identical across every frame are emitted once as static text
rather than duplicated per frame, which is what keeps the file small even
though the source repeats the box and HUD in each frame.

.anim format
------------
    # comment (outside a frame body)
    @duration 4.0        seconds for one full loop
    @fontsize 14         px
    @color #7d8590       glyph colour
    @color_dark #adbac7  glyph colour when the viewer prefers dark
    @title ...           accessible label
    ---                  frame separator
    <frame lines>
    ---
    <frame lines>
"""

import argparse
import pathlib
import sys
import unicodedata
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "dist" / "bio.anim"
DEFAULT_OUT = ROOT / "dist" / "bio.svg"

DEFAULTS = {
    "duration": "4.0",
    "fontsize": "14",
    "color": "#7d8590",
    "color_dark": "",
    "title": "ASCII animation",
}

# A monospace advance is ~0.6em. Frames align because the font is monospace;
# these numbers only size the viewBox and line spacing.
ADVANCE_EM = 0.601
LINE_EM = 1.32
PAD = 12

MONO = ("ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
        "'Liberation Mono',monospace")


def rel(p):
    """Path relative to the repo root when possible, else as given."""
    try:
        return pathlib.Path(p).resolve().relative_to(ROOT)
    except ValueError:
        return p


def display_width(s):
    """Column count as a monospace font measures it."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def parse(text):
    """Return (directives, frames). Frames are lists of lines."""
    meta = dict(DEFAULTS)
    frames = []
    current = None

    source = text.split("\n")
    if source and source[-1] == "":
        # The file's terminal newline, not a row. Dropping it here rather than
        # trimming blank rows per frame, which would eat deliberate blank rows
        # at the bottom of a frame and leave frames with unequal heights.
        source.pop()

    for raw in source:
        line = raw.rstrip("\r")
        if current is None:
            # Header region: directives and comments only.
            if not line.strip():
                continue
            if line.startswith("@"):
                key, _, val = line[1:].partition(" ")
                meta[key.strip()] = val.strip()
                continue
            if line.startswith("#"):
                continue
            if line.strip() == "---":
                current = []
                continue
            raise SystemExit(f"unexpected line before first '---': {line!r}")
        else:
            if line.strip() == "---":
                frames.append(current)
                current = []
                continue
            current.append(line)

    if current is not None:
        frames.append(current)

    # A trailing separator produces an empty final frame; drop it.
    frames = [f for f in frames if f]
    if not frames:
        raise SystemExit("no frames found")
    return meta, frames


def validate(frames):
    """Frames must be rectangular and mutually the same size."""
    problems = []
    heights = {len(f) for f in frames}
    if len(heights) != 1:
        problems.append(f"frames differ in height: {sorted(heights)}")

    for n, f in enumerate(frames, 1):
        widths = {display_width(l) for l in f}
        if len(widths) > 1:
            expected = max(widths, key=lambda w: sum(
                1 for l in f if display_width(l) == w))
            for i, l in enumerate(f):
                w = display_width(l)
                if w != expected:
                    problems.append(
                        f"frame {n} line {i + 1}: {w} cols, expected {expected}")
    return problems


def build(meta, frames):
    duration = float(meta["duration"])
    fs = float(meta["fontsize"])
    advance, line_h = fs * ADVANCE_EM, fs * LINE_EM

    rows = len(frames[0])
    cols = max(display_width(l) for f in frames for l in f)
    width = cols * advance + PAD * 2
    height = rows * line_h + PAD * 2
    y0 = PAD + fs

    # A row whose content never changes is drawn once instead of once per frame.
    static = {}
    for r in range(rows):
        values = {f[r] for f in frames}
        if len(values) == 1:
            static[r] = values.pop()

    slice_pct = 100.0 / len(frames)
    css = (
        f"text{{font-family:{MONO};font-size:{fs:g}px;"
        f"fill:{meta['color']};white-space:pre}}"
        f".f{{opacity:0;animation:cycle {duration:g}s steps(1,end) infinite}}"
        f"@keyframes cycle{{0%{{opacity:1}}{slice_pct:.4f}%{{opacity:0}}"
        f"100%{{opacity:0}}}}"
    )
    # Resolved against the viewer's browser/OS preference, not GitHub's own
    # theme toggle - see the README for what that does and does not cover.
    if meta["color_dark"]:
        css += (f"@media(prefers-color-scheme:dark)"
                f"{{text{{fill:{meta['color_dark']}}}}}")

    def text(s, r):
        return (f'<text x="{PAD}" y="{y0 + r * line_h:.1f}" '
                f'xml:space="preserve">{escape(s)}</text>')

    out = [
        "<!-- Generated by tools/anim2svg.py from bio.conf. Do not edit. -->",
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'role="img" aria-label="{escape(meta["title"])}">',
        f"<style>{css}</style>",
    ]
    for r in sorted(static):
        out.append(text(static[r], r))

    for i, f in enumerate(frames):
        # Positive delay, not negative: a negative offset makes the visibility
        # windows fire in reverse and plays the animation backwards.
        delay = duration * i / len(frames)
        out.append(f'<g class="f" style="animation-delay:{delay:.3f}s">')
        for r in range(rows):
            if r not in static:
                out.append(text(f[r], r))
        out.append("</g>")

    out.append("</svg>")
    return "\n".join(out), len(static), rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", type=pathlib.Path, default=DEFAULT_IN)
    ap.add_argument("-o", "--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="validate the .anim and exit without writing")
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"no such file: {args.source}")

    meta, frames = parse(args.source.read_text(encoding="utf-8"))
    print(f"{args.source.name}: {len(frames)} frames, "
          f"{len(frames[0])} rows, {float(meta['duration']):g}s loop")

    problems = validate(frames)
    if problems:
        for p in problems:
            print(f"  ERROR {p}", file=sys.stderr)
        return 1
    print("  geometry ok")

    if args.check:
        return 0

    svg, n_static, rows = build(meta, frames)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    kb = len(svg.encode("utf-8")) / 1024
    print(f"  {n_static}/{rows} rows static, deduped")
    print(f"wrote {rel(args.out)} ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
