# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.gain_comparison
# ─────────────────────────────────────────────────────────────────
"""Gain raincloud per strain × cell-type."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from arista.viz.gain_comparison import (  # noqa: E402
    GainComparison,
    fetch_recording_gains,
    plot_gain_comparison,
)

# ─────────────────────────────────────────────────────────────────
#  Synthetic data
# ─────────────────────────────────────────────────────────────────


def _toy_gains_df(
    *,
    strains: tuple[str, ...] = ("CantonS", "nompC3"),
    cell_types: tuple[str, ...] = ("CC", "HC"),
    n_per_group: int = 10,
    seed: int = 0,
) -> pd.DataFrame:
    """One row per (recording, strain, cell_type, hemisphere)."""
    rng = np.random.default_rng(seed)
    rows = []
    rec_id = 0
    for strain in strains:
        for cell_type in cell_types:
            # CC slope negative, HC slope positive; nompC3 attenuated.
            base = -0.12 if cell_type == "CC" else 0.12
            base *= 1.0 if strain == "CantonS" else 0.3
            for _ in range(n_per_group):
                rec_id += 1
                rows.append({
                    "recording_id": rec_id,
                    "strain_name": strain,
                    "cell_type": cell_type,
                    "hemisphere": rng.choice(["l", "r"]),
                    "slope": base + rng.normal(0, 0.01),
                    "intercept": 0.0,
                    "r_squared": 0.95,
                    "n_points": 9,
                })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
#  plot_gain_comparison
# ─────────────────────────────────────────────────────────────────


def test_plot_returns_figure_with_one_panel_per_cell_type() -> None:
    df = _toy_gains_df()
    fig = plot_gain_comparison(df, cell_types=("CC", "HC"))
    assert len(fig.axes) == 2
    plt.close(fig)


def test_plot_single_cell_type_still_works() -> None:
    df = _toy_gains_df(cell_types=("CC",))
    fig = plot_gain_comparison(df, cell_types=("CC",))
    assert len(fig.axes) == 1
    plt.close(fig)


def test_plot_signed_y_label_says_gain() -> None:
    df = _toy_gains_df()
    fig = plot_gain_comparison(df)
    ylabel = fig.axes[0].get_ylabel()
    assert "gain" in ylabel
    assert "|" not in ylabel  # signed mode — no absolute bars
    plt.close(fig)


def test_plot_abs_gain_label_includes_pipes() -> None:
    df = _toy_gains_df()
    fig = plot_gain_comparison(df, abs_gain=True)
    ylabel = fig.axes[0].get_ylabel()
    assert "|" in ylabel
    plt.close(fig)


def test_plot_xticks_match_strains_present() -> None:
    df = _toy_gains_df(strains=("CantonS", "nompC3", "OE"))
    fig = plot_gain_comparison(df, cell_types=("CC",))
    labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    assert set(labels) == {"CantonS", "nompC3", "OE"}
    plt.close(fig)


def test_plot_strain_order_respects_explicit_argument() -> None:
    df = _toy_gains_df(strains=("CantonS", "nompC3"))
    fig = plot_gain_comparison(
        df, cell_types=("CC",), strains=("nompC3", "CantonS"),
    )
    labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    assert labels == ["nompC3", "CantonS"]
    plt.close(fig)


def test_plot_requires_stimulus_name_when_passed_a_connection() -> None:
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="stimulus_name"):
        plot_gain_comparison(conn)
    conn.close()


def test_plot_handles_empty_gains_frame() -> None:
    empty = pd.DataFrame(columns=[
        "recording_id", "strain_name", "cell_type", "hemisphere",
        "slope", "intercept", "r_squared", "n_points",
    ])
    fig = plot_gain_comparison(empty)
    # Empty panels still rendered (one per cell type)
    assert len(fig.axes) == 2
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  GainComparison class
# ─────────────────────────────────────────────────────────────────


def test_class_is_callable() -> None:
    df = _toy_gains_df()
    plotter = GainComparison()
    fig = plotter(df)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_class_save_writes_png_and_svg(tmp_path: Path) -> None:
    df = _toy_gains_df()
    plotter = GainComparison()
    fig = plotter(df)
    target = tmp_path / "gain.png"
    png_path = plotter.save(fig, target)
    assert png_path == target
    assert png_path.exists()
    assert png_path.with_suffix(".svg").exists()


def test_class_abs_gain_override_propagates() -> None:
    df = _toy_gains_df()
    plotter = GainComparison(abs_gain=False)
    fig = plotter(df, abs_gain=True)
    assert "|" in fig.axes[0].get_ylabel()
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  fetch_recording_gains against an in-memory DB
# ─────────────────────────────────────────────────────────────────


def _build_minimal_db_with_responses(tmp_path: Path) -> Path:
    """Reuse the schema fixture pattern from test_viz_response_curves."""
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
                       (2, 1, 1, 2, 1, 'l', 1);
            -- Recording 1: clean negative slope (CC response)
            INSERT INTO stimulus_responses(recording_id, step_index,
                                           target_temp_c, delta_target_c,
                                           observed_temp_median,
                                           dfbf_response_median,
                                           n_frames_in_window)
                VALUES (1, 0, 19.0, -3.0, 19.0,  0.30, 200),
                       (1, 1, 21.0, -1.0, 21.0,  0.10, 200),
                       (1, 2, 22.0,  0.0, 22.0,  0.00, 200),
                       (1, 3, 23.0,  1.0, 23.0, -0.10, 200),
                       (1, 4, 25.0,  3.0, 25.0, -0.30, 200),
                       (2, 0, 19.0, -3.0, 19.0,  0.25, 200),
                       (2, 1, 21.0, -1.0, 21.0,  0.08, 200),
                       (2, 2, 22.0,  0.0, 22.0,  0.01, 200),
                       (2, 3, 23.0,  1.0, 23.0, -0.07, 200),
                       (2, 4, 25.0,  3.0, 25.0, -0.22, 200);
        """)
    return db_path


def test_fetch_recording_gains_returns_one_row_per_recording(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_responses(tmp_path)
    conn = sqlite3.connect(db_path)
    table = fetch_recording_gains(
        conn, stimulus_name="ascAmp", cell_types=("CC",),
    )
    conn.close()
    assert len(table) == 2
    # Both recordings should produce negative slopes (CC cold-response)
    assert (table["slope"] < 0).all()
    assert (table["r_squared"] > 0.95).all()


def test_plot_from_real_db_round_trip(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_responses(tmp_path)
    conn = sqlite3.connect(db_path)
    fig = plot_gain_comparison(
        conn, stimulus_name="ascAmp", cell_types=("CC",),
    )
    conn.close()
    assert len(fig.axes) == 1
    plt.close(fig)
