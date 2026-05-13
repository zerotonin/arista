# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — processing                                             ║
# ║  « post-ingest computation on DB samples »                       ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Stimulus-response medians and adaptation τ fits, computed      ║
# ║  unconditionally on every recording (CLAUDE.md § 11.2).          ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Post-ingest computation on samples already in the DB."""

from __future__ import annotations

from arista.processing.adaptation import AdaptationFit, fit_adaptation
from arista.processing.orchestrator import ProcessingStats, process_all
from arista.processing.stimulus_response import (
    StimulusResponseRow,
    compute_stimulus_responses,
)

__all__ = [
    "AdaptationFit",
    "ProcessingStats",
    "StimulusResponseRow",
    "compute_stimulus_responses",
    "fit_adaptation",
    "process_all",
]
