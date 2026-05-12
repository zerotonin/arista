# ─────────────────────────────────────────────────────────────────
#  Tests for arista.preprocess.drift
# ─────────────────────────────────────────────────────────────────
"""Drift fitting + AIC chooser behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from arista.preprocess.drift import (
    DriftFit,
    apply_drift,
    correct_drift,
    fit_all,
    fit_exponential,
    fit_linear,
    fit_polynomial,
    pick_best,
)
from arista.preprocess.io import Recording


def _toy_recording(drift_shape: str = "linear", n: int = 500) -> Recording:
    """Synthetic recording with a known drift shape plus small noise."""
    rng = np.random.default_rng(42)
    t = np.linspace(0.0, 60.0, n)
    noise = rng.normal(0, 0.005, n)
    if drift_shape == "linear":
        drift = 0.01 * t + 0.05
    elif drift_shape == "poly":
        drift = 0.0005 * (t - 30.0) ** 2 + 0.05
    elif drift_shape == "exp":
        drift = 0.5 * np.exp(-0.05 * t) + 0.1
    else:
        drift = np.zeros(n)
    return Recording(
        frame=np.arange(n),
        time_s=t,
        sensor_t_c=np.full(n, 22.0),
        target_t_c=np.full(n, 22.0),
        drive_t_c=np.full(n, 18.0),
        dfbf=drift + noise,
    )


# ─────────────────────────────────────────────────────────────────
#  Per-method fits
# ─────────────────────────────────────────────────────────────────

def test_fit_linear_recovers_known_slope() -> None:
    n = 1000
    t = np.linspace(0.0, 100.0, n)
    y = 0.02 * t + 0.5
    fit = fit_linear(t, y)
    assert fit.method == "linear"
    assert fit.fitted.shape == y.shape
    assert abs(fit.params["slope"] - 0.02) < 1e-6
    assert abs(fit.params["intercept"] - 0.5) < 1e-6
    assert fit.residual_ssq < 1e-12


def test_fit_polynomial_returns_requested_degree() -> None:
    n = 200
    t = np.linspace(0.0, 10.0, n)
    y = 0.001 * t**3 + 0.01 * t**2 + 0.1 * t
    fit = fit_polynomial(t, y, degree=4)
    assert fit.method == "poly"
    assert fit.params["degree"] == 4
    assert len(fit.params["coefs"]) == 5  # deg+1


def test_fit_exponential_recovers_known_decay() -> None:
    n = 500
    t = np.linspace(0.0, 100.0, n)
    y = 2.0 * np.exp(-0.05 * t) + 0.5
    fit = fit_exponential(t, y)
    assert fit.method == "exp"
    assert abs(fit.params["a"] - 2.0) < 0.05
    assert abs(fit.params["b"] - 0.05) < 0.01
    assert abs(fit.params["c"] - 0.5) < 0.05


# ─────────────────────────────────────────────────────────────────
#  AIC chooser
# ─────────────────────────────────────────────────────────────────

def test_fit_all_returns_three_methods_on_typical_data() -> None:
    rec = _toy_recording("poly", n=500)
    fits = fit_all(rec.time_s, rec.dfbf)
    assert set(fits) >= {"linear", "poly"}  # exp may or may not converge


def test_auto_picks_lowest_aic() -> None:
    rec = _toy_recording("poly", n=500)
    fits = fit_all(rec.time_s, rec.dfbf)
    chosen = pick_best(fits, method="auto")
    expected = min(fits.values(), key=lambda f: f.aic)
    assert chosen is expected


def test_auto_prefers_poly_on_curved_drift() -> None:
    """With a clear quadratic drift, AIC should favour poly over linear."""
    rec = _toy_recording("poly", n=1000)
    fits = fit_all(rec.time_s, rec.dfbf)
    chosen = pick_best(fits, method="auto")
    assert chosen.method == "poly"


def test_auto_prefers_linear_on_pure_linear_drift() -> None:
    rec = _toy_recording("linear", n=1000)
    fits = fit_all(rec.time_s, rec.dfbf)
    chosen = pick_best(fits, method="auto")
    assert chosen.method == "linear"


def test_force_method_returns_that_fit() -> None:
    rec = _toy_recording("poly", n=300)
    fits = fit_all(rec.time_s, rec.dfbf)
    assert pick_best(fits, method="linear").method == "linear"
    assert pick_best(fits, method="poly").method == "poly"


def test_pick_best_none_returns_none() -> None:
    rec = _toy_recording("linear", n=200)
    fits = fit_all(rec.time_s, rec.dfbf)
    assert pick_best(fits, method="none") is None


def test_pick_best_rejects_unknown_method() -> None:
    rec = _toy_recording("linear", n=200)
    fits = fit_all(rec.time_s, rec.dfbf)
    with pytest.raises(ValueError, match="Unknown drift method"):
        pick_best(fits, method="magic")  # type: ignore[arg-type]


def test_pick_best_rejects_missing_forced_method() -> None:
    """Forcing exp when fit_exponential failed should raise, not fall back."""
    fits = {"linear": fit_linear(np.linspace(0, 1, 10), np.zeros(10))}
    with pytest.raises(ValueError, match="exp.* unavailable"):
        pick_best(fits, method="exp")


# ─────────────────────────────────────────────────────────────────
#  apply_drift + correct_drift
# ─────────────────────────────────────────────────────────────────

def test_apply_drift_subtracts_fit() -> None:
    rec = _toy_recording("linear", n=500)
    fit = fit_linear(rec.time_s, rec.dfbf)
    corrected = apply_drift(rec, fit)
    assert corrected.drift_method == "linear"
    assert corrected.dfbf_drift_corrected is not None
    # Corrected trace should be approximately zero-mean (drift removed)
    assert abs(corrected.dfbf_drift_corrected.mean()) < 0.005
    # Raw dfbf untouched
    np.testing.assert_array_equal(corrected.dfbf, rec.dfbf)


def test_apply_drift_none_marks_method_none() -> None:
    rec = _toy_recording("linear", n=100)
    out = apply_drift(rec, None)
    assert out.drift_method == "none"
    assert out.dfbf_drift_corrected is None


def test_correct_drift_end_to_end() -> None:
    rec = _toy_recording("exp", n=500)
    corrected = correct_drift(rec, method="auto")
    assert corrected.drift_method in {"linear", "poly", "exp"}
    assert corrected.dfbf_drift_corrected is not None
    assert corrected.n_frames == rec.n_frames


def test_correct_drift_none_returns_uncorrected() -> None:
    rec = _toy_recording("linear", n=100)
    out = correct_drift(rec, method="none")
    assert out.drift_method == "none"
    assert out.dfbf_drift_corrected is None
