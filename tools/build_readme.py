#!/usr/bin/env python3
"""Build the published README.md from README.tmpl.md.

    tools/build_readme.py                 -> dist/README.md

The blog list is owned by the scheduled workflow on the default branch, not by
this template. Rebuilding therefore has to carry the live list across or the
next build would silently revert whatever the workflow last committed. The
order of preference is:

  1. whatever sits between the markers in the published branch's README
  2. the seed list in the template

Never re-fetch the feed here: that would race the workflow and produce a README
that disagrees with the branch it is about to overwrite.
"""

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "README.tmpl.md"
OUT = ROOT / "dist" / "README.md"

START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)


def rel(p):
    """Path relative to the repo root when possible, else as given."""
    try:
        return pathlib.Path(p).resolve().relative_to(ROOT)
    except ValueError:
        return p


def published_blog_block(branch):
    """The marker block as it currently exists on `branch`, or None."""
    try:
        readme = subprocess.run(
            ["git", "show", f"{branch}:README.md"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    m = BLOCK.search(readme)
    return m.group(0) if m else None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--branch", default="main",
                    help="branch whose blog list should be preserved")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=OUT)
    args = ap.parse_args()

    template = TEMPLATE.read_text(encoding="utf-8")
    if not BLOCK.search(template):
        raise SystemExit(f"{TEMPLATE.name} is missing the BLOG-POST-LIST markers")

    live = published_blog_block(args.branch)
    if live:
        # Format-agnostic: the workflow's template is configurable, so count
        # any non-marker line with content rather than matching one shape.
        n = len([l for l in live.split("\n")
                 if l.strip() and not l.lstrip().startswith("<!--")])
        print(f"  carried {n} blog entries across from {args.branch}")
        # A literal replacement, so backslashes in post titles survive intact.
        template = BLOCK.sub(lambda _: live, template, count=1)
    else:
        print(f"  no README on {args.branch}; using the template's seed list",
              file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(template, encoding="utf-8")
    print(f"wrote {rel(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
