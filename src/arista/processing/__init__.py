# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — processing                                             ║
# ║  « post-ingest computation on DB samples »                       ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Stimulus-response medians and adaptation τ fits, computed      ║
# ║  unconditionally on every recording (CLAUDE.md § 11.2).          ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Post-ingest computation on samples already in the DB. Sprint 7."""

from __future__ import annotations
