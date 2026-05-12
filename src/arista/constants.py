# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — constants                                              ║
# ║  « single source of truth for colours, paths, figure rules »     ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Central configuration for the arista package.                   ║
# ║                                                                  ║
# ║  Holds the Wong (2011) colourblind-safe palette with semantic    ║
# ║  mappings to HC / CC / WC cell types, the canonical stimulus     ║
# ║  protocol dictionary, the canonical strain list with synonym     ║
# ║  normalisation, and the save_figure helper that produces         ║
# ║  SVG + PNG + CSV triples for every plot.                         ║
# ║                                                                  ║
# ║  Import this module instead of hardcoding any of the above.      ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Constants, palettes, and shared paths for the arista package.

Populated in sprint 1; currently a stub holding only the package-data
fixture path so the test suite can resolve the shipped demo data
without depending on ``importlib.resources`` boilerplate elsewhere.
"""

from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────────────────────────
#  Shipped fixture paths
# ─────────────────────────────────────────────────────────────────

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PACKAGE_ROOT.parents[1]
DATA_DIR: Path = REPO_ROOT / "data"
FIJI_FIXTURE_DIR: Path = DATA_DIR / "fiji"
SENSOR_FIXTURE_DIR: Path = DATA_DIR / "sensor"
PREPROCESSED_FIXTURE_DIR: Path = DATA_DIR / "preprocessed"
