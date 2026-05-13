# ─────────────────────────────────────────────────────────────────
#  Tests for arista.processing.adaptation
# ─────────────────────────────────────────────────────────────────
"""Exponential decay fit for HotAdapt / ColdAdapt recordings."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from arista.processing.adaptation import AdaptationFit, fit_adaptation


def _synthetic_adaptation_samples(
    *,
    tau_s: float,
    amplitude: float = 0.3,
    asymptote: float = 0.05,
    duration_s: float = 300.0,
    fps: float = 10.0,
    noise_sd: float = 0.001,
) -> pd.DataFrame:
    """Build a recording that decays as ``amplitude·exp(-t/tau)+asymptote`` from t=75 s."""
    rng = np.random.default_rng(0)
    n = int(duration_s * fps)
    time_s = np.arange(n) / fps
    dfbf = np.zeros(n)
    # Pre-stimulus baseline (frames before 75 s) = small noise around 0
    pre_mask = time_s < 75.0
    dfbf[pre_mask] = rng.normal(0, noise_sd, size=pre_mask.sum())
    # Post-onset decay
    post_mask = ~pre_mask
    t_post = time_s[post_mask] - 75.0
    dfbf[post_mask] = (
        amplitude * np.exp(-t_post / tau_s)
        + asymptote
        + rng.normal(0, noise_sd, size=post_mask.sum())
    )
    return pd.DataFrame({
        "frame": np.arange(n),
        "time_s": time_s,
        "sensor_t_c": np.full(n, 22.0),
        "target_t_c": np.where(pre_mask, 22.0, 26.0),
        "drive_t_c": np.full(n, 18.0),
        "dfbf": dfbf,
        "dfbf_drift_corrected": dfbf,
    })


# ─────────────────────────────────────────────────────────────────
#  Happy path
# ─────────────────────────────────────────────────────────────────

def test_recovers_known_tau() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    fit = fit_adaptation(samples)
    assert fit is not None
    assert fit.tau_s == pytest.approx(60.0, rel=0.05)


def test_recovers_amplitude_and_asymptote() -> None:
    samples = _synthetic_adaptation_samples(tau_s=120.0, amplitude=0.4, asymptote=0.1)
    fit = fit_adaptation(samples)
    assert fit is not None
    assert fit.amplitude == pytest.approx(0.4, abs=0.02)
    assert fit.asymptote == pytest.approx(0.1, abs=0.02)


def test_r_squared_is_high_on_clean_data() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    fit = fit_adaptation(samples)
    assert fit is not None
    assert fit.r_squared > 0.99


def test_fit_window_metadata_is_populated() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    fit = fit_adaptation(samples)
    assert fit is not None
    assert fit.fit_window_start_s == 75.0
    assert fit.fit_window_end_s == pytest.approx(300.0 - 0.1, abs=0.1)
    assert fit.n_points > 1000


# ─────────────────────────────────────────────────────────────────
#  Custom windows
# ─────────────────────────────────────────────────────────────────

def test_custom_fit_window_used() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    fit = fit_adaptation(samples, fit_start_s=100.0, fit_end_s=200.0)
    assert fit is not None
    assert fit.fit_window_start_s == 100.0
    assert fit.fit_window_end_s == 200.0


def test_min_points_threshold_returns_none() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0, duration_s=80.0)
    # Fit window 75-80 s × 10 fps ≈ 50 points; require 100 → reject
    fit = fit_adaptation(samples, fit_start_s=75.0, fit_end_s=80.0, min_points=100)
    assert fit is None


# ─────────────────────────────────────────────────────────────────
#  Failure modes
# ─────────────────────────────────────────────────────────────────

def test_flat_data_does_not_crash() -> None:
    """A perfectly flat trace is degenerate — amplitude → 0 and τ is
    meaningless. The fitter is allowed to either return None or to
    return an AdaptationFit with amplitude near zero; the only hard
    requirement is that we don't raise.
    """
    n = 3000
    samples = pd.DataFrame({
        "frame": np.arange(n),
        "time_s": np.arange(n) / 10.0,
        "sensor_t_c": np.full(n, 22.0),
        "target_t_c": np.full(n, 22.0),
        "drive_t_c": np.full(n, 18.0),
        "dfbf": np.full(n, 0.05),
        "dfbf_drift_corrected": np.full(n, 0.05),
    })
    fit = fit_adaptation(samples)
    if fit is not None:
        # Trivial fit: amplitude ~ 0 means the "exponential" is just the
        # constant asymptote. Acceptable; downstream callers filter on
        # |amplitude| or n_points to drop these.
        assert abs(fit.amplitude) < 1e-3 or fit.r_squared < 0.5


def test_falls_back_to_dfbf_when_drift_corrected_all_nan() -> None:
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    samples["dfbf_drift_corrected"] = np.nan
    fit = fit_adaptation(samples)
    assert fit is not None
    assert fit.tau_s == pytest.approx(60.0, rel=0.05)


def test_empty_samples_returns_none() -> None:
    empty = pd.DataFrame({
        "frame": [], "time_s": [], "sensor_t_c": [],
        "target_t_c": [], "drive_t_c": [], "dfbf": [],
        "dfbf_drift_corrected": [],
    })
    assert fit_adaptation(empty) is None


# ─────────────────────────────────────────────────────────────────
#  Dataclass shape
# ─────────────────────────────────────────────────────────────────

def test_fit_dataclass_is_frozen() -> None:
    import dataclasses
    samples = _synthetic_adaptation_samples(tau_s=60.0)
    fit = fit_adaptation(samples)
    assert isinstance(fit, AdaptationFit)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fit.tau_s = 999.0  # type: ignore[misc]
