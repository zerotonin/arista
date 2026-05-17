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
from arista.processing.gain import (
    RecordingGain,
    compute_gains_table,
    compute_recording_gain,
)
from arista.processing.orchestrator import ProcessingStats, process_all
from arista.processing.sigmoid import (
    SigmoidFit,
    fit_sigmoid,
    fit_sigmoids_by_group,
    four_pl,
)
from arista.processing.stimulus_response import (
    StimulusResponseRow,
    compute_stimulus_responses,
)

__all__ = [
    "AdaptationFit",
    "ProcessingStats",
    "RecordingGain",
    "SigmoidFit",
    "StimulusResponseRow",
    "compute_gains_table",
    "compute_recording_gain",
    "compute_stimulus_responses",
    "fit_adaptation",
    "fit_sigmoid",
    "fit_sigmoids_by_group",
    "four_pl",
    "process_all",
]
