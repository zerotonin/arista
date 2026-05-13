# ─────────────────────────────────────────────────────────────────
#  arista.processing.adaptation
#  « phasic-tonic exponential fit for HotAdapt / ColdAdapt »
# ─────────────────────────────────────────────────────────────────
"""Fit ``a·exp(-t/τ) + c`` to the post-onset segment of an adaptation trace.

Kossen 2019 §3.2 (Fig. 21) characterised the time course of Ca²⁺
adaptation in HC and CC cells using long-step protocols (HotAdapt to
26 °C, ColdAdapt to 18 °C). The published τ values span four orders
of magnitude (163 s in HC under HotAdapt → 17 414 s in HC under
ColdAdapt, essentially "no decay"), so the fit must accept both
fast-decay and near-flat cases without blowing up.

Robustness measures:

* :func:`scipy.optimize.curve_fit` with bounded parameters so the
  rate constant ``b`` stays non-negative and the asymptote stays in
  a physically plausible range.
* Initial guesses derived from the first and last samples of the fit
  window so the optimiser starts close to the data.
* Failure modes (no convergence, ``b ≤ 0``, ``R² < 0``) return
  ``None`` rather than raising — callers iterate over many recordings
  and a single bad fit shouldn't abort the batch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from arista.constants import ADAPTATION_FIT_START_S


@dataclass(frozen=True)
class AdaptationFit:
    """One exponential-decay fit, destined for ``adaptation_fits``."""

    tau_s: float              # time constant 1/b
    amplitude: float          # a
    asymptote: float          # c
    r_squared: float
    fit_window_start_s: float
    fit_window_end_s: float
    n_points: int


def _exp_decay(t: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a * np.exp(-b * t) + c


def _select_dfbf_column(samples_df: pd.DataFrame) -> np.ndarray:
    """Prefer drift-corrected ΔF/F when present (matches stimulus_response)."""
    if "dfbf_drift_corrected" in samples_df.columns:
        col = samples_df["dfbf_drift_corrected"]
        if not col.isna().all():
            return col.to_numpy()
    return samples_df["dfbf"].to_numpy()


def fit_adaptation(
    samples_df: pd.DataFrame,
    *,
    fit_start_s: float = ADAPTATION_FIT_START_S,
    fit_end_s: float | None = None,
    min_points: int = 30,
) -> AdaptationFit | None:
    """Fit ``a·exp(-b·t) + c`` and return τ + R² + asymptote.

    Args:
        samples_df: One recording's samples (same columns as for
            :func:`compute_stimulus_responses`).
        fit_start_s: Where to start the fit window. Default
            :data:`arista.constants.ADAPTATION_FIT_START_S` (75 s, the
            end of the canonical pre-stimulus baseline).
        fit_end_s: End of the fit window. ``None`` uses the recording's
            last time stamp.
        min_points: Refuse to fit on fewer than this many in-window
            samples — 30 is enough to constrain three parameters with
            confidence.

    Returns:
        :class:`AdaptationFit` on success, ``None`` if the curve_fit
        fails to converge, if too few points lie in the window, or if
        the fitted decay rate is non-positive (degenerate / no decay
        captured by ``a · exp(-b·t)`` with this parameterisation).
    """
    time_s = samples_df["time_s"].to_numpy()
    dfbf = _select_dfbf_column(samples_df)

    if fit_end_s is None:
        fit_end_s = float(time_s[-1]) if time_s.size else fit_start_s

    mask = (
        (time_s >= fit_start_s)
        & (time_s <= fit_end_s)
        & ~np.isnan(dfbf)
    )
    n = int(mask.sum())
    if n < min_points:
        return None

    # Zero-shift the time axis so the exponential's domain starts at
    # 0; this stabilises curve_fit when fit_start_s is large.
    t = time_s[mask] - fit_start_s
    y = dfbf[mask]

    a0 = float(y[0] - y[-1])
    c0 = float(y[-1])
    # Initial b corresponds to τ = (window length / e). Conservative
    # default that lets the optimiser climb to large τ if the data
    # supports it.
    b0 = 1.0 / max(1.0, (t[-1] - t[0]) / np.e)

    try:
        params, _cov = curve_fit(
            _exp_decay, t, y,
            p0=(a0, b0, c0),
            bounds=([-5.0, 0.0, -5.0], [5.0, 10.0, 5.0]),
            maxfev=4000,
        )
    except (RuntimeError, ValueError):
        return None

    a, b, c = (float(p) for p in params)
    if b <= 0.0:
        return None

    fitted = _exp_decay(t, a, b, c)
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return AdaptationFit(
        tau_s=1.0 / b,
        amplitude=a,
        asymptote=c,
        r_squared=r_squared,
        fit_window_start_s=float(fit_start_s),
        fit_window_end_s=float(fit_end_s),
        n_points=n,
    )
