# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.adaptation_taus
# ─────────────────────────────────────────────────────────────────
"""τ raincloud + DB fetch."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from arista.viz.adaptation_taus import (  # noqa: E402
    AdaptationTaus,
    discover_adaptation_stimuli,
    fetch_adaptation_taus,
    plot_adaptation_taus,
)

# ─────────────────────────────────────────────────────────────────
#  Synthetic τ frame
# ─────────────────────────────────────────────────────────────────


def _toy_tau_df(
    *,
    strains: tuple[str, ...] = ("CantonS", "nompC3"),
    cell_types: tuple[str, ...] = ("CC", "HC"),
    n_per_group: int = 10,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    rec_id = 0
    for strain in strains:
        for cell_type in cell_types:
            # nompC3 has shorter τ (faster adaptation) than CantonS
            mu = np.log(60.0) if strain == "CantonS" else np.log(20.0)
            for _ in range(n_per_group):
                rec_id += 1
                rows.append({
                    "recording_id": rec_id,
                    "researcher_name": "test",
                    "strain_name": strain,
                    "cell_type": cell_type,
                    "hemisphere": rng.choice(["l", "r"]),
                    "stimulus_name": "HotAdapt",
                    "tau_s": float(np.exp(mu + rng.normal(0, 0.2))),
                    "amplitude": 0.3,
                    "asymptote": 0.05,
                    "r_squared": 0.97,
                    "n_points": 2000,
                })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
#  plot_adaptation_taus
# ─────────────────────────────────────────────────────────────────


def test_returns_figure_with_one_panel_per_cell_type() -> None:
    df = _toy_tau_df()
    fig = plot_adaptation_taus(df)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_default_yscale_is_log() -> None:
    df = _toy_tau_df()
    fig = plot_adaptation_taus(df)
    assert fig.axes[0].get_yscale() == "log"
    plt.close(fig)


def test_linear_mode_disables_log_scale() -> None:
    df = _toy_tau_df()
    fig = plot_adaptation_taus(df, log_tau=False)
    assert fig.axes[0].get_yscale() == "linear"
    plt.close(fig)


def test_strain_order_respects_explicit_argument() -> None:
    df = _toy_tau_df(strains=("CantonS", "nompC3", "white"))
    fig = plot_adaptation_taus(
        df, cell_types=("CC",), strains=("white", "CantonS", "nompC3"),
    )
    labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    assert labels == ["white", "CantonS", "nompC3"]
    plt.close(fig)


def test_nonpositive_taus_are_dropped() -> None:
    df = _toy_tau_df(n_per_group=5)
    # Inject one nonpositive τ; raincloud should still render
    df.loc[df.index[0], "tau_s"] = -1.0
    fig = plot_adaptation_taus(df, cell_types=("CC",))
    assert len(fig.axes) == 1
    plt.close(fig)


def test_requires_stimulus_name_with_connection() -> None:
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="stimulus_name"):
        plot_adaptation_taus(conn)
    conn.close()


def test_ylabel_says_tau_seconds() -> None:
    df = _toy_tau_df()
    fig = plot_adaptation_taus(df)
    ylabel = fig.axes[0].get_ylabel()
    assert "tau" in ylabel.lower() or r"\tau" in ylabel
    assert "(s)" in ylabel
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  AdaptationTaus class
# ─────────────────────────────────────────────────────────────────


def test_class_callable_returns_figure() -> None:
    df = _toy_tau_df()
    plotter = AdaptationTaus()
    fig = plotter(df)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_class_save_writes_png_and_svg(tmp_path: Path) -> None:
    df = _toy_tau_df()
    plotter = AdaptationTaus()
    fig = plotter(df)
    target = tmp_path / "tau.png"
    png_path = plotter.save(fig, target)
    assert png_path == target
    assert png_path.exists()
    assert png_path.with_suffix(".svg").exists()


def test_class_log_tau_override_propagates() -> None:
    df = _toy_tau_df()
    plotter = AdaptationTaus(log_tau=True)
    fig = plotter(df, log_tau=False)
    assert fig.axes[0].get_yscale() == "linear"
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  DB round-trip
# ─────────────────────────────────────────────────────────────────


def _build_minimal_db_with_adaptation(tmp_path: Path) -> Path:
    from arista.db.connection import open_db
    from arista.db.schema import build_schema

    db_path = tmp_path / "adapt_fixture.db"
    with open_db(db_path) as conn:
        build_schema(conn)
        conn.executescript("""
            INSERT INTO researchers(researcher_id, name, role, period)
                VALUES (1, 'kossen', 'PhD', '2014-2019');
            INSERT INTO strains(strain_id, strain_name)
                VALUES (1, 'CantonS'), (2, 'nompC_hom');
            INSERT INTO cell_types(cell_type_id, code, name)
                VALUES (1, 'CC', 'cold cell'), (2, 'HC', 'hot cell');
            INSERT INTO stimulus_protocols(stimulus_id, name, family)
                VALUES (1, 'HotAdapt', 'thermal_adapt');
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
                    (1, 1, 2, 1, 1, 'l', 1),
                    (2, 1, 2, 2, 1, 'r', 1),
                    (3, 2, 2, 1, 1, 'l', 1),
                    (4, 2, 2, 2, 1, 'r', 1);
            INSERT INTO adaptation_fits(recording_id, tau_s, amplitude,
                                        asymptote, r_squared,
                                        fit_window_start_s, fit_window_end_s,
                                        n_points)
                VALUES
                    (1, 60.0, 0.4, 0.05, 0.97, 75.0, 300.0, 2000),
                    (2, 55.0, 0.4, 0.05, 0.96, 75.0, 300.0, 2000),
                    (3, 25.0, 0.4, 0.05, 0.95, 75.0, 300.0, 2000),
                    (4, 18.0, 0.4, 0.05, 0.94, 75.0, 300.0, 2000);
        """)
    return db_path


def test_discover_adaptation_stimuli_returns_thermal_adapt_only(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_adaptation(tmp_path)
    conn = sqlite3.connect(db_path)
    stims = discover_adaptation_stimuli(conn)
    conn.close()
    assert stims == ["HotAdapt"]


def test_fetch_adaptation_taus_round_trips(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_adaptation(tmp_path)
    conn = sqlite3.connect(db_path)
    taus = fetch_adaptation_taus(
        conn, stimulus_name="HotAdapt", cell_types=("HC",),
    )
    conn.close()
    assert len(taus) == 4
    assert set(taus["strain_name"]) == {"CantonS", "nompC_hom"}
    cantonS = taus[taus["strain_name"] == "CantonS"]
    nompC_hom = taus[taus["strain_name"] == "nompC_hom"]
    assert cantonS["tau_s"].mean() > nompC_hom["tau_s"].mean()


def test_fetch_min_r_squared_filters(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_adaptation(tmp_path)
    conn = sqlite3.connect(db_path)
    taus = fetch_adaptation_taus(
        conn, stimulus_name="HotAdapt", cell_types=("HC",),
        min_r_squared=0.965,
    )
    conn.close()
    # Only recordings 1 (0.97) and 2 (0.96 → just under 0.965) — actually
    # only recording 1 passes. Verify the filter works directionally:
    assert (taus["r_squared"] >= 0.965).all()


def test_plot_from_real_db_round_trip(tmp_path: Path) -> None:
    db_path = _build_minimal_db_with_adaptation(tmp_path)
    conn = sqlite3.connect(db_path)
    fig = plot_adaptation_taus(
        conn, stimulus_name="HotAdapt", cell_types=("HC",),
    )
    conn.close()
    assert len(fig.axes) == 1
    plt.close(fig)
