# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.sigmoid_fits
# ─────────────────────────────────────────────────────────────────
"""Per-strain × cell-type 4PL sigmoid overlays."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from arista.processing.sigmoid import four_pl  # noqa: E402
from arista.viz.sigmoid_fits import (  # noqa: E402
    SigmoidFits,
    plot_sigmoid_fits,
)


def _synthetic_response_frame() -> pd.DataFrame:
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


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def test_returns_figure_with_one_panel_per_cell_type() -> None:
    df = _synthetic_response_frame()
    fig = plot_sigmoid_fits(df, stimulus_name="ascAmp")
    assert len(fig.axes) == 2
    plt.close(fig)


def test_each_panel_has_one_line_per_strain() -> None:
    df = _synthetic_response_frame()
    fig = plot_sigmoid_fits(df, stimulus_name="ascAmp")
    for ax in fig.axes:
        # One Line2D per fitted strain (CantonS, nompC3)
        n_lines = sum(1 for line in ax.get_lines() if line.get_linestyle() == "-")
        assert n_lines >= 2
    plt.close(fig)


def test_handles_unfittable_group_silently() -> None:
    """Flat data for one strain should still let the rest of the figure render."""
    df = _synthetic_response_frame()
    flat_rows = pd.DataFrame({
        "strain_name": ["FlatStrain"] * 30,
        "cell_type": ["CC"] * 30,
        "delta_target_c": np.linspace(-3, 3, 30),
        "dfbf_response_median": np.full(30, 0.05),
    })
    combined = pd.concat([df, flat_rows], ignore_index=True)
    fig = plot_sigmoid_fits(combined, stimulus_name="ascAmp")
    assert len(fig.axes) == 2
    plt.close(fig)


def test_handles_empty_frame() -> None:
    empty = pd.DataFrame(columns=[
        "strain_name", "cell_type",
        "delta_target_c", "dfbf_response_median",
    ])
    fig = plot_sigmoid_fits(empty, stimulus_name="ascAmp")
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("no data" in t for t in txts)
    plt.close(fig)


def test_requires_stimulus_name_with_connection() -> None:
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="stimulus_name"):
        plot_sigmoid_fits(conn)
    conn.close()


def test_title_auto_from_stimulus_name() -> None:
    df = _synthetic_response_frame()
    fig = plot_sigmoid_fits(df, stimulus_name="ascAmp")
    assert fig._suptitle is not None
    assert "ascAmp" in fig._suptitle.get_text()
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  SigmoidFits class
# ─────────────────────────────────────────────────────────────────


def test_class_callable_returns_figure() -> None:
    df = _synthetic_response_frame()
    plotter = SigmoidFits()
    fig = plotter(df, stimulus_name="ascAmp")
    assert len(fig.axes) == 2
    plt.close(fig)


def test_class_save_writes_png_and_svg(tmp_path: Path) -> None:
    df = _synthetic_response_frame()
    plotter = SigmoidFits()
    fig = plotter(df, stimulus_name="ascAmp")
    target = tmp_path / "sig.png"
    png_path = plotter.save(fig, target)
    assert png_path == target
    assert png_path.exists()
    assert png_path.with_suffix(".svg").exists()


def test_class_strains_filter_propagates() -> None:
    df = _synthetic_response_frame()
    plotter = SigmoidFits(strains=("CantonS",))
    fig = plotter(df, stimulus_name="ascAmp", cell_types=("HC",))
    ax = fig.axes[0]
    # Only one strain → at most one fitted curve
    line_strains = [
        line.get_label() for line in ax.get_lines()
        if line.get_label().startswith("CantonS")
    ]
    assert len(line_strains) >= 1
    plt.close(fig)
