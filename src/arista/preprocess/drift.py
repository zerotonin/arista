# ─────────────────────────────────────────────────────────────────
#  arista.preprocess.drift  « stages D / E / F »
# ─────────────────────────────────────────────────────────────────
"""Drift-correction fits and chooser.

Replaces ``_legacy/pytci/tciAnalysis.py`` with pure functions returning
:class:`DriftFit` dataclasses. The default chooser is **AIC**-based
(no GUI prompt). The interactive matplotlib chooser from the legacy
pipeline is intentionally NOT ported into this module — it belongs in
the CLI layer (Phase 3, ``arista-preprocess drift --method interactive``)
where stdout/stdin handling is appropriate.

Three candidate fits are computed, identical in form to pytci:

* ``linear`` — degree-1 polyfit on pre+post-stimulus tails only
* ``poly`` — degree-4 polyfit over the whole trace
* ``exp`` — ``a·exp(-b·t) + c`` via ``scipy.optimize.curve_fit``

AIC scoring uses the standard Gaussian-residuals formula and the
``params`` dict on each fit makes the model auditable downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from scipy.optimize import curve_fit

from arista.preprocess.io import Recording

DriftMethod = Literal["linear", "poly", "exp", "none", "auto"]

# Number of frames used at the start and end of the trace to fit the
# linear drift. Matches the 300-frame window used in pytci's fitLinear.
_LINEAR_TAIL_FRAMES: int = 300

# Polynomial degree of the global poly fit (matches pytci's fitLowPoly).
_POLY_DEGREE: int = 4

# Exponential fit bounds: a in [0, 4], b in [0, 0.1], c in [0, 4].
# Matches pytci defaults; loose enough to accept most real traces.
_EXP_BOUNDS: tuple[list[float], list[float]] = ([0.0, 0.0, 0.0], [4.0, 0.1, 4.0])
_EXP_P0: list[float] = [1.0, 1e-3, 1.0]


# ─────────────────────────────────────────────────────────────────
#  Dataclass
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DriftFit:
    """A fitted drift model plus its evaluation on the full trace."""

    method: Literal["linear", "poly", "exp"]
    fitted: np.ndarray          # evaluation of the fit on the full time axis
    residual_ssq: float         # sum of squared residuals
    aic: float                  # Akaike Information Criterion (lower = better)
    params: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────


def _exp_model(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a * np.exp(-b * x) + c


def _aic(residuals: np.ndarray, n_params: int) -> float:
    """Akaike Information Criterion under Gaussian-residual assumption."""
    n = residuals.size
    ssq = float(np.sum(residuals ** 2))
    if n == 0 or ssq <= 0.0:
        return float("inf")
    # AIC = n·ln(SSR/n) + 2k under MLE on Gaussian residuals.
    return n * np.log(ssq / n) + 2 * n_params


# ─────────────────────────────────────────────────────────────────
#  Per-method fits
# ─────────────────────────────────────────────────────────────────


def fit_linear(t: np.ndarray, y: np.ndarray) -> DriftFit:
    """Degree-1 polyfit on the first and last ``_LINEAR_TAIL_FRAMES`` frames.

    Matches pytci's ``fitLinear``: the fit is *trained* on pre + post
    stimulus tails only, then *evaluated* over the whole trace. This
    deliberately ignores the stimulus-evoked excursions so the linear
    component captures photobleach drift rather than the response.
    """
    n_tail = min(_LINEAR_TAIL_FRAMES, max(t.size // 4, 1))
    x_train = np.concatenate([t[:n_tail], t[-n_tail:]])
    y_train = np.concatenate([y[:n_tail], y[-n_tail:]])
    coefs = np.polyfit(x_train, y_train, deg=1)
    fitted = np.polyval(coefs, t)
    residuals = y - fitted
    return DriftFit(
        method="linear",
        fitted=fitted,
        residual_ssq=float(np.sum(residuals ** 2)),
        aic=_aic(residuals, n_params=2),
        params={"slope": float(coefs[0]), "intercept": float(coefs[1])},
    )


def fit_polynomial(t: np.ndarray, y: np.ndarray, degree: int = _POLY_DEGREE) -> DriftFit:
    """Degree-``degree`` polyfit over the whole trace (default 4, pytci default)."""
    coefs = np.polyfit(t, y, deg=degree)
    fitted = np.polyval(coefs, t)
    residuals = y - fitted
    return DriftFit(
        method="poly",
        fitted=fitted,
        residual_ssq=float(np.sum(residuals ** 2)),
        aic=_aic(residuals, n_params=degree + 1),
        params={"coefs": list(map(float, coefs)), "degree": degree},
    )


def fit_exponential(t: np.ndarray, y: np.ndarray) -> DriftFit:
    """``a·exp(-b·t) + c`` fit. Mirrors pytci's ``fitExp`` bounds + p0."""
    parms, _cov = curve_fit(
        _exp_model,
        t,
        y,
        p0=_EXP_P0,
        bounds=_EXP_BOUNDS,
        maxfev=1000,
    )
    fitted = _exp_model(t, *parms)
    residuals = y - fitted
    return DriftFit(
        method="exp",
        fitted=fitted,
        residual_ssq=float(np.sum(residuals ** 2)),
        aic=_aic(residuals, n_params=3),
        params={"a": float(parms[0]), "b": float(parms[1]), "c": float(parms[2])},
    )


def fit_all(t: np.ndarray, y: np.ndarray) -> dict[str, DriftFit]:
    """Compute linear, poly and exp fits; return them in a dict by method name.

    The exponential fit may fail to converge on flat traces; in that
    case it is omitted from the returned dict (rather than raising) so
    the AIC chooser can still pick between linear and poly.
    """
    fits: dict[str, DriftFit] = {
        "linear": fit_linear(t, y),
        "poly": fit_polynomial(t, y),
    }
    try:
        fits["exp"] = fit_exponential(t, y)
    except (RuntimeError, ValueError):
        pass  # fit_exponential can fail on degenerate inputs; that's fine
    return fits


# ─────────────────────────────────────────────────────────────────
#  Chooser
# ─────────────────────────────────────────────────────────────────


def pick_best(
    fits: dict[str, DriftFit],
    method: DriftMethod = "auto",
) -> DriftFit | None:
    """Select one fit from a :func:`fit_all` result.

    Args:
        fits: Mapping ``method_name → DriftFit`` as returned by
            :func:`fit_all`.
        method: Either ``"auto"`` (pick lowest AIC), or one of
            ``"linear"`` / ``"poly"`` / ``"exp"`` to force that fit,
            or ``"none"`` to apply no correction.

    Returns:
        The chosen :class:`DriftFit`, or ``None`` if ``method == "none"``.

    Raises:
        ValueError: If ``method`` is not a valid choice, or if a forced
            method is requested but missing from ``fits``.
    """
    if method == "none":
        return None
    if method == "auto":
        if not fits:
            raise ValueError("No fits available to auto-pick from")
        return min(fits.values(), key=lambda f: f.aic)
    if method in ("linear", "poly", "exp"):
        if method not in fits:
            raise ValueError(
                f"Drift method {method!r} requested but its fit is unavailable; "
                f"got {sorted(fits)!r}"
            )
        return fits[method]
    raise ValueError(
        f"Unknown drift method {method!r}; expected one of "
        f"'auto', 'linear', 'poly', 'exp', 'none'"
    )


# ─────────────────────────────────────────────────────────────────
#  Apply
# ─────────────────────────────────────────────────────────────────


def apply_drift(recording: Recording, fit: DriftFit | None) -> Recording:
    """Subtract a fit from the ΔF/F trace and return a new :class:`Recording`.

    If ``fit`` is ``None`` the recording is returned with
    ``drift_method = "none"`` and ``dfbf_drift_corrected = None`` (i.e.
    drift correction explicitly *not* applied — the original ``dfbf``
    column remains the source of truth).

    Args:
        recording: An aligned :class:`Recording` from
            :func:`arista.preprocess.align.assemble_recording`.
        fit: The chosen :class:`DriftFit`, or ``None``.

    Returns:
        A new :class:`Recording` with ``dfbf_drift_corrected`` and
        ``drift_method`` filled in.
    """
    if fit is None:
        return Recording(
            frame=recording.frame,
            time_s=recording.time_s,
            sensor_t_c=recording.sensor_t_c,
            target_t_c=recording.target_t_c,
            drive_t_c=recording.drive_t_c,
            dfbf=recording.dfbf,
            dfbf_drift_corrected=None,
            drift_method="none",
            recording_date=recording.recording_date,
        )
    corrected = recording.dfbf - fit.fitted
    return Recording(
        frame=recording.frame,
        time_s=recording.time_s,
        sensor_t_c=recording.sensor_t_c,
        target_t_c=recording.target_t_c,
        drive_t_c=recording.drive_t_c,
        dfbf=recording.dfbf,
        dfbf_drift_corrected=corrected,
        drift_method=fit.method,
        recording_date=recording.recording_date,
    )


def correct_drift(
    recording: Recording,
    method: DriftMethod = "auto",
) -> Recording:
    """Convenience: fit all candidates, pick the best, apply it.

    For headless / batch / CI use. Matches the default behaviour
    ``arista-preprocess drift --method auto`` will expose at the CLI
    level in Phase 3.
    """
    if method == "none":
        return apply_drift(recording, None)
    fits = fit_all(recording.time_s, recording.dfbf)
    chosen = pick_best(fits, method=method)
    return apply_drift(recording, chosen)
