# Minimal Sphinx makefile for local doc builds.
# CI uses the equivalent commands directly (see .github/workflows/docs.yml).

SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html clean

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)"

html:
	$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"

clean:
	rm -rf "$(BUILDDIR)"
