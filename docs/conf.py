# ─────────────────────────────────────────────────────────────────
#  Sphinx configuration for the arista package
# ─────────────────────────────────────────────────────────────────
"""Sphinx config. Built by .github/workflows/docs.yml on every push to main."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# Make the package importable for autodoc when building from a clean checkout.
DOCS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCS_DIR.parent / "src"))

# -- Project information -----------------------------------------------------

project = "arista"
author = "Bart R. H. Geurten"
copyright = f"{datetime.now():%Y}, {author}"  # noqa: A001

try:
    from arista import __version__ as release
except ImportError:
    release = "0.0.0"
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",      # Google-style docstrings (CLAUDE.md § 4.2)
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",              # Markdown support for narrative pages
    "nbsphinx",                 # execute Jupyter notebooks at build time
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

# Napoleon — Google-style docstrings (CLAUDE.md § 4.2).
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

# autodoc
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"

# Mock heavy deps so docs build on cheap CI runners (CLAUDE.md § 8.5).
autodoc_mock_imports = [
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "click",
    "rich",
    "tqdm",
]

autosummary_generate = True

# nbsphinx — execute notebooks during build so docs always reflect runnable code.
nbsphinx_execute = "auto"
nbsphinx_allow_errors = False

# intersphinx
intersphinx_mapping = {
    "python":     ("https://docs.python.org/3",                 None),
    "numpy":      ("https://numpy.org/doc/stable/",             None),
    "pandas":     ("https://pandas.pydata.org/docs/",           None),
    "scipy":      ("https://docs.scipy.org/doc/scipy/",         None),
    "matplotlib": ("https://matplotlib.org/stable/",            None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_title = f"arista v{release}"
html_static_path = ["_static"]
html_show_sourcelink = True
html_show_copyright = True

# Do NOT use -W (warnings-as-errors) — CLAUDE.md § 8.5 flags it as too brittle.
