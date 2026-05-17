# ─────────────────────────────────────────────────────────────────
#  arista.viz.adaptation_taus
#  « τ raincloud per strain × cell-type (Kossen 2019 Fig 21) »
# ─────────────────────────────────────────────────────────────────
"""Adaptation time-constant rainclouds.

Pulls ``adaptation_fits`` directly from the DB (already computed during
``arista-ingest --process``) and renders one figure per adaptation
stimulus, panel per cell type, raincloud per strain.

τ is positively skewed and bounded below at zero, so the y-axis
defaults to a log scale (``log_tau=True``). Toggle off for a linear
view. Median + IQR per group is read directly off the boxplot at the
centre of each raincloud — bootstrap CI of the median is *not*
shown here because each cell contributes a single τ value, not a
distribution that benefits from re-sampling.
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
from arista.viz._raincloud import raincloud

if TYPE_CHECKING:
    from matplotlib.figure import Figure


_DEFAULT_RNG_SEED: int = 19


# ─────────────────────────────────────────────────────────────────
#  Discovery + fetch
# ─────────────────────────────────────────────────────────────────


def discover_adaptation_stimuli(conn: sqlite3.Connection) -> list[str]:
    """Stimuli that produced ``adaptation_fits`` rows."""
    cur = conn.execute(
        """
        SELECT DISTINCT v.stimulus_name
        FROM adaptation_fits af
        JOIN v_recordings v ON v.recording_id = af.recording_id
        WHERE v.stimulus_family = 'thermal_adapt'
        ORDER BY v.stimulus_name
        """
    )
    return [row[0] for row in cur.fetchall()]


def fetch_adaptation_taus(
    conn: sqlite3.Connection,
    *,
    stimulus_name: str | None = None,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    min_r_squared: float | None = None,
) -> pd.DataFrame:
    """Per-recording τ values joined with v_recordings metadata.

    Args:
        conn: Open SQLite connection to a populated ``arista.db``.
        stimulus_name: Optional stimulus filter (one figure per
            stimulus in the typical batch workflow).
        cell_types: Cell types to include.
        strains: Optional strain whitelist.
        min_r_squared: Drop fits below this quality threshold; ``None``
            keeps every fit.

    Returns:
        DataFrame with one row per recording carrying ``recording_id,
        researcher_name, strain_name, cell_type, hemisphere,
        stimulus_name, tau_s, amplitude, asymptote, r_squared,
        n_points``.
    """
    placeholders = ",".join(["?"] * len(cell_types))
    query = f"""
        SELECT v.recording_id, v.researcher_name, v.strain_name, v.cell_type,
               v.hemisphere, v.stimulus_name,
               af.tau_s, af.amplitude, af.asymptote, af.r_squared,
               af.n_points
        FROM adaptation_fits af
        JOIN v_recordings v ON v.recording_id = af.recording_id
        WHERE v.stimulus_family = 'thermal_adapt'
          AND v.cell_type IN ({placeholders})
    """
    params: list = list(cell_types)
    if stimulus_name is not None:
        query += " AND v.stimulus_name = ?"
        params.append(stimulus_name)
    if strains is not None:
        strain_placeholders = ",".join(["?"] * len(strains))
        query += f" AND v.strain_name IN ({strain_placeholders})"
        params.extend(strains)
    if min_r_squared is not None:
        query += " AND af.r_squared >= ?"
        params.append(min_r_squared)
    return pd.read_sql_query(query, conn, params=params)


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def plot_adaptation_taus(
    data: pd.DataFrame | sqlite3.Connection,
    *,
    stimulus_name: str | None = None,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    log_tau: bool = True,
    figsize: tuple[float, float] = (12, 5),
    title: str | None = None,
    rng_seed: int = _DEFAULT_RNG_SEED,
    min_r_squared: float | None = None,
) -> Figure:
    """Raincloud of adaptation τ per strain × cell-type.

    Args:
        data: Either an already-fetched τ frame (output of
            :func:`fetch_adaptation_taus`) or a live SQLite connection.
        stimulus_name: Mandatory when ``data`` is a connection.
        cell_types: Cell types to plot, one panel per.
        strains: Optional strain whitelist (display order).
        log_tau: Plot τ on a log y-axis (default). τ is positively
            skewed and bounded below at zero so log is the natural
            view; toggle off for a linear inspection.
        figsize: ``(width, height)`` inches.
        title: Optional figure suptitle.
        rng_seed: Seed for the jitter RNG (reproducibility).
        min_r_squared: Forwarded to :func:`fetch_adaptation_taus`.

    Returns:
        :class:`matplotlib.figure.Figure`. Caller owns I/O.
    """
    import matplotlib.pyplot as plt

    if isinstance(data, sqlite3.Connection):
        if stimulus_name is None:
            raise ValueError(
                "stimulus_name is required when data is a Connection"
            )
        taus = fetch_adaptation_taus(
            data,
            stimulus_name=stimulus_name,
            cell_types=cell_types,
            strains=strains,
            min_r_squared=min_r_squared,
        )
    else:
        taus = data

    # Drop nonpositive τ values up front — they cannot be plotted on a
    # log axis and they're not physically meaningful for an adaptation
    # decay either.
    plot_taus = taus[taus["tau_s"] > 0].copy()

    fig, axes = plt.subplots(1, len(cell_types), figsize=figsize, sharey=True)
    if len(cell_types) == 1:
        axes = [axes]

    rng = np.random.default_rng(rng_seed)

    for ax, cell_type in zip(axes, cell_types, strict=True):
        sub = plot_taus[plot_taus["cell_type"] == cell_type]
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
                strain_data["tau_s"].to_numpy(),
                position,
                color=colour,
                rng=rng,
                hemispheres=strain_data["hemisphere"].to_numpy(),
            )

        if log_tau:
            ax.set_yscale("log")
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(present_strains, rotation=30, ha="right", fontsize=8)
        ax.set_title(f"{cell_type} cells")
        ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)

    axes[0].set_ylabel(r"adaptation $\tau$ (s)")

    if title is None and stimulus_name:
        title = f"Adaptation τ — {stimulus_name}"
    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper
# ─────────────────────────────────────────────────────────────────


@dataclass
class AdaptationTaus:
    """Callable wrapper holding default styling."""

    cell_types: tuple[str, ...] = ("CC", "HC")
    log_tau: bool = True
    figsize: tuple[float, float] = (12, 5)
    dpi: int = FIGURE_DPI
    strains: tuple[str, ...] | None = None
    rng_seed: int = _DEFAULT_RNG_SEED
    min_r_squared: float | None = None

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
            "log_tau": self.log_tau,
            "figsize": self.figsize,
            "strains": self.strains,
            "rng_seed": self.rng_seed,
            "min_r_squared": self.min_r_squared,
        }
        kwargs.update(overrides)
        return plot_adaptation_taus(
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
