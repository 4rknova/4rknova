#!/usr/bin/env python3
"""Render a rotating ASCII torus into dist/bio.anim.

    tools/gen_torus.py                  read bio.conf
    tools/gen_torus.py other.conf       read a different source

Everything configurable lives in the .conf file: frame count, loop duration,
viewport size, the layout, and the info block beside the torus. Nothing
in this script should need editing to change what the animation says.

Feed the result to tools/anim2svg.py to get the SVG the README embeds.
"""

import argparse
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONF_FILE = ROOT / "bio.conf"
OUT = ROOT / "dist" / "bio.anim"

RAMP = ".,-~:;=!*#$@"

DEFAULTS = {
    "frames": "24",
    "duration": "4.0",
    "phase": "1.1",
    "cols": "66",
    "rows": "20",
    "header": "4rknova / framebuffer 0",
    "title": "Rotating ASCII torus, 4rknova",
    "fontsize": "14",
    "color": "#7d8590",
    "color_dark": "",
    "caption": "right",
    "border": "off",
    "fill": "0.92",
}
NUMERIC = {"frames": int, "duration": float, "phase": float,
           "cols": int, "rows": int, "fill": float}


def load_conf(path):
    """Return (settings, caption_lines) from a .conf file.

    Directives sit above the '---' separator, the caption below it. A value may
    carry a trailing ' #' comment, which is stripped; the space is required so
    that '#rrggbb' colours survive.
    """
    if not path.exists():
        raise SystemExit(f"no config at {path}")

    meta = dict(DEFAULTS)
    caption = []
    in_caption = False

    for n, raw in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        line = raw.rstrip("\r")
        if in_caption:
            caption.append(line)
            continue
        if line.strip() == "---":
            in_caption = True
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith("@"):
            raise SystemExit(f"{path.name}:{n}: expected @directive, got {line!r}")
        key, _, val = line[1:].partition(" ")
        # Comments are '#' followed by a space; a '#' followed by anything else
        # is a value, so '#rrggbb' colours survive. Leading padding is trimmed
        # first, otherwise the alignment spaces before a colour look exactly
        # like the ' #' that introduces a comment.
        val = val.lstrip()
        if val.startswith("# "):
            val = ""                      # the whole value is a comment
        elif " #" in val:
            val = val.split(" #")[0]      # a comment after a real value
        meta[key.strip()] = val.rstrip()

    if not in_caption:
        raise SystemExit(f"{path.name}: missing the '---' separator")

    while caption and not caption[-1].strip():
        caption.pop()          # trailing newline, not a deliberate blank row

    for key, cast in NUMERIC.items():
        try:
            meta[key] = cast(meta[key])
        except (ValueError, TypeError):
            raise SystemExit(f"{path.name}: @{key} must be "
                             f"{cast.__name__}, got {meta[key]!r}")

    if meta["border"] not in ("on", "off"):
        raise SystemExit(f"{path.name}: @border must be 'on' or 'off', "
                         f"got {meta['border']!r}")
    if meta["caption"] not in ("left", "right", "below"):
        raise SystemExit(f"{path.name}: @caption must be 'left', 'right' or "
                         f"'below', got {meta['caption']!r}")

    # Beside the torus the box grows to fit the caption, so only the 'below'
    # layout can overflow.
    room = max(meta["cols"], 1) if meta["caption"] == "below" else 10 ** 6
    problems = []
    if meta["caption"] == "below" and len(meta["header"]) > room:
        problems.append(f"  @header is {len(meta['header'])} chars, max {room}")
    for i, line in enumerate(caption, 1):
        if len(line) > room:
            problems.append(
                f"  caption line {i} is {len(line)} chars, max {room}: {line!r}")
        if not line.isascii():
            bad = sorted({c for c in line if not c.isascii()})
            problems.append(f"  caption line {i} has non-ASCII {bad}")
    if problems:
        raise SystemExit(f"{path.name} is unusable:\n" + "\n".join(problems))

    return meta, caption


K2 = 5.0                   # distance from viewer to the torus centre


def fit_scale(angles, W, H, fill):
    """One projection scale that keeps every frame inside the viewport.

    Deriving it from the width alone (as donut.c does) only works while the
    viewport is roughly square. A wide, short viewport is height-limited, and
    a width-derived scale would push the torus off the top and bottom.

    The scale is shared by every frame; computing it per frame would make the
    torus visibly pulse as it turns.
    """
    mx = my = 1e-9
    for A, B in angles:
        cA, sA = math.cos(A), math.sin(A)
        cB, sB = math.cos(B), math.sin(B)
        theta = 0.0
        while theta < 6.29:
            ct, st = math.cos(theta), math.sin(theta)
            phi = 0.0
            while phi < 6.29:
                cp, sp = math.cos(phi), math.sin(phi)
                circlex, circley = 2 + ct, st
                x = circlex * (cB * cp + sA * sB * sp) - circley * cA * sB
                y = circlex * (sB * cp - sA * cB * sp) + circley * cA * cB
                ooz = 1 / (K2 + cA * circlex * sp + circley * sA)
                mx = max(mx, abs(x * ooz))
                my = max(my, abs(y * ooz))
                phi += 0.08
            theta += 0.08
    # xp = W/2 + K1*ooz*x        needs K1*mx <= W/2
    # yp = H/2 - K1*ooz*y*0.5    needs K1*my*0.5 <= H/2
    return fill * min(W / (2 * mx), H / my)


def torus(A, B, W, H, K1, dtheta=0.010, dphi=0.020):
    """Z-buffered ASCII torus. A and B are the two rotation angles."""
    zbuf = [0.0] * (W * H)
    out = [" "] * (W * H)
    cA, sA = math.cos(A), math.sin(A)
    cB, sB = math.cos(B), math.sin(B)
    theta = 0.0
    while theta < 6.28:
        ct, st = math.cos(theta), math.sin(theta)
        phi = 0.0
        while phi < 6.28:
            cp, sp = math.cos(phi), math.sin(phi)
            circlex, circley = 2 + ct, st
            x = circlex * (cB * cp + sA * sB * sp) - circley * cA * sB
            y = circlex * (sB * cp - sA * cB * sp) + circley * cA * cB
            z = K2 + cA * circlex * sp + circley * sA
            ooz = 1 / z
            xp = int(W / 2 + K1 * ooz * x)
            # 0.5 compensates for character cells being ~2x taller than wide.
            yp = int(H / 2 - K1 * ooz * y * 0.5)
            L = (cp * ct * sB - cA * ct * sp - sA * st
                 + cB * (cA * st - ct * sA * sp))
            if L > 0 and 0 <= xp < W and 0 <= yp < H:
                i = xp + W * yp
                if ooz > zbuf[i]:
                    zbuf[i] = ooz
                    out[i] = RAMP[min(len(RAMP) - 1, int(L * 8))]
            phi += dphi
        theta += dtheta
    return ["".join(out[r * W:(r + 1) * W]) for r in range(H)]


GAP = 3                    # columns between the torus and a side caption


SIDEWAYS = ("left", "right")


def inner_width(meta, caption):
    """Content width, which the caption placement decides."""
    capw = max((len(l) for l in caption), default=0)
    if meta["caption"] in SIDEWAYS:
        w = meta["cols"] + GAP + capw
    else:
        w = max(meta["cols"], capw)
    if meta["border"] == "off":
        # Without a frame the header is a plain line and can be the widest.
        w = max(w, len(meta["header"]))
    return w


def frame(A, B, meta, caption, K1):
    inner, header = inner_width(meta, caption), meta["header"]
    art = torus(A, B, meta["cols"], meta["rows"], K1)

    if meta["caption"] in SIDEWAYS:
        # Caption sits beside the torus, vertically centred against it. A wide
        # viewport with the caption below would leave dead space either side
        # of the torus, which is the whole reason for this layout.
        pad = (meta["rows"] - len(caption)) // 2
        beside = [""] * pad + list(caption)
        beside += [""] * (meta["rows"] - len(beside))
        capw = max((len(l) for l in caption), default=0)
        gap = " " * GAP
        if meta["caption"] == "right":
            body = [a.ljust(meta["cols"]) + gap + c
                    for a, c in zip(art, beside)]
        else:
            body = [c.ljust(capw) + gap + a
                    for a, c in zip(art, beside)]
        below = []
    else:
        body, below = list(art), list(caption)

    if meta["border"] == "off":
        lines = ([header, ""] if header else []) + body
        if below:
            lines += [""] + below
        # anim2svg requires every row in a frame to be the same width.
        return [l.rstrip().ljust(inner) for l in lines]

    box = inner + 2
    rule = "+" + "-" * box + "+"
    lines = ["+- " + header + " " + "-" * (box - len(header) - 3) + "+"]
    lines += ["| " + l.ljust(inner) + " |" for l in body]
    if below:
        lines.append(rule)
        lines += ["| " + l.ljust(inner) + " |" for l in below]
    lines.append(rule)
    return lines


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("conf", nargs="?", type=pathlib.Path, default=CONF_FILE,
                    help="animation source (default: bio.conf)")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=OUT)
    args = ap.parse_args()

    meta, caption = load_conf(args.conf)
    frames = meta["frames"]
    angles = [meta["phase"] + 2 * math.pi * i / frames for i in range(frames)]
    K1 = fit_scale([(a, a) for a in angles], meta["cols"], meta["rows"],
                   meta["fill"])

    # Only the directives anim2svg understands are forwarded; the rest are
    # consumed here.
    out = [
        "# Generated by tools/gen_torus.py - do not edit.",
        "# Edit bio.conf and run 'make' instead.",
        f"@duration {meta['duration']:g}",
        f"@fontsize {meta['fontsize']}",
        f"@color {meta['color']}",
        f"@color_dark {meta['color_dark']}",
        f"@title {meta['title']}",
    ]

    for i in range(frames):
        # Both angles complete exactly one revolution, so the loop is seamless.
        # @phase only shifts where it starts: at zero the torus is face-on and
        # reads as a blob, which is a poor first frame.
        a = angles[i]
        out.append("---")
        out.extend(frame(a, a, meta, caption, K1))
        print(f"  frame {i + 1}/{frames}", end="\r", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out) + "\n"
    args.out.write_text(text, encoding="utf-8")
    kb = len(text.encode("utf-8")) / 1024
    print(f"read  {args.conf} ({frames} frames, {len(caption)} caption lines)")
    print(f"wrote {args.out} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
