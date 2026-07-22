# Build the published profile README from source.
#
# This branch ('source') holds everything: the ASCII animation, the tools that
# compile it, and the README template. The published branch holds only the
# generated README.md and the workflow that keeps its blog list fresh.
#
#   make            build everything into dist/
#   make preview    render dist/README.md the way GitHub will show it
#   make check      validate geometry without writing anything
#   make publish    commit dist/README.md onto $(PUBLISH_BRANCH)
#   make clean      remove build artefacts

PY             ?= python3
PUBLISH_BRANCH ?= main

CONF  := bio.conf
ANIM  := dist/bio.anim
SVG   := dist/bio.svg
TMPL  := README.tmpl.md
BUILT := dist/README.md
WORKTREE := .publish

.PHONY: all anim svg readme preview check publish clean help

all: svg readme

help:
	@sed -n 's/^# \{0,1\}//p' $(MAKEFILE_LIST) | sed -n '1,12p'

# bio.conf is the only file to edit: it carries the frame count, loop
# duration, viewport size, header, and the caption block. The .anim and .svg
# below it are both generated, so editing either one is pointless.
$(ANIM): $(CONF) tools/gen_torus.py
	$(PY) tools/gen_torus.py $(CONF) -o $(ANIM)

anim: $(ANIM)

$(SVG): $(ANIM) tools/anim2svg.py
	$(PY) tools/anim2svg.py $(ANIM) -o $(SVG)

svg: $(SVG)

# Always rebuilt: it splices in the live blog list from the published branch,
# which changes without any file here changing.
readme: $(TMPL) tools/build_readme.py
	$(PY) tools/build_readme.py --branch $(PUBLISH_BRANCH) -o $(BUILT)

preview: readme
	$(PY) tools/preview.py $(BUILT)

check:
	$(PY) tools/anim2svg.py $(ANIM) --check
	$(PY) tools/preview.py $(BUILT) --check

# Publish via a throwaway worktree so the current checkout is never disturbed
# and no branch switch is needed. Committing nothing is not an error.
publish: all
	@git worktree remove --force $(WORKTREE) 2>/dev/null || true
	git worktree add --force $(WORKTREE) $(PUBLISH_BRANCH)
	cp $(BUILT) $(WORKTREE)/README.md
	cd $(WORKTREE) && git add README.md && \
	  (git diff --cached --quiet || git commit -m "Rebuild README from source")
	git worktree remove --force $(WORKTREE)
	@echo "committed to $(PUBLISH_BRANCH); push when ready"

clean:
	rm -rf dist preview.html
	@git worktree remove --force $(WORKTREE) 2>/dev/null || true
