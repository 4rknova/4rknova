# Profile README source

Build sources for the profile README on `main`. Nothing here is published
directly; `make publish` generates `main`'s `README.md` from these files.

## Layout

Inputs, edited by hand:

    bio.conf            settings and caption text for the animation
    README.tmpl.md      README skeleton with the blog markers
    tools/gen_torus.py  renders bio.conf into dist/bio.anim
    tools/anim2svg.py   compiles dist/bio.anim into dist/bio.svg
    tools/build_readme.py  fills the template, preserving the live blog list
    tools/preview.py    renders a README the way GitHub will display it

Everything in `dist/` is a **generated output**. Do not edit it; `make`
overwrites it, and each file carries a header saying so. It is committed
rather than ignored only because `dist/bio.svg` has to be reachable over
HTTP for the profile README to display it.

    dist/bio.anim       generated: one ASCII frame per '---' block
    dist/bio.svg        generated: the animated SVG the README embeds
    dist/README.md      generated: what 'make publish' copies onto main

## Usage

    make            rebuild bio.anim, bio.svg and build/README.md
    make check      validate frame geometry, write nothing
    make preview    open build/README.md styled as GitHub renders it
    make publish    commit build/README.md onto main

## Why an SVG

GitHub strips `<script>`, `<style>`, and inline event handlers from README
HTML, so JavaScript animation is impossible. CSS animations *inside* an SVG
loaded through `<img>` do still run, which is the only animation hook
available. `anim2svg.py` turns each frame into a `<g>` that is opaque for one
slice of the cycle and transparent for the rest, staggered by
`animation-delay`.

`main` holds only `README.md` and the blog workflow, so `dist/bio.svg` is
served from this branch:

    https://raw.githubusercontent.com/4rknova/4rknova/source/dist/bio.svg

This branch must stay pushed for the image to resolve. GitHub proxies external
images through its camo cache, so changes to `bio.svg` can take a while to
appear on the profile.

## Editing the animation

Edit `bio.conf` and run `make`. It is the only input; everything in `dist/`
is generated and is overwritten on every build.

`@` directives sit above the `---` separator, the caption block below it:

    @frames    24        frames in one loop
    @duration  4.0       seconds per loop
    @phase     1.1       starting angle, radians
    @cols      40        torus viewport width
    @rows      18        torus viewport height
    @fill      0.92      how much of the viewport the torus fills
    @caption   right     'left' or 'right' of the torus, or 'below' it
    @border    off       'on' draws an ASCII frame around everything
    @header              plain line above the art; blank for none
    @title     ...       accessible label on the SVG
    @fontsize  14        px, in the rendered SVG
    @color      #636c76  glyph colour on a light background
    @color_dark #7d8590  glyph colour on a dark background

A value may carry a trailing ` #` comment. The space matters, so that
`#rrggbb` colours are not mistaken for one.

Blank lines in the info block are significant and become blank rows.
Non-ASCII is rejected, with the offending line reported; with
`@caption below` an over-wide line is rejected too, whereas `left` and
`right` widen to fit. `@phase` only shifts where the loop starts: at zero the torus is
face-on and reads as a blob.

The projection scale is fitted to the viewport across every frame, so `@cols`
and `@rows` can be any aspect without the torus clipping or pulsing. `@fill`
trades margin for size.

## Light and dark

The SVG carries a `prefers-color-scheme` media query, so the glyph colour
switches between `@color` and `@color_dark`. That query resolves against the
viewer's **browser or OS** setting, not against GitHub's own theme menu. A
reader whose system is light but who has set GitHub to dark gets the light
value on a dark page.

The two colours are therefore chosen to stay legible in all four
combinations, not just the matching two: contrast is at least 5.0:1 when the
settings agree and never drops below 3.5:1 when they disagree. Picking a
higher-contrast pair would look better matched and worse mismatched.

Making this track GitHub's menu exactly would mean shipping two SVGs behind a
`<picture>` element with `media="(prefers-color-scheme: dark)"` sources, which
is GitHub's documented mechanism.

## The blog list

The scheduled workflow on `main` rewrites the region between the
`BLOG-POST-LIST` markers. `build_readme.py` reads that region back out of
`main` and splices it into the template, so rebuilding never reverts what the
workflow last committed. It deliberately does not re-fetch the feed itself,
which would race the workflow.
