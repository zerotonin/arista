# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — package                                                ║
# ║  « Drosophila arista Ca²⁺-imaging corpus + analysis »            ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Public API surface for the arista package.                      ║
# ║                                                                  ║
# ║  Three CLIs ship with this package:                              ║
# ║    arista-preprocess  reproduce the pytci preprocessing stages   ║
# ║                       on raw Fiji + MATLAB sensor data           ║
# ║    arista-ingest      load preprocessed CSVs into SQLite         ║
# ║    arista-figs        rebuild publication figures from the DB    ║
# ║                                                                  ║
# ║  Docs: https://zerotonin.github.io/arista                        ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Drosophila arista calcium-imaging corpus and analysis package."""

from __future__ import annotations

try:
    from arista._version import version as __version__
except ImportError:  # editable install before setuptools-scm has run
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
