# ─────────────────────────────────────────────────────────────────
#  Tests for arista.processing.gain
# ─────────────────────────────────────────────────────────────────
"""Per-recording linear gain across stimulus-response steps."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from arista.processing.gain import (
    RecordingGain,
    compute_gains_table,
    compute_recording_gain,
)

# ─────────────────────────────────────────────────────────────────
#  compute_recording_gain
# ─────────────────────────────────────────────────────────────────


def test_perfect_line_recovers_known_slope_and_intercept() -> None:
    df = pd.DataFrame({
        "delta_target_c": [-3.0, -1.0, 0.0, 1.0, 3.0],
        "dfbf_response_median": [-0.3, -0.1, 0.0, 0.1, 0.3],
    })
    fit = compute_recording_gain(df)
    assert fit.slope == pytest.approx(0.1)
    assert fit.intercept == pytest.approx(0.0, abs=1e-9)
    assert fit.r_squared == pytest.approx(1.0)
    assert fit.n_points == 5


def test_noisy_line_returns_close_slope() -> None:
    rng = np.random.default_rng(0)
    x = np.linspace(-3.0, 3.0, 20)
    y = 0.12 * x + 0.05 + rng.normal(0, 0.005, size=20)
    df = pd.DataFrame({"delta_target_c": x, "dfbf_response_median": y})
    fit = compute_recording_gain(df)
    assert fit.slope == pytest.approx(0.12, rel=0.1)
    assert fit.r_squared > 0.95


def test_negative_slope_for_cold_cell_response() -> None:
    df = pd.DataFrame({
        "delta_target_c": [-3.0, -1.0, 0.0, 1.0, 3.0],
        "dfbf_response_median": [0.4, 0.2, 0.0, -0.1, -0.2],
    })
    fit = compute_recording_gain(df)
    assert fit.slope < 0
    assert fit.r_squared > 0.95


def test_too_few_points_returns_nan() -> None:
    df = pd.DataFrame({
        "delta_target_c": [-3.0],
        "dfbf_response_median": [0.1],
    })
    fit = compute_recording_gain(df)
    assert np.isnan(fit.slope)
    assert np.isnan(fit.r_squared)
    assert fit.n_points == 1


def test_all_x_identical_returns_nan() -> None:
    df = pd.DataFrame({
        "delta_target_c": [1.0, 1.0, 1.0],
        "dfbf_response_median": [0.1, 0.2, 0.3],
    })
    fit = compute_recording_gain(df)
    assert np.isnan(fit.slope)
    assert fit.n_points == 3


def test_nan_inputs_are_dropped_before_fitting() -> None:
    df = pd.DataFrame({
        "delta_target_c": [-3.0, -1.0, np.nan, 1.0, 3.0],
        "dfbf_response_median": [-0.3, -0.1, 0.5, 0.1, 0.3],
    })
    fit = compute_recording_gain(df)
    # The NaN-y pair should be dropped → 4 clean points fitting y = 0.1 x
    assert fit.n_points == 4
    assert fit.slope == pytest.approx(0.1)


def test_recording_gain_is_frozen() -> None:
    fit = compute_recording_gain(pd.DataFrame({
        "delta_target_c": [-1.0, 1.0],
        "dfbf_response_median": [-0.1, 0.1],
    }))
    assert isinstance(fit, RecordingGain)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fit.slope = 999.0  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────
#  compute_gains_table
# ─────────────────────────────────────────────────────────────────


def _toy_response_df() -> pd.DataFrame:
    """Two recordings × two cell types × five delta steps."""
    rows = []
    rec_id = 0
    for strain in ("CantonS", "nompC3"):
        for cell_type in ("CC", "HC"):
            for _ in range(3):  # 3 recordings per (strain, cell_type)
                rec_id += 1
                # CC: negative slope. HC: positive slope.
                slope = -0.1 if cell_type == "CC" else 0.1
                slope *= 1.0 if strain == "CantonS" else 0.3  # nompC3 attenuated
                for delta in (-3.0, -1.0, 0.0, 1.0, 3.0):
                    rows.append({
                        "recording_id": rec_id,
                        "strain_name": strain,
                        "cell_type": cell_type,
                        "hemisphere": "l",
                        "delta_target_c": delta,
                        "dfbf_response_median": slope * delta,
                    })
    return pd.DataFrame(rows)


def test_table_one_row_per_recording() -> None:
    df = _toy_response_df()
    table = compute_gains_table(df)
    # 2 strains × 2 cell_types × 3 recordings = 12 rows
    assert len(table) == 12


def test_table_carries_group_keys() -> None:
    df = _toy_response_df()
    table = compute_gains_table(df)
    expected = {"recording_id", "strain_name", "cell_type", "hemisphere",
                "slope", "intercept", "r_squared", "n_points"}
    assert expected <= set(table.columns)


def test_table_signs_match_cell_type() -> None:
    df = _toy_response_df()
    table = compute_gains_table(df)
    cc_slopes = table.loc[table["cell_type"] == "CC", "slope"]
    hc_slopes = table.loc[table["cell_type"] == "HC", "slope"]
    assert (cc_slopes < 0).all()
    assert (hc_slopes > 0).all()


def test_table_filters_below_min_steps() -> None:
    # Build a response frame where one recording has only 2 steps
    df = pd.DataFrame({
        "recording_id": [1, 1, 2, 2, 2, 2, 2],
        "strain_name":  ["A"] * 7,
        "cell_type":    ["CC"] * 7,
        "hemisphere":   ["l"] * 7,
        "delta_target_c":      [-1.0, 1.0, -3.0, -1.0, 0.0, 1.0, 3.0],
        "dfbf_response_median": [0.1, -0.1, 0.3, 0.1, 0.0, -0.1, -0.3],
    })
    table = compute_gains_table(df, min_steps=3)
    # Recording 1 has only 2 points → dropped. Recording 2 stays.
    assert set(table["recording_id"]) == {2}


def test_table_handles_empty_frame() -> None:
    empty = pd.DataFrame(columns=[
        "recording_id", "strain_name", "cell_type", "hemisphere",
        "delta_target_c", "dfbf_response_median",
    ])
    table = compute_gains_table(empty)
    assert table.empty
    assert "slope" in table.columns


def test_table_preserves_nulls_in_group_keys() -> None:
    # Recordings with NULL hemisphere should still be grouped, not silently dropped
    df = pd.DataFrame({
        "recording_id": [1, 1, 1],
        "strain_name":  ["A", "A", "A"],
        "cell_type":    ["CC", "CC", "CC"],
        "hemisphere":   [None, None, None],
        "delta_target_c":      [-1.0, 0.0, 1.0],
        "dfbf_response_median": [0.1, 0.0, -0.1],
    })
    table = compute_gains_table(df, min_steps=3)
    assert len(table) == 1
