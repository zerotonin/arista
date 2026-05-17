# ─────────────────────────────────────────────────────────────────
#  arista.viz.sigmoid_fits
#  « per-strain × cell-type 4PL sigmoid panels (Kossen Fig 24/25) »
# ─────────────────────────────────────────────────────────────────
"""Sigmoid-fit overlay of the response curves.

One panel per cell type. Within each panel: a light scatter of every
(Δtarget, ΔF/F) point in the response frame, overlaid with one fitted
4PL sigmoid per strain. Per-strain colours come from
:data:`arista.constants.STRAIN_COLOURS` so the same strain reads the
same across response_curves / gain_comparison / sigmoid_fits panels.

For groups too sparse / flat to fit, the scatter still appears but no
curve is drawn — failure is silent, not an exception, so the figure
still renders for the full corpus.
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
from arista.processing.sigmoid import fit_sigmoid, four_pl
from arista.viz.response_curves import fetch_response_data

if TYPE_CHECKING:
    from matplotlib.figure import Figure


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def plot_sigmoid_fits(
    data: pd.DataFrame | sqlite3.Connection,
    *,
    stimulus_name: str | None = None,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    figsize: tuple[float, float] = (10, 5),
    title: str | None = None,
    n_curve: int = 200,
    scatter_alpha: float = 0.18,
    scatter_size: float = 8.0,
) -> Figure:
    """One panel per cell type; one fitted sigmoid per strain.

    Args:
        data: Either an already-fetched response frame (output of
            :func:`fetch_response_data`) or a live SQLite connection.
        stimulus_name: Mandatory when ``data`` is a connection.
        cell_types: Cell types to plot, one panel per.
        strains: Optional strain whitelist.
        figsize: ``(width, height)`` inches.
        title: Optional figure suptitle (auto from ``stimulus_name``).
        n_curve: Number of x-samples in each plotted sigmoid line.
        scatter_alpha: Per-point alpha for the underlying scatter.
        scatter_size: Per-point marker area for the scatter.

    Returns:
        :class:`matplotlib.figure.Figure`. Caller owns I/O.
    """
    import matplotlib.pyplot as plt

    if isinstance(data, sqlite3.Connection):
        if stimulus_name is None:
            raise ValueError(
                "stimulus_name is required when data is a Connection"
            )
        df = fetch_response_data(
            data, stimulus_name=stimulus_name,
            cell_types=cell_types, strains=strains,
        )
    else:
        df = data

    fig, axes = plt.subplots(1, len(cell_types), figsize=figsize, sharey=True)
    if len(cell_types) == 1:
        axes = [axes]

    for ax, cell_type in zip(axes, cell_types, strict=True):
        sub = df[df["cell_type"] == cell_type]
        if sub.empty:
            ax.text(
                0.5, 0.5, f"no data for {cell_type}",
                transform=ax.transAxes, ha="center", va="center",
                color="#888888",
            )
        for strain in sorted(sub["strain_name"].unique()):
            strain_data = sub[sub["strain_name"] == strain]
            x = strain_data["delta_target_c"].to_numpy(dtype=float)
            y = strain_data["dfbf_response_median"].to_numpy(dtype=float)
            colour = STRAIN_COLOURS.get(strain, "#666666")

            ax.scatter(
                x, y, color=colour,
                s=scatter_size, alpha=scatter_alpha,
                edgecolors="none",
            )
            fit = fit_sigmoid(x, y)
            if fit is None:
                continue
            x_curve = np.linspace(x.min(), x.max(), n_curve)
            y_curve = four_pl(
                x_curve, fit.bottom, fit.top,
                fit.midpoint_c, fit.slope,
            )
            label = f"{strain} (R²={fit.r_squared:.2f}, n={fit.n_points})"
            ax.plot(
                x_curve, y_curve,
                color=colour, linewidth=1.6, label=label,
            )

        ax.set_title(f"{cell_type} cells")
        ax.axhline(0.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
        ax.axvline(0.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
        ax.set_xlabel(r"$\Delta$ target T (°C from baseline)")
        ax.legend(loc="best", fontsize=7, framealpha=0.85)
        ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)

    axes[0].set_ylabel(r"$\Delta F / F_0$")

    if title is None and stimulus_name:
        title = f"Sigmoid fits — {stimulus_name}"
    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper
# ─────────────────────────────────────────────────────────────────


@dataclass
class SigmoidFits:
    """Callable wrapper holding default styling.

    Mirrors :class:`arista.viz.response_curves.ResponseCurves`.
    """

    cell_types: tuple[str, ...] = ("CC", "HC")
    figsize: tuple[float, float] = (10, 5)
    dpi: int = FIGURE_DPI
    strains: tuple[str, ...] | None = None
    n_curve: int = 200
    scatter_alpha: float = 0.18
    scatter_size: float = 8.0

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
            "figsize": self.figsize,
            "strains": self.strains,
            "n_curve": self.n_curve,
            "scatter_alpha": self.scatter_alpha,
            "scatter_size": self.scatter_size,
        }
        kwargs.update(overrides)
        return plot_sigmoid_fits(
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
