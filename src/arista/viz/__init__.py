# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — viz                                                    ║
# ║  « publication figure builders for the NompC story »             ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  One module per figure family. Wong palette, raincloud over      ║
# ║  bar, save_figure produces SVG + PNG + CSV triple output.        ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Publication figure builders. Sprint 8."""

from __future__ import annotations

from arista.viz.gain_comparison import (
    GainComparison,
    fetch_recording_gains,
    plot_gain_comparison,
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
]
