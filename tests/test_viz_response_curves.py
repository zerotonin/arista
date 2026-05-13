# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.response_curves
# ─────────────────────────────────────────────────────────────────
"""Bootstrap-CI aggregation, Shapiro-Wilk gated SEM, two-panel plot."""

from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from arista.viz.response_curves import (  # noqa: E402
    ResponseCurves,
    _bootstrap_median_ci,
    aggregate_response_data,
    fetch_response_data,
    plot_response_curves,
)

# ─────────────────────────────────────────────────────────────────
#  Synthetic data
# ─────────────────────────────────────────────────────────────────


def _synthetic_long_df(
    *,
    strains: tuple[str, ...] = ("CantonS", "nompC3"),
    cell_types: tuple[str, ...] = ("CC", "HC"),
    deltas: tuple[float, ...] = (-3.0, -1.0, 1.0, 3.0),
    n_per_group: int = 6,
    noise_sd: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    """One row per (strain, cell_type, delta, recording)."""
    rng = np.random.default_rng(seed)
    rows = []
    rec_id = 0
    for strain in strains:
        for cell_type in cell_types:
            for delta in deltas:
                # CC: respond to cold (negative delta). HC: respond to hot.
                # nompC3 has flattened response.
                gain = 0.15 if strain == "CantonS" else 0.05
                sign = -1.0 if cell_type == "CC" else 1.0
                expected = max(0.0, sign * delta * gain)
                for _ in range(n_per_group):
                    rec_id += 1
                    rows.append({
                        "recording_id": rec_id,
                        "researcher_name": "test",
                        "strain_name": strain,
                        "cell_type": cell_type,
                        "cell_number": 1,
                        "hemisphere": "left",
                        "animal_number": 1,
                        "step_index": 0,
                        "target_temp_c": 22.0 + delta,
                        "delta_target_c": delta,
                        "dfbf_response_median": expected + rng.normal(0, noise_sd),
                        "observed_temp_median": 22.0 + delta,
                        "n_frames_in_window": 200,
                    })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
#  _bootstrap_median_ci
# ─────────────────────────────────────────────────────────────────


def test_bootstrap_ci_brackets_true_median_for_clean_data() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(loc=2.5, scale=0.3, size=200)
    low, high = _bootstrap_median_ci(
        x, n_resamples=2000, confidence_level=0.95, rng=np.random.default_rng(1)
    )
    assert low < 2.5 < high
    assert high - low < 0.2  # tight CI on n=200


def test_bootstrap_ci_handles_n_equals_one() -> None:
    rng = np.random.default_rng(0)
    low, high = _bootstrap_median_ci(
        np.array([3.14]), n_resamples=100, confidence_level=0.95, rng=rng,
    )
    assert low == high == 3.14


def test_bootstrap_ci_is_reproducible_under_same_seed() -> None:
    x = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    a = _bootstrap_median_ci(x, n_resamples=500, confidence_level=0.95, rng=np.random.default_rng(7))
    b = _bootstrap_median_ci(x, n_resamples=500, confidence_level=0.95, rng=np.random.default_rng(7))
    assert a == b


# ─────────────────────────────────────────────────────────────────
#  aggregate_response_data
# ─────────────────────────────────────────────────────────────────


def test_aggregate_returns_expected_columns() -> None:
    df = _synthetic_long_df()
    agg = aggregate_response_data(df)
    expected = {
        "strain_name", "cell_type", "delta_target_c",
        "n", "median", "ci_low", "ci_high",
        "q25", "q75", "mean", "sem", "shapiro_p",
    }
    assert expected <= set(agg.columns)


def test_aggregate_ci_brackets_median_at_each_group() -> None:
    df = _synthetic_long_df(n_per_group=20, noise_sd=0.02)
    agg = aggregate_response_data(df)
    # For non-degenerate groups (n>=2), ci_low <= median <= ci_high
    valid = agg["n"] >= 2
    assert ((agg.loc[valid, "ci_low"] <= agg.loc[valid, "median"]).all())
    assert ((agg.loc[valid, "median"] <= agg.loc[valid, "ci_high"]).all())


def test_aggregate_n_counts_recordings() -> None:
    df = _synthetic_long_df(n_per_group=6)
    agg = aggregate_response_data(df)
    # Each (strain, cell_type, delta) group should have exactly 6 recordings
    assert (agg["n"] == 6).all()


def test_aggregate_handles_empty_df() -> None:
    empty = pd.DataFrame(columns=[
        "recording_id", "strain_name", "cell_type",
        "delta_target_c", "dfbf_response_median",
    ])
    agg = aggregate_response_data(empty)
    assert agg.empty
    assert "ci_low" in agg.columns
    assert "shapiro_p" in agg.columns


def test_aggregate_is_reproducible_under_same_seed() -> None:
    df = _synthetic_long_df()
    a = aggregate_response_data(df, rng_seed=11)
    b = aggregate_response_data(df, rng_seed=11)
    pd.testing.assert_frame_equal(a, b)


def test_aggregate_shapiro_p_is_nan_for_small_n() -> None:
    # n=2 should give NaN Shapiro-Wilk
    df = pd.DataFrame({
        "strain_name": ["A", "A"],
        "cell_type": ["CC", "CC"],
        "delta_target_c": [-3.0, -3.0],
        "dfbf_response_median": [0.1, 0.2],
    })
    agg = aggregate_response_data(df)
    assert agg["n"].iloc[0] == 2
    assert np.isnan(agg["shapiro_p"].iloc[0])


# ─────────────────────────────────────────────────────────────────
#  plot_response_curves
# ─────────────────────────────────────────────────────────────────


def test_plot_returns_figure_with_one_panel_per_cell_type() -> None:
    df = _synthetic_long_df()
    fig = plot_response_curves(df, stimulus_name="ascAmp")
    assert len(fig.axes) == 2
    plt.close(fig)


def test_plot_default_error_mode_is_ci() -> None:
    df = _synthetic_long_df()
    fig = plot_response_curves(df, stimulus_name="ascAmp")
    ylabel = fig.axes[0].get_ylabel()
    assert "median" in ylabel
    assert "95% CI" in ylabel
    plt.close(fig)


def test_plot_iqr_mode_labels_correctly() -> None:
    df = _synthetic_long_df()
    fig = plot_response_curves(df, stimulus_name="ascAmp", error="iqr")
    ylabel = fig.axes[0].get_ylabel()
    assert "IQR" in ylabel
    plt.close(fig)


def test_plot_none_mode_omits_band() -> None:
    df = _synthetic_long_df()
    fig = plot_response_curves(df, stimulus_name="ascAmp", error="none")
    ylabel = fig.axes[0].get_ylabel()
    assert "CI" not in ylabel and "IQR" not in ylabel and "SEM" not in ylabel
    plt.close(fig)


def test_plot_sem_falls_back_to_ci_on_non_normal_data() -> None:
    # Heavily skewed → Shapiro should reject normality
    rng = np.random.default_rng(0)
    rows = []
    rec_id = 0
    for delta in (-3.0, -1.0, 1.0, 3.0):
        for _ in range(15):
            rec_id += 1
            # Exponential is decidedly non-normal
            rows.append({
                "recording_id": rec_id, "strain_name": "Skewed",
                "cell_type": "CC", "delta_target_c": delta,
                "dfbf_response_median": rng.exponential(scale=0.5),
            })
    df = pd.DataFrame(rows)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = plot_response_curves(
            df, stimulus_name="test",
            cell_types=("CC",), error="sem",
        )
    # We expect at least one RuntimeWarning about Shapiro-Wilk
    msgs = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    assert any("Shapiro-Wilk" in m for m in msgs), msgs
    # And the y-axis label should reflect the fallback to median+CI
    assert "median" in fig.axes[0].get_ylabel()
    assert "95% CI" in fig.axes[0].get_ylabel()
    plt.close(fig)


def test_plot_sem_passes_through_when_normal() -> None:
    rng = np.random.default_rng(1)
    rows = []
    rec_id = 0
    for delta in (-3.0, -1.0, 1.0, 3.0):
        for _ in range(20):
            rec_id += 1
            rows.append({
                "recording_id": rec_id, "strain_name": "Normal",
                "cell_type": "CC", "delta_target_c": delta,
                "dfbf_response_median": rng.normal(loc=delta * 0.1, scale=0.05),
            })
    df = pd.DataFrame(rows)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = plot_response_curves(
            df, stimulus_name="test",
            cell_types=("CC",), error="sem",
        )
    # Should NOT have downgraded
    msgs = [str(w.message) for w in caught if "Shapiro-Wilk" in str(w.message)]
    assert msgs == [], f"unexpected Shapiro downgrade warnings: {msgs}"
    ylabel = fig.axes[0].get_ylabel()
    assert "mean" in ylabel
    assert "SEM" in ylabel
    plt.close(fig)


def test_plot_requires_stimulus_name_when_passed_a_connection(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="stimulus_name"):
        plot_response_curves(conn)
    conn.close()


def test_plot_handles_empty_dataframe() -> None:
    empty = pd.DataFrame(columns=[
        "recording_id", "strain_name", "cell_type",
        "delta_target_c", "dfbf_response_median",
    ])
    fig = plot_response_curves(empty, stimulus_name="ascAmp")
    # "no data for CC" / "no data for HC" annotations on both panels
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("no data" in t for t in txts)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  ResponseCurves class wrapper
# ─────────────────────────────────────────────────────────────────


def test_response_curves_class_is_callable() -> None:
    df = _synthetic_long_df()
    plotter = ResponseCurves()
    fig = plotter(df, stimulus_name="ascAmp")
    assert len(fig.axes) == 2
    plt.close(fig)


def test_response_curves_class_save_writes_png_and_svg(tmp_path: Path) -> None:
    df = _synthetic_long_df()
    plotter = ResponseCurves()
    fig = plotter(df, stimulus_name="ascAmp")
    target = tmp_path / "out.png"
    png_path = plotter.save(fig, target)
    assert png_path == target
    assert png_path.exists()
    assert png_path.with_suffix(".svg").exists()


def test_response_curves_class_overrides_propagate() -> None:
    df = _synthetic_long_df()
    plotter = ResponseCurves(error="ci", figsize=(8, 4))
    fig = plotter(df, stimulus_name="ascAmp", error="iqr")
    assert "IQR" in fig.axes[0].get_ylabel()
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  fetch_response_data against an in-memory DB
# ─────────────────────────────────────────────────────────────────


def _build_minimal_db_with_responses(tmp_path: Path) -> Path:
    """Spin up a real arista schema and stuff one strain × one cell type."""
    from arista.db.connection import open_db
    from arista.db.schema import build_schema

    db_path = tmp_path / "fixture.db"
    with open_db(db_path) as conn:
        build_schema(conn)
        conn.executescript("""
            INSERT INTO researchers(researcher_id, name, role, period)
                VALUES (1, 'test_researcher', 'MSc', '2020-2021');
            INSERT INTO strains(strain_id, strain_name)
                VALUES (1, 'CantonS');
            INSERT INTO cell_types(cell_type_id, code, name)
                VALUES (1, 'CC', 'cold cell');
            INSERT INTO stimulus_protocols(stimulus_id, name, family)
                VALUES (1, 'ascAmp', 'thermal_step');
            INSERT INTO source_files(file_id, path, kind, sha256, size_bytes)
                VALUES (1, '/tmp/x.csv', 'fiji_csv', 'deadbeef', 1);
            INSERT INTO animals(animal_id, researcher_id, strain_id,
                                recording_date, sex, animal_number, arista_suffix)
                VALUES (1, 1, 1, '2020-01-01', 'f', 1, NULL);
            INSERT INTO recordings(recording_id, animal_id, cell_type_id,
                                   cell_number, stimulus_id, hemisphere,
                                   response_file_id)
                VALUES (1, 1, 1, 1, 1, 'l', 1),
                       (2, 1, 1, 2, 1, 'l', 1),
                       (3, 1, 1, 3, 1, 'l', 1);
            INSERT INTO stimulus_responses(recording_id, step_index,
                                           target_temp_c, delta_target_c,
                                           observed_temp_median,
                                           dfbf_response_median,
                                           n_frames_in_window)
                VALUES (1, 0, 19.0, -3.0, 19.0, 0.45, 200),
                       (2, 0, 19.0, -3.0, 19.0, 0.50, 200),
                       (3, 0, 19.0, -3.0, 19.0, 0.55, 200);
        """)
    return db_path


def test_fetch_response_data_from_real_db(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_responses(tmp_path)
    conn = sqlite3.connect(db_path)
    df = fetch_response_data(
        conn, stimulus_name="ascAmp", cell_types=("CC",)
    )
    conn.close()
    assert len(df) == 3
    assert set(df["strain_name"]) == {"CantonS"}
    assert set(df["cell_type"]) == {"CC"}
    assert df["dfbf_response_median"].mean() == pytest.approx(0.5)


def test_plot_from_real_db_round_trip(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_responses(tmp_path)
    conn = sqlite3.connect(db_path)
    fig = plot_response_curves(
        conn, stimulus_name="ascAmp", cell_types=("CC",)
    )
    conn.close()
    assert len(fig.axes) == 1
    plt.close(fig)
