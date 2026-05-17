# ─────────────────────────────────────────────────────────────────
#  arista.viz.nompc_dosage
#  « publication headline: gain vs NompC functional dosage »
# ─────────────────────────────────────────────────────────────────
"""Phase 7d headline figure — |gain| (or signed gain) vs NompC dosage.

For every thermal_step protocol we already have per-recording gains
(``arista.processing.gain.compute_recording_gain``). This module pools
gains across protocols, canonicalises strain names through
:data:`arista.constants.STRAIN_SYNONYMS`, looks up the functional
NompC dosage per strain via :data:`arista.constants.NOMPC_DOSAGE`,
and draws one raincloud per strain at its dosage x-position. One
panel per cell type.

Strains sharing the same dosage tier (CantonS / white / 641 at 2.0,
NompCRescue / UASnompC… also at 2.0 — though the latter alias is
canonicalised to NompCRescue before plotting) get small symmetric
x-offsets so their rainclouds don't overlap; their colours come from
:data:`arista.constants.STRAIN_COLOURS` so the legend disambiguates.

Recordings whose strain is not in ``NOMPC_DOSAGE`` are dropped with a
console-visible message; the dosage figure is by definition only
meaningful for strains with a defined functional level.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from arista.constants import (
    FIGURE_DPI,
    NOMPC_DOSAGE,
    STRAIN_COLOURS,
)
from arista.viz._raincloud import raincloud
from arista.viz.gain_comparison import fetch_recording_gains

if TYPE_CHECKING:
    from matplotlib.figure import Figure


#: Default stimulus protocols pooled together for the headline figure.
DEFAULT_DOSAGE_STIMULI: tuple[str, ...] = (
    "ascAmp", "descAmp", "ascAmpFlip", "descAmpFlip",
)

_DEFAULT_RNG_SEED: int = 23

#: Maximum horizontal spread when multiple strains share a dosage tier.
_INTRA_TIER_SPREAD: float = 0.28

#: Display-canonical name per cross-student alias. Kept local to this
#: module so :data:`arista.constants.STRAIN_SYNONYMS` stays the
#: ingest-time invariant (Laurin's filename parser stores
#: ``nompC_hom`` etc. verbatim and we don't rewrite that on read).
_DOSAGE_CANONICAL_NAME: dict[str, str] = {
    "nompC_hom": "NompC3",
    "nompC_het": "NompC-HeterozControl",
    "UASnompC_UASGCaMP-Gr28bd_Gal4-arista": "NompCRescue",
}


# ─────────────────────────────────────────────────────────────────
#  Data fetch
# ─────────────────────────────────────────────────────────────────


def _canonicalise(strain_name: str) -> str:
    """Collapse cross-student aliases to one display name per dosage group."""
    return _DOSAGE_CANONICAL_NAME.get(strain_name, strain_name)


def fetch_dosage_gains(
    conn: sqlite3.Connection,
    *,
    stimulus_names: tuple[str, ...] = DEFAULT_DOSAGE_STIMULI,
    cell_types: tuple[str, ...] = ("CC", "HC"),
) -> pd.DataFrame:
    """Per-recording gains pooled across stimuli, canonicalised + dosage-tagged.

    Args:
        conn: Open SQLite connection to a populated ``arista.db``.
        stimulus_names: Thermal_step protocols to pool. Defaults to all
            four ramp stimuli.
        cell_types: Cell types to include.

    Returns:
        DataFrame with one row per (recording, stimulus) carrying the
        original gain columns plus ``canonical_strain`` and ``dosage``.
        Rows whose strain has no entry in :data:`NOMPC_DOSAGE` are
        dropped.
    """
    pieces: list[pd.DataFrame] = []
    for stim in stimulus_names:
        piece = fetch_recording_gains(
            conn, stimulus_name=stim, cell_types=cell_types,
        )
        if piece.empty:
            continue
        piece = piece.copy()
        piece["stimulus_name"] = stim
        pieces.append(piece)
    if not pieces:
        return pd.DataFrame(columns=[
            "recording_id", "strain_name", "canonical_strain", "dosage",
            "cell_type", "hemisphere", "stimulus_name",
            "slope", "intercept", "r_squared", "n_points",
        ])
    df = pd.concat(pieces, ignore_index=True)
    df["canonical_strain"] = df["strain_name"].apply(_canonicalise)
    df["dosage"] = df["canonical_strain"].map(NOMPC_DOSAGE)
    return df.dropna(subset=["dosage"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def _strain_x_positions(
    canonical_strains: list[str],
    *,
    intra_tier_spread: float = _INTRA_TIER_SPREAD,
) -> dict[str, float]:
    """Place each strain on the x-axis at its dosage, spread within tier.

    Strains sharing a dosage tier are offset by up to ±``intra_tier_spread/2``
    so their rainclouds don't overlap.
    """
    tier_to_strains: dict[float, list[str]] = defaultdict(list)
    for s in canonical_strains:
        d = NOMPC_DOSAGE.get(s)
        if d is None:
            continue
        tier_to_strains[d].append(s)

    positions: dict[str, float] = {}
    for dose, strains in tier_to_strains.items():
        n = len(strains)
        if n == 1:
            positions[strains[0]] = dose
            continue
        offsets = np.linspace(
            -intra_tier_spread / 2, intra_tier_spread / 2, n,
        )
        for s, off in zip(sorted(strains), offsets, strict=True):
            positions[s] = dose + float(off)
    return positions


def plot_nompc_dosage(
    data: pd.DataFrame | sqlite3.Connection,
    *,
    stimulus_names: tuple[str, ...] = DEFAULT_DOSAGE_STIMULI,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    abs_gain: bool = True,
    figsize: tuple[float, float] = (12, 5.5),
    title: str | None = None,
    rng_seed: int = _DEFAULT_RNG_SEED,
    connect_tiers: bool = True,
) -> Figure:
    """One panel per cell type, raincloud per strain at its NompC dosage.

    Args:
        data: Either an already-fetched dosage-gain frame (output of
            :func:`fetch_dosage_gains`) or a live SQLite connection.
        stimulus_names: Thermal-step protocols to pool when fetching
            from a connection.
        cell_types: Cell types to plot, one panel per.
        abs_gain: Plot ``|slope|`` (default, makes CC and HC comparable
            and reads as "how much does the cell care about temperature
            change"). Set ``False`` to preserve sign.
        figsize: ``(width, height)`` inches.
        title: Optional suptitle.
        rng_seed: Seed for the raincloud jitter RNG.
        connect_tiers: When ``True``, overlays a thin median-vs-dosage
            line connecting tier centres so the dose-response trend is
            visible at a glance.

    Returns:
        :class:`matplotlib.figure.Figure`. Caller owns I/O.
    """
    import matplotlib.pyplot as plt

    if isinstance(data, sqlite3.Connection):
        df = fetch_dosage_gains(
            data, stimulus_names=stimulus_names, cell_types=cell_types,
        )
    else:
        df = data

    if abs_gain:
        df = df.assign(gain=df["slope"].abs())
    else:
        df = df.assign(gain=df["slope"])

    fig, axes = plt.subplots(
        1, len(cell_types), figsize=figsize, sharey=abs_gain,
    )
    if len(cell_types) == 1:
        axes = [axes]

    rng = np.random.default_rng(rng_seed)

    for ax, cell_type in zip(axes, cell_types, strict=True):
        sub = df[df["cell_type"] == cell_type]
        if sub.empty:
            ax.text(
                0.5, 0.5, f"no data for {cell_type}",
                transform=ax.transAxes, ha="center", va="center",
                color="#888888",
            )
            continue

        present = sorted(sub["canonical_strain"].unique())
        positions = _strain_x_positions(present)

        for strain in present:
            strain_data = sub[sub["canonical_strain"] == strain]
            if strain_data.empty or strain not in positions:
                continue
            colour = STRAIN_COLOURS.get(strain, "#666666")
            raincloud(
                ax,
                strain_data["gain"].to_numpy(),
                positions[strain],
                color=colour,
                rng=rng,
                hemispheres=strain_data["hemisphere"].to_numpy(),
                violin_width=0.10,
                box_width=0.05,
                strip_width=0.06,
            )

        # Dose-response trend: median |gain| at each tier
        if connect_tiers:
            tier_medians = (
                sub.groupby("dosage")["gain"]
                .median()
                .sort_index()
            )
            if len(tier_medians) >= 2:
                ax.plot(
                    tier_medians.index, tier_medians.values,
                    color="#555555", linewidth=1.0,
                    linestyle="--", alpha=0.6, zorder=1,
                    label="tier median",
                )

        ax.set_title(f"{cell_type} cells")
        ax.set_xlabel("NompC functional dosage")
        ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)

        # x-tick at every dosage tier present, with strain label group
        tier_to_strains: dict[float, list[str]] = defaultdict(list)
        for s in present:
            d = NOMPC_DOSAGE.get(s)
            if d is not None:
                tier_to_strains[d].append(s)
        xticks = sorted(tier_to_strains.keys())
        ax.set_xticks(xticks)
        ax.set_xticklabels([f"{t:g}" for t in xticks])
        if not abs_gain:
            ax.axhline(
                0.0, color="#cccccc", linewidth=0.5,
                linestyle="--", zorder=0,
            )

        # Strain legend per panel (top-right) since colour-by-strain is
        # the primary disambiguator within a tier.
        legend_handles = []
        from matplotlib.lines import Line2D
        for strain in present:
            colour = STRAIN_COLOURS.get(strain, "#666666")
            legend_handles.append(
                Line2D(
                    [0], [0], marker="o", color="w",
                    markerfacecolor=colour, markersize=6,
                    label=strain,
                )
            )
        ax.legend(handles=legend_handles, loc="best",
                  fontsize=7, framealpha=0.85)

    axes[0].set_ylabel(
        r"$|\mathrm{gain}|$ ($\Delta F / F_0$ per $^{\circ}$C)"
        if abs_gain
        else r"gain ($\Delta F / F_0$ per $^{\circ}$C)"
    )

    if title is None:
        title = "NompC dosage — recording gains pooled across ramp protocols"
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper
# ─────────────────────────────────────────────────────────────────


@dataclass
class NompCDosage:
    """Callable wrapper for batch reuse."""

    cell_types: tuple[str, ...] = ("CC", "HC")
    stimulus_names: tuple[str, ...] = DEFAULT_DOSAGE_STIMULI
    abs_gain: bool = True
    figsize: tuple[float, float] = (12, 5.5)
    dpi: int = FIGURE_DPI
    rng_seed: int = _DEFAULT_RNG_SEED
    connect_tiers: bool = True

    def plot(
        self,
        data: pd.DataFrame | sqlite3.Connection,
        *,
        title: str | None = None,
        **overrides,
    ) -> Figure:
        kwargs = {
            "cell_types": self.cell_types,
            "stimulus_names": self.stimulus_names,
            "abs_gain": self.abs_gain,
            "figsize": self.figsize,
            "rng_seed": self.rng_seed,
            "connect_tiers": self.connect_tiers,
        }
        kwargs.update(overrides)
        return plot_nompc_dosage(data, title=title, **kwargs)

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
