# ─────────────────────────────────────────────────────────────────
#  Tests for arista.processing.sigmoid
# ─────────────────────────────────────────────────────────────────
"""4PL logistic fit on pooled (Δtarget, ΔF/F) points."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from arista.processing.sigmoid import (
    SigmoidFit,
    fit_sigmoid,
    fit_sigmoids_by_group,
    four_pl,
)

# ─────────────────────────────────────────────────────────────────
#  Synthetic curves
# ─────────────────────────────────────────────────────────────────


def _generate_sigmoid(
    *,
    bottom: float,
    top: float,
    midpoint: float,
    slope: float,
    x_range: tuple[float, float] = (-5.0, 5.0),
    n: int = 60,
    noise_sd: float = 0.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample (x, y) from a known 4PL with optional Gaussian noise."""
    rng = np.random.default_rng(seed)
    x = np.linspace(x_range[0], x_range[1], n)
    y = four_pl(x, bottom, top, midpoint, slope)
    if noise_sd > 0:
        y = y + rng.normal(0.0, noise_sd, size=n)
    return x, y


# ─────────────────────────────────────────────────────────────────
#  fit_sigmoid happy path
# ─────────────────────────────────────────────────────────────────


def test_recovers_known_increasing_curve() -> None:
    x, y = _generate_sigmoid(bottom=0.0, top=0.4, midpoint=1.0, slope=1.5)
    fit = fit_sigmoid(x, y)
    assert fit is not None
    assert fit.bottom == pytest.approx(0.0, abs=0.02)
    assert fit.top == pytest.approx(0.4, abs=0.02)
    assert fit.midpoint_c == pytest.approx(1.0, abs=0.05)
    assert fit.slope == pytest.approx(1.5, rel=0.1)
    assert fit.r_squared > 0.999


def test_recovers_decreasing_curve_as_negative_slope_or_flipped_asymptotes() -> None:
    """A CC-style descending curve fits either via slope<0 or via bottom>top."""
    x, y = _generate_sigmoid(bottom=0.4, top=0.0, midpoint=-1.0, slope=1.5)
    fit = fit_sigmoid(x, y)
    assert fit is not None
    assert fit.r_squared > 0.99
    # The curve evaluated at the extremes should be near 0.4 (low x) and 0.0 (high x)
    y_at_low = four_pl(x.min(), fit.bottom, fit.top, fit.midpoint_c, fit.slope)
    y_at_high = four_pl(x.max(), fit.bottom, fit.top, fit.midpoint_c, fit.slope)
    assert y_at_low > y_at_high


def test_noisy_curve_still_recovers_within_tolerance() -> None:
    x, y = _generate_sigmoid(
        bottom=0.0, top=0.3, midpoint=0.5, slope=1.2,
        noise_sd=0.01, n=80, seed=0,
    )
    fit = fit_sigmoid(x, y)
    assert fit is not None
    assert fit.r_squared > 0.95
    assert fit.midpoint_c == pytest.approx(0.5, abs=0.2)


def test_r_squared_close_to_one_on_clean_data() -> None:
    x, y = _generate_sigmoid(bottom=0.0, top=0.5, midpoint=0.0, slope=2.0)
    fit = fit_sigmoid(x, y)
    assert fit is not None
    assert fit.r_squared > 0.999


# ─────────────────────────────────────────────────────────────────
#  Failure / edge modes
# ─────────────────────────────────────────────────────────────────


def test_too_few_points_returns_none() -> None:
    x = np.array([-1.0, 0.0, 1.0])
    y = np.array([0.0, 0.1, 0.2])
    assert fit_sigmoid(x, y) is None


def test_perfectly_flat_input_returns_none() -> None:
    x = np.linspace(-3.0, 3.0, 20)
    y = np.full(20, 0.123)
    assert fit_sigmoid(x, y) is None


def test_nan_inputs_are_dropped_before_fitting() -> None:
    x, y = _generate_sigmoid(bottom=0.0, top=0.3, midpoint=0.0, slope=1.5, n=40)
    x_dirty = x.copy()
    y_dirty = y.copy()
    x_dirty[5] = np.nan
    y_dirty[10] = np.nan
    fit = fit_sigmoid(x_dirty, y_dirty)
    assert fit is not None
    assert fit.n_points == 38


def test_pandas_series_inputs_work() -> None:
    x_arr, y_arr = _generate_sigmoid(
        bottom=0.0, top=0.4, midpoint=0.0, slope=1.5, n=40,
    )
    fit = fit_sigmoid(pd.Series(x_arr), pd.Series(y_arr))
    assert fit is not None
    assert fit.r_squared > 0.99


def test_fit_is_frozen_dataclass() -> None:
    x, y = _generate_sigmoid(bottom=0.0, top=0.4, midpoint=0.0, slope=1.5, n=40)
    fit = fit_sigmoid(x, y)
    assert isinstance(fit, SigmoidFit)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fit.midpoint_c = 999.0  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────
#  fit_sigmoids_by_group
# ─────────────────────────────────────────────────────────────────


def _toy_response_frame() -> pd.DataFrame:
    """Two strains × two cell types, each with a pooled sigmoid."""
    rng = np.random.default_rng(0)
    rows = []
    for strain in ("CantonS", "nompC3"):
        for cell_type in ("CC", "HC"):
            top = 0.4 if strain == "CantonS" else 0.12
            mid = 1.0 if cell_type == "HC" else -1.0
            slope = 1.5 if cell_type == "HC" else -1.5
            x = np.linspace(-3, 3, 40)
            y = four_pl(x, 0.0, top, mid, slope) + rng.normal(0, 0.005, size=40)
            for xv, yv in zip(x, y, strict=True):
                rows.append({
                    "strain_name": strain,
                    "cell_type": cell_type,
                    "delta_target_c": xv,
                    "dfbf_response_median": yv,
                })
    return pd.DataFrame(rows)


def test_group_table_has_one_row_per_group() -> None:
    table = fit_sigmoids_by_group(_toy_response_frame())
    assert len(table) == 4
    assert set(table.columns) >= {
        "strain_name", "cell_type",
        "bottom", "top", "midpoint_c", "slope", "r_squared", "n_points",
    }


def test_group_table_recovers_per_group_top() -> None:
    table = fit_sigmoids_by_group(_toy_response_frame())
    cantonS = table[table["strain_name"] == "CantonS"]
    assert (cantonS["top"].abs() > 0.3).all()  # nompC3 top is 0.12, CantonS is 0.4
    nompC3 = table[table["strain_name"] == "nompC3"]
    assert (nompC3["top"].abs() < 0.2).all()


def test_group_table_skips_unfittable_groups() -> None:
    df = pd.DataFrame({
        "strain_name": ["FlatStrain"] * 20,
        "cell_type": ["CC"] * 20,
        "delta_target_c": np.linspace(-3, 3, 20),
        "dfbf_response_median": np.full(20, 0.05),
    })
    table = fit_sigmoids_by_group(df)
    assert table.empty


def test_group_table_handles_empty_frame() -> None:
    empty = pd.DataFrame(columns=[
        "strain_name", "cell_type", "delta_target_c", "dfbf_response_median",
    ])
    table = fit_sigmoids_by_group(empty)
    assert table.empty
    assert "slope" in table.columns
