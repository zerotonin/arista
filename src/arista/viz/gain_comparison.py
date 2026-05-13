# ─────────────────────────────────────────────────────────────────
#  arista.viz.gain_comparison
#  « linear-gain raincloud per strain × cell-type (Kossen Fig 27) »
# ─────────────────────────────────────────────────────────────────
"""Compare ΔF/F-per-°C gain across strains and cell types.

This is the headline NompC-dosage figure: for each recording fit a
line through the per-step (Δ target, ΔF/F) points, take the slope as
the cell's gain, and render a raincloud (half-violin + box + jittered
strip) per (strain, cell-type) group. CLAUDE.md §7.3 — raincloud over
bar — is honoured by construction.

Cell-type signs: CC slope is negative (cold stimuli drive positive
response), HC slope is positive. The default panel layout keeps the
signs as-is (one panel per cell type, y-axis crosses zero) so the
direction is read directly off the figure. ``abs_gain=True`` switches
to absolute slope magnitude when the goal is direct strain comparison
across cell types.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from arista.constants import (
    FIGURE_DPI,
    STRAIN_COLOURS,
)
from arista.processing.gain import compute_gains_table
from arista.viz._raincloud import raincloud
from arista.viz.response_curves import fetch_response_data

if TYPE_CHECKING:
    from matplotlib.figure import Figure


_DEFAULT_RNG_SEED: int = 13


# ─────────────────────────────────────────────────────────────────
#  Data fetch
# ─────────────────────────────────────────────────────────────────


def fetch_recording_gains(
    conn: sqlite3.Connection,
    *,
    stimulus_name: str,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    min_steps: int = 3,
) -> pd.DataFrame:
    """Per-recording gains from a populated ``arista.db``.

    Returns:
        DataFrame with one row per (recording, strain, cell_type,
        hemisphere) carrying ``slope``, ``intercept``, ``r_squared``,
        ``n_points``.
    """
    response_df = fetch_response_data(
        conn,
        stimulus_name=stimulus_name,
        cell_types=cell_types,
        strains=strains,
    )
    return compute_gains_table(response_df, min_steps=min_steps)


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def plot_gain_comparison(
    data: pd.DataFrame | sqlite3.Connection,
    *,
    stimulus_name: str | None = None,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    abs_gain: bool = False,
    min_steps: int = 3,
    figsize: tuple[float, float] = (12, 5),
    title: str | None = None,
    rng_seed: int = _DEFAULT_RNG_SEED,
) -> Figure:
    """Raincloud comparison of per-recording gain across strains.

    Args:
        data: Either an already-computed gain frame (output of
            :func:`fetch_recording_gains` / :func:`compute_gains_table`)
            or a live SQLite connection.
        stimulus_name: Stimulus protocol (mandatory when ``data`` is a
            connection).
        cell_types: Cell types to plot, one panel per.
        strains: Optional strain whitelist (in display order). When
            ``None``, every strain present in ``data`` is plotted in
            sorted order.
        abs_gain: When ``True`` plot ``|slope|`` instead of signed
            slope — useful for direct cross-cell-type comparison.
        min_steps: Forwarded to :func:`compute_gains_table` when
            ``data`` is a connection.
        figsize: ``(width, height)`` inches.
        title: Optional figure suptitle.
        rng_seed: Seed for the jitter RNG (reproducibility).

    Returns:
        :class:`matplotlib.figure.Figure`. Caller owns I/O.
    """
    import matplotlib.pyplot as plt

    if isinstance(data, sqlite3.Connection):
        if stimulus_name is None:
            raise ValueError(
                "stimulus_name is required when data is a Connection"
            )
        gains = fetch_recording_gains(
            data,
            stimulus_name=stimulus_name,
            cell_types=cell_types,
            strains=strains,
            min_steps=min_steps,
        )
    else:
        gains = data.copy()

    if abs_gain:
        gains = gains.assign(slope=gains["slope"].abs())

    fig, axes = plt.subplots(1, len(cell_types), figsize=figsize, sharey=abs_gain)
    if len(cell_types) == 1:
        axes = [axes]

    rng = np.random.default_rng(rng_seed)

    for ax, cell_type in zip(axes, cell_types, strict=True):
        sub = gains[gains["cell_type"] == cell_type]
        present_strains: list[str] = (
            list(strains) if strains is not None
            else sorted(sub["strain_name"].unique().tolist())
        )

        x_ticks = list(range(1, len(present_strains) + 1))
        for position, strain in zip(x_ticks, present_strains, strict=True):
            strain_data = sub[sub["strain_name"] == strain]
            if strain_data.empty:
                continue
            colour = STRAIN_COLOURS.get(strain, "#666666")
            raincloud(
                ax,
                strain_data["slope"].to_numpy(),
                position,
                color=colour,
                rng=rng,
                hemispheres=strain_data["hemisphere"].to_numpy(),
            )

        ax.axhline(0.0, color="#888888", linewidth=0.5, linestyle="--", zorder=0)
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(present_strains, rotation=30, ha="right", fontsize=8)
        ax.set_title(f"{cell_type} cells")
        ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)

    ylabel = (
        r"$|\mathrm{gain}|$ ($\Delta F / F_0$ per $^{\circ}$C)"
        if abs_gain
        else r"gain ($\Delta F / F_0$ per $^{\circ}$C)"
    )
    axes[0].set_ylabel(ylabel)

    if title is None and stimulus_name:
        title = f"Recording gains — {stimulus_name}"
    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper
# ─────────────────────────────────────────────────────────────────


@dataclass
class GainComparison:
    """Callable wrapper holding default styling.

    Mirrors :class:`arista.viz.response_curves.ResponseCurves` so the
    same orchestration pattern carries over to gain figures.
    """

    cell_types: tuple[str, ...] = ("CC", "HC")
    abs_gain: bool = False
    figsize: tuple[float, float] = (12, 5)
    dpi: int = FIGURE_DPI
    strains: tuple[str, ...] | None = None
    rng_seed: int = _DEFAULT_RNG_SEED
    min_steps: int = 3

    def plot(
        self,
        data: pd.DataFrame | sqlite3.Connection,
        *,
        stimulus_name: str | None = None,
        title: str | None = None,
        **overrides,
    ) -> Figure:
        kwargs = {
            "cell_types": self.cell_types,
            "abs_gain": self.abs_gain,
            "figsize": self.figsize,
            "strains": self.strains,
            "rng_seed": self.rng_seed,
            "min_steps": self.min_steps,
        }
        kwargs.update(overrides)
        return plot_gain_comparison(
            data, stimulus_name=stimulus_name, title=title, **kwargs
        )

    def __call__(
        self,
        data: pd.DataFrame | sqlite3.Connection,
        **kwargs,
    ) -> Figure:
        return self.plot(data, **kwargs)

    def save(
        self,
        fig: Figure,
        path: Path | str,
        *,
        dpi: int | None = None,
        close: bool = True,
    ) -> Path:
        """Save fig as PNG. SVG sibling is written automatically."""
        import matplotlib.pyplot as plt

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        png_path = path.with_suffix(".png")
        svg_path = path.with_suffix(".svg")
        fig.savefig(png_path, dpi=dpi or self.dpi)
        fig.savefig(svg_path)
        if close:
            plt.close(fig)
        return png_path
