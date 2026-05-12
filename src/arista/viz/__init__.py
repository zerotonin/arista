# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — viz                                                    ║
# ║  « publication figure builders for the NompC story »             ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  One module per figure family. Wong palette, raincloud over      ║
# ║  bar, save_figure produces SVG + PNG + CSV triple output.        ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Publication figure builders. Sprint 8."""

from __future__ import annotations

from arista.viz.recording_overview import (
    SessionOverview,
    plot_session_overview,
)

__all__ = [
    "plot_session_overview",
    "SessionOverview",
]
