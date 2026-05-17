# ─────────────────────────────────────────────────────────────────
#  arista.processing.sigmoid
#  « 4PL logistic fit per (strain × cell-type) — Kossen Fig 24/25 »
# ─────────────────────────────────────────────────────────────────
"""Four-parameter logistic (4PL) fit of ΔF/F vs Δ target temperature.

Reproduces Kossen 2019 Fig 24 / 25: for each (strain × cell-type)
group, pool every recording's per-step response and fit a sigmoid

    y = bottom + (top - bottom) / (1 + exp(-slope · (x - midpoint)))

CC cells produce a *descending* curve (more positive Δtarget → less
ΔF/F): the fit recovers this either via ``slope < 0`` or via
``bottom > top`` depending on the initial guess. Either parameterisation
describes the same curve, so we let ``scipy.optimize.curve_fit`` settle
on whichever the data prefers — no bounds.

Fits are computed on demand (one ``curve_fit`` per group, milliseconds)
rather than persisted alongside ``adaptation_fits``: the fit is a
pooled-group statistic, not a per-recording one, so it doesn't fit the
per-recording schema.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


@dataclass(frozen=True)
class SigmoidFit:
    """One 4PL sigmoid fit."""

    bottom: float
    top: float
    midpoint_c: float
    slope: float
    r_squared: float
    n_points: int


def four_pl(
    x: np.ndarray, bottom: float, top: float, midpoint: float, slope: float,
) -> np.ndarray:
    """Four-parameter logistic.

    ``bottom`` and ``top`` are the left/right asymptotes,
    ``midpoint`` is the x-value at the curve's inflection, and
    ``slope`` is the curve's slope at the midpoint (units: 1/°C).
    """
    return bottom + (top - bottom) / (1.0 + np.exp(-slope * (x - midpoint)))


def fit_sigmoid(
    deltas: np.ndarray | pd.Series,
    responses: np.ndarray | pd.Series,
    *,
    max_iterations: int = 5000,
) -> SigmoidFit | None:
    """Fit a 4PL to pooled ``(Δtarget, ΔF/F)`` points.

    Args:
        deltas: x-values (Δ target temperature in °C).
        responses: y-values (median ΔF/F per step).
        max_iterations: ``curve_fit`` ``maxfev`` ceiling.

    Returns:
        :class:`SigmoidFit` on convergence, ``None`` when the data is
        too sparse (<4 points), perfectly flat, or when ``curve_fit``
        raises.
    """
    x = np.asarray(deltas, dtype=float)
    y = np.asarray(responses, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    n = int(len(x))
    if n < 4:
        return None
    y_min = float(y.min())
    y_max = float(y.max())
    if y_max - y_min < 1e-12:
        return None

    # Direction of monotonicity → sign of slope0. Keep bottom0 < top0
    # always; flipping the slope sign alone makes the curve descend
    # (y(-∞) → top, y(+∞) → bottom). Flipping BOTH the asymptotes and
    # the sign is a no-op, which was an earlier bug.
    with np.errstate(invalid="ignore"):
        corr = float(np.corrcoef(x, y)[0, 1]) if len(np.unique(x)) > 1 else 0.0
    if not np.isfinite(corr):
        corr = 0.0
    slope0 = 1.0 if corr >= 0 else -1.0
    bottom0, top0 = y_min, y_max
    # Estimate the midpoint as the x where y is closest to (min + max) / 2.
    # Median-of-x is a poor guess for shifted sigmoids and lets curve_fit
    # converge to a wrong local minimum on monotone-but-not-centred data.
    y_mid_target = 0.5 * (y_min + y_max)
    midpoint0 = float(x[int(np.argmin(np.abs(y - y_mid_target)))])

    try:
        popt, _ = curve_fit(
            four_pl, x, y,
            p0=[bottom0, top0, midpoint0, slope0],
            maxfev=max_iterations,
        )
    except (RuntimeError, ValueError, OverflowError):
        return None

    y_pred = four_pl(x, *popt)
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return SigmoidFit(
        bottom=float(popt[0]),
        top=float(popt[1]),
        midpoint_c=float(popt[2]),
        slope=float(popt[3]),
        r_squared=float(r_squared),
        n_points=n,
    )


def fit_sigmoids_by_group(
    response_df: pd.DataFrame,
    *,
    group_keys: tuple[str, ...] = ("strain_name", "cell_type"),
    min_points: int = 4,
) -> pd.DataFrame:
    """Run :func:`fit_sigmoid` over each group in a response frame.

    Args:
        response_df: Output of
            :func:`arista.viz.response_curves.fetch_response_data`.
        group_keys: Columns to group by (default per strain × cell-type).
        min_points: Skip groups with fewer than this many finite points.

    Returns:
        DataFrame with one row per group carrying ``bottom``, ``top``,
        ``midpoint_c``, ``slope``, ``r_squared``, ``n_points`` plus
        the group key columns. Groups whose fit failed are omitted.
    """
    columns = [
        *group_keys,
        "bottom", "top", "midpoint_c", "slope", "r_squared", "n_points",
    ]
    if response_df.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for keys, group in response_df.groupby(list(group_keys), dropna=False):
        fit = fit_sigmoid(
            group["delta_target_c"],
            group["dfbf_response_median"],
        )
        if fit is None or fit.n_points < min_points:
            continue
        key_dict = (
            {group_keys[0]: keys}
            if not isinstance(keys, tuple)
            else dict(zip(group_keys, keys, strict=True))
        )
        rows.append({
            **key_dict,
            "bottom": fit.bottom,
            "top": fit.top,
            "midpoint_c": fit.midpoint_c,
            "slope": fit.slope,
            "r_squared": fit.r_squared,
            "n_points": fit.n_points,
        })
    return pd.DataFrame(rows, columns=columns)
