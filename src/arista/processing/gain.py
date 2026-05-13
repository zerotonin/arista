# ─────────────────────────────────────────────────────────────────
#  arista.processing.gain
#  « per-recording linear gain across stimulus steps (Kossen Fig 27) »
# ─────────────────────────────────────────────────────────────────
"""Linear-fit gain per recording across the stimulus-response steps.

Reproduces Kossen 2019 Fig 27: for each recording, fit a line through
all (``delta_target_c``, ``dfbf_response_median``) points and use the
slope as the cell's ΔF/F-per-°C gain. CC cells produce negative slope
(cold → high response), HC cells produce positive slope; the absolute
value is comparable across cell types.

Gains are computed on demand from the ``stimulus_responses`` table —
not persisted alongside ``adaptation_fits`` because each fit is two
``np.polyfit`` calls and the full corpus completes in well under a
second. Persisting would add schema surface and a migration without
saving any meaningful time at figure-render time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RecordingGain:
    """One linear-gain fit for a single recording."""

    slope: float
    intercept: float
    r_squared: float
    n_points: int


def compute_recording_gain(steps_df: pd.DataFrame) -> RecordingGain:
    """Linear fit slope of ΔF/F vs Δ target temperature.

    Args:
        steps_df: One recording's rows from ``stimulus_responses``,
            with ``delta_target_c`` and ``dfbf_response_median`` columns.

    Returns:
        :class:`RecordingGain`. ``slope`` and ``r_squared`` are NaN
        when fewer than 2 finite points are available or when every
        x-value is identical (no spread to fit through).
    """
    x = steps_df["delta_target_c"].to_numpy(dtype=float)
    y = steps_df["dfbf_response_median"].to_numpy(dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    n = int(len(x))
    if n < 2 or np.allclose(x, x[0]):
        return RecordingGain(
            slope=float("nan"),
            intercept=float("nan"),
            r_squared=float("nan"),
            n_points=n,
        )

    slope, intercept = np.polyfit(x, y, deg=1)
    y_pred = slope * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return RecordingGain(
        slope=float(slope),
        intercept=float(intercept),
        r_squared=float(r_squared),
        n_points=n,
    )


def compute_gains_table(
    response_df: pd.DataFrame,
    *,
    min_steps: int = 3,
    group_keys: tuple[str, ...] = (
        "recording_id", "strain_name", "cell_type", "hemisphere",
    ),
) -> pd.DataFrame:
    """Per-recording gains across an already-fetched response frame.

    Args:
        response_df: Output of
            :func:`arista.viz.response_curves.fetch_response_data` —
            one row per (recording, step) with all v_recordings
            metadata joined in.
        min_steps: Drop recordings with fewer than this many valid
            steps (default 3 — needed for a meaningful linear fit).
        group_keys: Columns that uniquely identify one recording's
            row group. Must include ``recording_id``.

    Returns:
        DataFrame with one row per recording carrying the group keys
        plus ``slope``, ``intercept``, ``r_squared``, ``n_points``.
    """
    if response_df.empty:
        return pd.DataFrame(columns=[
            *group_keys, "slope", "intercept", "r_squared", "n_points",
        ])
    rows: list[dict] = []
    for keys, group in response_df.groupby(list(group_keys), dropna=False):
        fit = compute_recording_gain(group)
        if fit.n_points < min_steps:
            continue
        key_dict = dict(zip(group_keys, keys, strict=True))
        rows.append({
            **key_dict,
            "slope": fit.slope,
            "intercept": fit.intercept,
            "r_squared": fit.r_squared,
            "n_points": fit.n_points,
        })
    return pd.DataFrame(rows)
