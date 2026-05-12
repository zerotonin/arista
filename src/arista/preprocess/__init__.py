# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — preprocess                                             ║
# ║  « headless rebuild of pytci stages A-I »                        ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Pure-function pipeline that takes raw Fiji ΔF/F exports plus    ║
# ║  MATLAB sensor MATs and produces drift-corrected, frame-aligned  ║
# ║  CSVs identical in maths to the legacy pytci package.            ║
# ║                                                                  ║
# ║  Stages A-I documented in [[Preprocessing Pipeline]]; see        ║
# ║  align.py, interpolate.py, drift.py, template_rescue.py.         ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Headless preprocessing pipeline. Contents filled in sprints 2-3."""

from __future__ import annotations
