# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.nompc_dosage
# ─────────────────────────────────────────────────────────────────
"""Headline gain-vs-dosage raincloud figure."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from arista.viz.nompc_dosage import (  # noqa: E402
    DEFAULT_DOSAGE_STIMULI,
    NompCDosage,
    _strain_x_positions,
    fetch_dosage_gains,
    plot_nompc_dosage,
)

# ─────────────────────────────────────────────────────────────────
#  Synthetic dosage frame
# ─────────────────────────────────────────────────────────────────


def _toy_dosage_df(seed: int = 0) -> pd.DataFrame:
    """One row per (recording, stimulus) across known-dosage strains."""
    rng = np.random.default_rng(seed)
    rows = []
    rec_id = 0
    # (strain_name in DB, canonical, dosage, expected sign of slope per cell)
    panel = [
        ("CantonS",               "CantonS",              2.0),
        ("white",                 "white",                2.0),
        ("641",                   "641",                  2.0),
        ("NompC3",                "NompC3",               0.0),
        ("nompC_hom",             "NompC3",               0.0),
        ("NompC-HeterozControl",  "NompC-HeterozControl", 1.0),
        ("NompCPbac",             "NompCPbac",            1.75),
        ("NompCRescue",           "NompCRescue",          2.0),
        ("NompCOverExpression",   "NompCOverExpression",  3.0),
    ]
    for raw, _canonical, dose in panel:
        for cell_type in ("CC", "HC"):
            sign = -1.0 if cell_type == "CC" else 1.0
            base = sign * 0.04 * dose  # gain grows with dose
            for stim in ("ascAmp", "descAmp"):
                for _ in range(8):
                    rec_id += 1
                    rows.append({
                        "recording_id": rec_id,
                        "strain_name": raw,
                        "cell_type": cell_type,
                        "hemisphere": rng.choice(["l", "r"]),
                        "stimulus_name": stim,
                        "slope": base + rng.normal(0, 0.01),
                        "intercept": 0.0,
                        "r_squared": 0.95,
                        "n_points": 9,
                    })
    df = pd.DataFrame(rows)
    # Already-canonicalised + dosage columns to match fetch_dosage_gains shape
    from arista.constants import NOMPC_DOSAGE
    from arista.viz.nompc_dosage import _canonicalise
    df["canonical_strain"] = df["strain_name"].map(_canonicalise)
    df["dosage"] = df["strain_name"].map(NOMPC_DOSAGE)
    return df


# ─────────────────────────────────────────────────────────────────
#  _strain_x_positions
# ─────────────────────────────────────────────────────────────────


def test_lone_strain_sits_exactly_on_its_dosage() -> None:
    pos = _strain_x_positions(["NompC3"])
    assert pos["NompC3"] == 0.0


def test_tied_strains_get_symmetric_offsets() -> None:
    pos = _strain_x_positions(["CantonS", "white", "641"])
    xs = sorted(pos.values())
    # Three strains tied at 2.0 should be spread around 2.0 with mean=2.0
    assert xs[0] < 2.0 < xs[-1]
    assert abs(np.mean(xs) - 2.0) < 1e-9
    # And symmetric: outermost offsets equal
    assert abs((2.0 - xs[0]) - (xs[-1] - 2.0)) < 1e-9


def test_strain_unknown_to_dosage_map_is_skipped() -> None:
    pos = _strain_x_positions(["CantonS", "MysteryStrain"])
    assert "MysteryStrain" not in pos
    assert pos["CantonS"] == 2.0  # tier of one → sits exactly on dosage


# ─────────────────────────────────────────────────────────────────
#  plot_nompc_dosage
# ─────────────────────────────────────────────────────────────────


def test_plot_returns_figure_with_one_panel_per_cell_type() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_plot_default_is_abs_gain() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df)
    ylabel = fig.axes[0].get_ylabel()
    assert "|" in ylabel  # |gain| label
    plt.close(fig)


def test_plot_signed_mode_no_pipes_in_ylabel() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df, abs_gain=False)
    ylabel = fig.axes[0].get_ylabel()
    assert "|" not in ylabel
    plt.close(fig)


def test_plot_xlabel_is_dosage() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df)
    for ax in fig.axes:
        assert "dosage" in ax.get_xlabel().lower()
    plt.close(fig)


def test_plot_xticks_match_dosage_tiers_present() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df)
    xticks = fig.axes[0].get_xticks()
    # Tiers present: 0, 1, 1.75, 2, 3
    assert set(np.round(xticks, 2)) >= {0.0, 1.0, 1.75, 2.0, 3.0}
    plt.close(fig)


def test_plot_canonicalises_strain_aliases_at_plot_time() -> None:
    """``nompC_hom`` records should pool with ``NompC3`` (same dosage tier=0)."""
    df = _toy_dosage_df()
    # nompC_hom + NompC3 both canonicalise to NompC3
    assert (df.loc[df["strain_name"] == "nompC_hom", "canonical_strain"] == "NompC3").all()
    fig = plot_nompc_dosage(df, cell_types=("CC",))
    # Only one legend entry for the null-dosage tier (NompC3), not two
    ax = fig.axes[0]
    legend = ax.get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    assert "NompC3" in labels
    assert "nompC_hom" not in labels
    plt.close(fig)


def test_plot_handles_empty_frame() -> None:
    empty = pd.DataFrame(columns=[
        "recording_id", "strain_name", "canonical_strain", "dosage",
        "cell_type", "hemisphere", "stimulus_name",
        "slope", "intercept", "r_squared", "n_points",
    ])
    fig = plot_nompc_dosage(empty)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("no data" in t for t in txts)
    plt.close(fig)


def test_plot_connect_tiers_adds_trend_line() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df, connect_tiers=True)
    dashed_lines = [
        line for line in fig.axes[0].get_lines()
        if line.get_linestyle() == "--"
    ]
    assert len(dashed_lines) >= 1
    plt.close(fig)


def test_plot_connect_tiers_can_be_disabled() -> None:
    df = _toy_dosage_df()
    fig = plot_nompc_dosage(df, connect_tiers=False, abs_gain=False)
    dashed_lines = [
        line for line in fig.axes[0].get_lines()
        if line.get_linestyle() == "--" and line.get_label() == "tier median"
    ]
    assert len(dashed_lines) == 0
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  NompCDosage class
# ─────────────────────────────────────────────────────────────────


def test_class_callable_returns_figure() -> None:
    df = _toy_dosage_df()
    plotter = NompCDosage()
    fig = plotter(df)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_class_save_writes_png_and_svg(tmp_path: Path) -> None:
    df = _toy_dosage_df()
    plotter = NompCDosage()
    fig = plotter(df)
    target = tmp_path / "dosage.png"
    png_path = plotter.save(fig, target)
    assert png_path == target
    assert png_path.exists()
    assert png_path.with_suffix(".svg").exists()


def test_class_abs_gain_override_propagates() -> None:
    df = _toy_dosage_df()
    plotter = NompCDosage(abs_gain=True)
    fig = plotter(df, abs_gain=False)
    assert "|" not in fig.axes[0].get_ylabel()
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  DB round-trip
# ─────────────────────────────────────────────────────────────────


def _build_minimal_db_with_two_dosage_tiers(tmp_path: Path) -> Path:
    """Wild-type + null cells across one stimulus, enough for a tiny figure."""
    from arista.db.connection import open_db
    from arista.db.schema import build_schema

    db_path = tmp_path / "dosage_fixture.db"
    with open_db(db_path) as conn:
        build_schema(conn)
        conn.executescript("""
            INSERT INTO researchers(researcher_id, name, role, period)
                VALUES (1, 'kossen', 'PhD', '2014-2019');
            INSERT INTO strains(strain_id, strain_name)
                VALUES (1, 'CantonS'), (2, 'NompC3');
            INSERT INTO cell_types(cell_type_id, code, name)
                VALUES (1, 'CC', 'cold cell');
            INSERT INTO stimulus_protocols(stimulus_id, name, family)
                VALUES (1, 'ascAmp', 'thermal_step');
            INSERT INTO source_files(file_id, path, kind, sha256, size_bytes)
                VALUES (1, '/tmp/x.csv', 'fiji_csv', 'deadbeef', 1);
            INSERT INTO animals(animal_id, researcher_id, strain_id,
                                recording_date, sex, animal_number, arista_suffix)
                VALUES
                    (1, 1, 1, '2018-06-01', 'f', 1, NULL),
                    (2, 1, 2, '2018-06-02', 'f', 2, NULL);
            INSERT INTO recordings(recording_id, animal_id, cell_type_id,
                                   cell_number, stimulus_id, hemisphere,
                                   response_file_id)
                VALUES
                    (1, 1, 1, 1, 1, 'l', 1),
                    (2, 1, 1, 2, 1, 'l', 1),
                    (3, 2, 1, 1, 1, 'l', 1),
                    (4, 2, 1, 2, 1, 'l', 1);
            -- WT recordings: steep negative slope (good cold response)
            INSERT INTO stimulus_responses(recording_id, step_index,
                                           target_temp_c, delta_target_c,
                                           observed_temp_median,
                                           dfbf_response_median,
                                           n_frames_in_window)
                VALUES
                    (1, 0, 19.0, -3.0, 19.0,  0.30, 200),
                    (1, 1, 21.0, -1.0, 21.0,  0.10, 200),
                    (1, 2, 22.0,  0.0, 22.0,  0.00, 200),
                    (1, 3, 23.0,  1.0, 23.0, -0.10, 200),
                    (1, 4, 25.0,  3.0, 25.0, -0.30, 200),
                    (2, 0, 19.0, -3.0, 19.0,  0.25, 200),
                    (2, 1, 21.0, -1.0, 21.0,  0.08, 200),
                    (2, 2, 22.0,  0.0, 22.0,  0.01, 200),
                    (2, 3, 23.0,  1.0, 23.0, -0.07, 200),
                    (2, 4, 25.0,  3.0, 25.0, -0.22, 200),
                    -- Null recordings: nearly flat (poor response)
                    (3, 0, 19.0, -3.0, 19.0,  0.02, 200),
                    (3, 1, 21.0, -1.0, 21.0,  0.01, 200),
                    (3, 2, 22.0,  0.0, 22.0,  0.00, 200),
                    (3, 3, 23.0,  1.0, 23.0, -0.01, 200),
                    (3, 4, 25.0,  3.0, 25.0, -0.02, 200),
                    (4, 0, 19.0, -3.0, 19.0,  0.01, 200),
                    (4, 1, 21.0, -1.0, 21.0,  0.00, 200),
                    (4, 2, 22.0,  0.0, 22.0,  0.00, 200),
                    (4, 3, 23.0,  1.0, 23.0,  0.00, 200),
                    (4, 4, 25.0,  3.0, 25.0, -0.01, 200);
        """)
    return db_path


def test_fetch_dosage_gains_drops_strains_with_no_dosage(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_two_dosage_tiers(tmp_path)
    conn = sqlite3.connect(db_path)
    df = fetch_dosage_gains(
        conn, stimulus_names=("ascAmp",), cell_types=("CC",),
    )
    conn.close()
    assert set(df["canonical_strain"]) == {"CantonS", "NompC3"}
    assert (df["dosage"] >= 0).all()


def test_fetch_dosage_gains_uses_default_stimuli_when_unspecified() -> None:
    assert DEFAULT_DOSAGE_STIMULI == (
        "ascAmp", "descAmp", "ascAmpFlip", "descAmpFlip",
    )


def test_plot_from_db_round_trip(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_two_dosage_tiers(tmp_path)
    conn = sqlite3.connect(db_path)
    fig = plot_nompc_dosage(
        conn, stimulus_names=("ascAmp",), cell_types=("CC",),
    )
    conn.close()
    assert len(fig.axes) == 1
    plt.close(fig)
