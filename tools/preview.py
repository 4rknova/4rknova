#!/usr/bin/env python3
"""Preview README.md the way GitHub renders it, and check ASCII-art alignment.

    tools/preview.py            render to preview.html and open a browser
    tools/preview.py --check    verify every line inside a fence has equal width
    tools/preview.py --no-open  render only, don't launch a browser

Rendering goes through GitHub's own Markdown API, so the HTML is what GitHub
produces. Styling uses github-markdown-css, fetched at run time. Either step
degrades gracefully; the page reports which fidelity level it achieved.
"""

import argparse
import json
import pathlib
import sys
import unicodedata
import urllib.error
import urllib.request
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
OUT = ROOT / "preview.html"

MARKDOWN_API = "https://api.github.com/markdown"
# The combined stylesheet picks a theme via prefers-color-scheme, which would
# ignore the toggle in the preview chrome. Fetch the two single-theme files
# instead and scope each to a data-theme attribute. Every selector in them is
# .markdown-body-prefixed, so a textual prefix is safe.
CSS_CDN = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown-{}.css"
REPO_CONTEXT = "4rknova/4rknova"

# GitHub renders a code block in the first font the viewer actually has. The
# order matters: a viewer missing all of these falls back to a metrics-
# incompatible font and the box art will shear regardless of what we do here.
MONO_STACK = (
    'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
    '"Liberation Mono", monospace'
)


def display_width(s):
    """Column count as a terminal or monospace font would measure it."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def fenced_blocks(text):
    """Yield (start_line, [lines]) for each ``` fenced block, 1-indexed."""
    lines = text.split("\n")
    inside = False
    start = 0
    buf = []
    for n, line in enumerate(lines, 1):
        if line.startswith("```"):
            if inside:
                yield start, buf
                buf = []
            else:
                start = n + 1
            inside = not inside
            continue
        if inside:
            buf.append(line)


def check(text):
    """Report width drift inside fenced blocks. Returns a process exit code."""
    problems = 0
    for start, block in fenced_blocks(text):
        widths = {}
        for offset, line in enumerate(block):
            widths.setdefault(display_width(line), []).append(start + offset)
        if len(widths) <= 1:
            w = next(iter(widths), 0)
            print(f"  ok    lines {start}-{start + len(block) - 1}: all {w} cols")
            continue
        # The majority width is the intended one; everything else is drift.
        expected = max(widths, key=lambda w: len(widths[w]))
        print(f"  DRIFT lines {start}-{start + len(block) - 1}: expected {expected} cols")
        for w in sorted(widths):
            if w == expected:
                continue
            for ln in widths[w]:
                problems += 1
                print(f"        line {ln}: {w} cols ({w - expected:+d})")
    if problems:
        print(f"\n{problems} line(s) out of alignment.")
        return 1
    print("\nAll fenced blocks are internally aligned.")
    return 0


def fetch(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


def render_markdown(text):
    """GitHub's own GFM HTML, or None if the API is unreachable."""
    payload = json.dumps(
        {"text": text, "mode": "gfm", "context": REPO_CONTEXT}
    ).encode("utf-8")
    try:
        return fetch(
            MARKDOWN_API,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "User-Agent": "4rknova-readme-preview",
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"  markdown api unavailable ({e}); falling back to a local render",
              file=sys.stderr)
        return None


def render_locally(text):
    """Enough Markdown to judge layout when the API is unreachable."""
    import html as html_mod

    out = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html_mod.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
        elif line.startswith("### "):
            out.append(f"<h3>{html_mod.escape(line[4:])}</h3>")
        elif line.startswith("- ["):
            buf = []
            while i < len(lines) and lines[i].startswith("- ["):
                item = lines[i][2:]
                label, _, rest = item.partition("](")
                buf.append(f'<li><a href="{rest.rstrip(")")}">'
                           f'{html_mod.escape(label[1:])}</a></li>')
                i += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        elif line.strip():
            out.append(line)  # raw HTML blocks pass through
        i += 1
    return "\n".join(out)


def fetch_css():
    """GitHub's markdown stylesheet, both themes, scoped to the toggle."""
    try:
        parts = []
        for theme in ("light", "dark"):
            sheet = fetch(CSS_CDN.format(theme),
                          headers={"User-Agent": "4rknova-readme-preview"})
            parts.append(sheet.replace(".markdown-body",
                                       f"[data-theme={theme}] .markdown-body"))
        return "\n".join(parts), True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"  github-markdown-css unavailable ({e}); using built-in metrics",
              file=sys.stderr)
        return FALLBACK_CSS, False


FALLBACK_CSS = """
.markdown-body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",
Helvetica,Arial,sans-serif;font-size:16px;line-height:1.5;color:var(--fg)}
.markdown-body h3{font-size:1.25em;font-weight:600;margin:24px 0 16px;
padding-bottom:.3em;border-bottom:1px solid var(--border)}
.markdown-body pre{background:var(--canvas-subtle);border-radius:6px;padding:16px;
overflow:auto;font-size:85%;line-height:1.45}
.markdown-body pre code{font-family:__MONO__;background:none;padding:0;white-space:pre}
.markdown-body ul{padding-left:2em;margin:0 0 16px}
.markdown-body a{color:var(--link);text-decoration:none}
.markdown-body a:hover{text-decoration:underline}
""".replace("__MONO__", MONO_STACK)

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>README preview - github.com/4rknova</title>
<style>
__CSS__
:root{--canvas:#fff;--canvas-subtle:#f6f8fa;--fg:#1f2328;--border:#d1d9e0;
--link:#0969da;--muted:#59636e}
[data-theme=dark]{--canvas:#0d1117;--canvas-subtle:#151b23;--fg:#f0f6fc;
--border:#3d444d;--link:#4493f8;--muted:#9198a1}
html{color-scheme:light}
html[data-theme=dark]{color-scheme:dark}
body{margin:0;background:var(--canvas);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.bar{position:sticky;top:0;z-index:9;display:flex;gap:8px;align-items:center;
flex-wrap:wrap;padding:10px 16px;background:var(--canvas-subtle);
border-bottom:1px solid var(--border);font-size:12px;color:var(--muted)}
.bar button{font:inherit;padding:4px 10px;border:1px solid var(--border);
border-radius:6px;background:var(--canvas);color:var(--fg);cursor:pointer}
.bar button[aria-pressed=true]{background:var(--link);border-color:var(--link);
color:#fff}
.bar .note{margin-left:auto}
.stage{padding:24px 16px;display:flex;justify-content:center}
/* The profile README sits in a bordered box on the profile page. */
.box{width:100%;max-width:var(--w,860px);border:1px solid var(--border);
border-radius:6px;background:var(--canvas)}
.box-head{padding:8px 16px;border-bottom:1px solid var(--border);font-size:12px;
color:var(--muted)}
/* Two-selector specificity, so this beats the scoped github-markdown-css
   rules above rather than losing to them. */
.box .markdown-body{padding:16px}
.box .markdown-body pre code{font-family:__MONO__}
</style>
<div class="bar">
  <span>theme</span>
  <button data-theme-btn="light" aria-pressed="true">light</button>
  <button data-theme-btn="dark" aria-pressed="false">dark</button>
  <span style="margin-left:12px">width</span>
  <button data-w="860" aria-pressed="true">desktop</button>
  <button data-w="620" aria-pressed="false">tablet</button>
  <button data-w="380" aria-pressed="false">phone</button>
  <span class="note">__FIDELITY__</span>
</div>
<div class="stage">
  <div class="box">
    <div class="box-head">4rknova / README.md</div>
    <article class="markdown-body">
__BODY__
    </article>
  </div>
</div>
<script>
const root = document.documentElement;
const box = document.querySelector('.box');
function group(sel, fn){
  const btns = [...document.querySelectorAll(sel)];
  btns.forEach(b => b.addEventListener('click', () => {
    btns.forEach(o => o.setAttribute('aria-pressed', String(o === b)));
    fn(b);
  }));
}
group('[data-theme-btn]', b => root.setAttribute('data-theme', b.dataset.themeBtn));
group('[data-w]', b => box.style.setProperty('--w', b.dataset.w + 'px'));
root.setAttribute('data-theme', 'light');
</script>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", type=pathlib.Path, default=README,
                    help="markdown file to preview (default: README.md)")
    ap.add_argument("--check", action="store_true",
                    help="only verify fenced-block alignment, don't render")
    ap.add_argument("--no-open", action="store_true",
                    help="write preview.html but don't launch a browser")
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"no such file: {args.source}")
    text = args.source.read_text(encoding="utf-8")

    print(f"checking {args.source}")
    code = check(text)
    if args.check:
        return code

    print("\nrendering")
    body = render_markdown(text)
    api_ok = body is not None
    if not api_ok:
        body = render_locally(text)
    css, css_ok = fetch_css()

    if api_ok and css_ok:
        fidelity = "github markdown api + github-markdown-css"
    elif api_ok:
        fidelity = "github markdown api + built-in css (approximate styling)"
    else:
        fidelity = "local render + built-in css (approximate)"

    page = (PAGE.replace("__CSS__", css)
                .replace("__MONO__", MONO_STACK)
                .replace("__FIDELITY__", fidelity)
                .replace("__BODY__", body))
    OUT.write_text(page, encoding="utf-8")
    print(f"  {fidelity}")
    print(f"  wrote {OUT.relative_to(ROOT)}")

    if not args.no_open:
        webbrowser.open(OUT.as_uri())
    return code


if __name__ == "__main__":
    sys.exit(main())
