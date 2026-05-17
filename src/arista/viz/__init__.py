# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — viz                                                    ║
# ║  « publication figure builders for the NompC story »             ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  One module per figure family. Wong palette, raincloud over      ║
# ║  bar, save_figure produces SVG + PNG + CSV triple output.        ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Publication figure builders. Sprint 8."""

from __future__ import annotations

from arista.viz.adaptation_taus import (
    AdaptationTaus,
    discover_adaptation_stimuli,
    fetch_adaptation_taus,
    plot_adaptation_taus,
)
from arista.viz.gain_comparison import (
    GainComparison,
    fetch_recording_gains,
    plot_gain_comparison,
)
from arista.viz.nompc_dosage import (
    DEFAULT_DOSAGE_STIMULI,
    NompCDosage,
    fetch_dosage_gains,
    plot_nompc_dosage,
)
from arista.viz.recording_overview import (
    SessionOverview,
    plot_session_overview,
)
from arista.viz.response_curves import (
    ResponseCurves,
    aggregate_response_data,
    fetch_response_data,
    plot_response_curves,
)
from arista.viz.sigmoid_fits import (
    SigmoidFits,
    plot_sigmoid_fits,
)

__all__ = [
    # session overview
    "plot_session_overview",
    "SessionOverview",
    # response curves (Kossen Fig 19 / 22-23)
    "plot_response_curves",
    "ResponseCurves",
    "fetch_response_data",
    "aggregate_response_data",
    # gain comparison (Kossen Fig 27)
    "plot_gain_comparison",
    "GainComparison",
    "fetch_recording_gains",
    # sigmoid fits (Kossen Fig 24 / 25)
    "plot_sigmoid_fits",
    "SigmoidFits",
    # adaptation taus (Kossen Fig 21)
    "plot_adaptation_taus",
    "AdaptationTaus",
    "fetch_adaptation_taus",
    "discover_adaptation_stimuli",
    # NompC dosage headline
    "plot_nompc_dosage",
    "NompCDosage",
    "fetch_dosage_gains",
    "DEFAULT_DOSAGE_STIMULI",
]
