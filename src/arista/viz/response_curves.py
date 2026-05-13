# ─────────────────────────────────────────────────────────────────
#  arista.viz.response_curves
#  « median ΔF/F + 95% bootstrap CI per (strain × cell_type) per step »
# ─────────────────────────────────────────────────────────────────
"""Reproduce Kossen 2019 Fig 19 / 22-23: response curves per strain × cell-type.

One panel per cell type (CC / HC, optionally WC). Within each panel
one line per strain, x-axis is ``delta_target_c`` (step target minus
22 °C baseline) or absolute ``target_temp_c``, y-axis is the per-step
median ΔF/F across recordings of that strain × cell_type.

Error band is **median ± 95% bootstrap CI of the median** by default —
non-parametric, no assumption of normality. The fallback ``error="iqr"``
mode plots median + interquartile range. The parametric ``error="sem"``
mode (mean ± SEM) runs a Shapiro-Wilk normality test per x-value and
silently downgrades to the CI band with a warning if any group rejects
normality at α = 0.05. This matches Bart's standing rule: median-based
summaries by default, parametric only after normality is checked.

Colours come from :data:`arista.constants.STRAIN_COLOURS`. The class
:class:`ResponseCurves` carries default styling for batch reuse; the
free function :func:`plot_response_curves` is the primary one-off API.
"""

from __future__ import annotations

import sqlite3
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from arista.constants import (
    FIGURE_DPI,
    STRAIN_COLOURS,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure


ErrorBand = Literal["ci", "iqr", "sem", "none"]

#: Minimum frames-in-window for a stimulus_responses row to qualify as
#: "well-matched". Filters out the Alex protocol-mismatch rows where
#: the sensor only briefly touched the target window.
_MIN_FRAMES_IN_WINDOW: int = 50

#: Bootstrap parameters for the 95% CI of the median.
_DEFAULT_N_BOOTSTRAP: int = 2000
_DEFAULT_CONFIDENCE_LEVEL: float = 0.95
_DEFAULT_RNG_SEED: int = 42

#: Shapiro-Wilk significance threshold for the parametric ``sem`` mode.
_SHAPIRO_ALPHA: float = 0.05


# ─────────────────────────────────────────────────────────────────
#  Data fetch
# ─────────────────────────────────────────────────────────────────


def fetch_response_data(
    conn: sqlite3.Connection,
    *,
    stimulus_name: str,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    min_frames_in_window: int = _MIN_FRAMES_IN_WINDOW,
) -> pd.DataFrame:
    """JOIN ``stimulus_responses`` with ``v_recordings`` and filter.

    Args:
        conn: Open SQLite connection to a populated ``arista.db``.
        stimulus_name: Canonical stimulus protocol name (``"ascAmp"``,
            ``"descAmp"``, …).
        cell_types: Which cell types to include.
        strains: Optional whitelist of canonical strain names; ``None``
            means "every strain that has matching responses".
        min_frames_in_window: Drop rows that medianed over fewer than
            this many frames — filters Alex's protocol-mismatch cases
            where the sensor barely touched a step's target window.

    Returns:
        DataFrame with one row per (recording, step).
    """
    placeholders = ",".join(["?"] * len(cell_types))
    query = f"""
        SELECT v.recording_id, v.researcher_name, v.strain_name, v.cell_type,
               v.cell_number, v.hemisphere, v.animal_number,
               sr.step_index, sr.target_temp_c, sr.delta_target_c,
               sr.dfbf_response_median, sr.observed_temp_median,
               sr.n_frames_in_window
        FROM stimulus_responses sr
        JOIN v_recordings v ON v.recording_id = sr.recording_id
        WHERE v.stimulus_name = ?
          AND v.cell_type IN ({placeholders})
          AND sr.n_frames_in_window >= ?
    """
    params: list = [stimulus_name, *cell_types, min_frames_in_window]
    if strains is not None:
        strain_placeholders = ",".join(["?"] * len(strains))
        query += f" AND v.strain_name IN ({strain_placeholders})"
        params.extend(strains)
    return pd.read_sql_query(query, conn, params=params)


# ─────────────────────────────────────────────────────────────────
#  Aggregation: median + bootstrap CI + Shapiro-Wilk
# ─────────────────────────────────────────────────────────────────


def _bootstrap_median_ci(
    values: np.ndarray,
    *,
    n_resamples: int,
    confidence_level: float,
    rng: np.random.Generator,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the median of ``values``."""
    n = len(values)
    if n < 2:
        v = float(values[0]) if n == 1 else float("nan")
        return (v, v)
    indices = rng.integers(0, n, size=(n_resamples, n))
    boot_medians = np.median(values[indices], axis=1)
    alpha = (1.0 - confidence_level) / 2.0
    low = float(np.quantile(boot_medians, alpha))
    high = float(np.quantile(boot_medians, 1.0 - alpha))
    return (low, high)


def _shapiro_p(values: np.ndarray) -> float:
    """Shapiro-Wilk p; NaN when n < 3 or when scipy refuses."""
    if len(values) < 3:
        return float("nan")
    from scipy.stats import shapiro
    try:
        return float(shapiro(values).pvalue)
    except Exception:
        return float("nan")


def _aggregate_group(
    values: pd.Series,
    *,
    n_bootstrap: int,
    confidence_level: float,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Compute median + bootstrap CI + IQR + mean + SEM + Shapiro p + n."""
    x = values.dropna().to_numpy(dtype=float)
    n = len(x)
    if n == 0:
        return {
            "median": np.nan, "ci_low": np.nan, "ci_high": np.nan,
            "q25": np.nan, "q75": np.nan,
            "mean": np.nan, "sem": np.nan, "shapiro_p": np.nan,
            "n": 0,
        }
    ci_low, ci_high = _bootstrap_median_ci(
        x, n_resamples=n_bootstrap,
        confidence_level=confidence_level, rng=rng,
    )
    sem = float(np.std(x, ddof=1) / np.sqrt(n)) if n >= 2 else float("nan")
    return {
        "median": float(np.median(x)),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "q25": float(np.quantile(x, 0.25)),
        "q75": float(np.quantile(x, 0.75)),
        "mean": float(np.mean(x)),
        "sem": sem,
        "shapiro_p": _shapiro_p(x),
        "n": int(n),
    }


def aggregate_response_data(
    df: pd.DataFrame,
    *,
    by_x: str = "delta_target_c",
    n_bootstrap: int = _DEFAULT_N_BOOTSTRAP,
    confidence_level: float = _DEFAULT_CONFIDENCE_LEVEL,
    rng_seed: int = _DEFAULT_RNG_SEED,
) -> pd.DataFrame:
    """Per (strain, cell_type, x) compute centre + spread + n.

    The output carries enough columns to render any of the four
    supported error bands (``ci`` / ``iqr`` / ``sem`` / ``none``)
    without re-aggregating:

    - ``median, ci_low, ci_high`` — non-parametric default. CI is the
      percentile bootstrap CI of the median at ``confidence_level``
      (default 0.95). Resampled ``n_bootstrap`` times (default 2000)
      from a seeded ``np.random.Generator``.
    - ``q25, q75`` — interquartile range (legacy ``error="iqr"`` mode).
    - ``mean, sem`` — for the parametric ``error="sem"`` mode.
    - ``shapiro_p`` — per-group Shapiro-Wilk p (NaN when n<3); used
      by the plot layer to gate ``error="sem"``.
    - ``n`` — recordings contributing to this (strain, cell_type, x)
      bucket.

    Args:
        df: Output of :func:`fetch_response_data`.
        by_x: ``"delta_target_c"`` (default, Kossen-style relative
            amplitude) or ``"target_temp_c"`` (absolute temperature).
        n_bootstrap: Number of bootstrap resamples for the median CI.
        confidence_level: CI coverage (default 0.95).
        rng_seed: Seed for the bootstrap RNG (reproducibility).
    """
    columns = [
        "strain_name", "cell_type", by_x, "n",
        "median", "ci_low", "ci_high",
        "q25", "q75",
        "mean", "sem", "shapiro_p",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    rng = np.random.default_rng(rng_seed)
    rows: list[dict] = []
    for (strain, cell_type, x_val), group_df in df.groupby(
        ["strain_name", "cell_type", by_x]
    ):
        row: dict = {"strain_name": strain, "cell_type": cell_type, by_x: x_val}
        row.update(_aggregate_group(
            group_df["dfbf_response_median"],
            n_bootstrap=n_bootstrap,
            confidence_level=confidence_level,
            rng=rng,
        ))
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


# ─────────────────────────────────────────────────────────────────
#  Plot
# ─────────────────────────────────────────────────────────────────


def _band_for_strain(
    strain_data: pd.DataFrame,
    *,
    error: ErrorBand,
    label: str,
    shapiro_alpha: float,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None, str]:
    """Return ``(centre, lower, upper, centre_kind)`` for one strain.

    ``centre_kind`` is either ``"median"`` or ``"mean"`` (drives the
    y-axis label). When ``error == "sem"`` and Shapiro-Wilk rejects
    normality at any x-value the band silently downgrades to
    median + CI and emits a runtime warning naming the strain.
    """
    median = strain_data["median"].to_numpy()
    if error == "ci":
        return median, strain_data["ci_low"].to_numpy(), strain_data["ci_high"].to_numpy(), "median"
    if error == "iqr":
        return median, strain_data["q25"].to_numpy(), strain_data["q75"].to_numpy(), "median"
    if error == "none":
        return median, None, None, "median"

    # error == "sem": gated by Shapiro-Wilk
    shapiro_p = strain_data["shapiro_p"].to_numpy()
    finite = np.isfinite(shapiro_p)
    rejected = (shapiro_p < shapiro_alpha) & finite
    if np.any(rejected):
        warnings.warn(
            f"{label}: Shapiro-Wilk rejected normality at "
            f"{int(rejected.sum())} of {int(finite.sum())} x-values "
            f"(p < {shapiro_alpha}); falling back to median + 95% CI.",
            RuntimeWarning,
            stacklevel=3,
        )
        return median, strain_data["ci_low"].to_numpy(), strain_data["ci_high"].to_numpy(), "median"
    mean = strain_data["mean"].to_numpy()
    sem = strain_data["sem"].to_numpy()
    return mean, mean - sem, mean + sem, "mean"


def plot_response_curves(
    data: pd.DataFrame | sqlite3.Connection,
    *,
    stimulus_name: str | None = None,
    strains: tuple[str, ...] | None = None,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    by_x: str = "delta_target_c",
    error: ErrorBand = "ci",
    figsize: tuple[float, float] = (10, 5),
    title: str | None = None,
    shapiro_alpha: float = _SHAPIRO_ALPHA,
) -> Figure:
    """Two-panel response curve figure: one panel per cell type.

    Args:
        data: Either an already-fetched DataFrame (output of
            :func:`fetch_response_data`) or a live SQLite connection.
            When a connection is passed ``stimulus_name`` becomes
            mandatory.
        stimulus_name: Stimulus protocol name (when fetching from DB).
        strains: Optional strain whitelist.
        cell_types: Cell types to plot, one panel per.
        by_x: ``"delta_target_c"`` (Kossen's relative-amplitude axis,
            default) or ``"target_temp_c"`` (absolute).
        error: Error band mode. ``"ci"`` (default, median + 95%
            bootstrap CI of the median), ``"iqr"`` (median + IQR),
            ``"sem"`` (mean + SEM, gated by per-x Shapiro-Wilk; falls
            back to ``"ci"`` with a warning on non-normality), or
            ``"none"``.
        figsize: ``(width, height)`` inches.
        title: Figure suptitle. Auto-generated from ``stimulus_name``
            when ``None``.
        shapiro_alpha: Normality rejection threshold for the ``"sem"``
            mode (default 0.05).

    Returns:
        :class:`matplotlib.figure.Figure`. The caller owns I/O.
    """
    import matplotlib.pyplot as plt

    if isinstance(data, sqlite3.Connection):
        if stimulus_name is None:
            raise ValueError(
                "stimulus_name is required when data is a Connection"
            )
        df = fetch_response_data(
            data,
            stimulus_name=stimulus_name,
            cell_types=cell_types,
            strains=strains,
        )
    else:
        df = data

    agg = aggregate_response_data(df, by_x=by_x)

    fig, axes = plt.subplots(1, len(cell_types), figsize=figsize, sharey=True)
    if len(cell_types) == 1:
        axes = [axes]

    centre_kinds: set[str] = set()
    for ax, cell_type in zip(axes, cell_types, strict=True):
        sub = agg[agg["cell_type"] == cell_type]
        if sub.empty:
            ax.text(
                0.5, 0.5, f"no data for {cell_type}",
                transform=ax.transAxes, ha="center", va="center",
                color="#888888",
            )
        for strain in sorted(sub["strain_name"].unique()):
            strain_data = sub[sub["strain_name"] == strain].sort_values(by_x)
            colour = STRAIN_COLOURS.get(strain, "#666666")
            n_label = int(strain_data["n"].max())
            label = f"{strain} (n≤{n_label})"

            centre, lower, upper, kind = _band_for_strain(
                strain_data,
                error=error,
                label=f"{strain}/{cell_type}",
                shapiro_alpha=shapiro_alpha,
            )
            centre_kinds.add(kind)

            x = strain_data[by_x].to_numpy()
            ax.plot(
                x, centre, color=colour, marker="o",
                linewidth=1.4, markersize=4, label=label,
            )
            if lower is not None and upper is not None:
                ax.fill_between(
                    x, lower, upper,
                    color=colour, alpha=0.18, linewidth=0,
                )

        ax.set_title(f"{cell_type} cells")
        ax.axhline(0.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
        ax.axvline(0.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
        ax.set_xlabel(
            r"$\Delta$ target T (°C from baseline)"
            if by_x == "delta_target_c"
            else "target T (°C)"
        )
        ax.legend(loc="best", fontsize=7, framealpha=0.85)
        ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)

    ylabel_centre = "mean" if centre_kinds == {"mean"} else "median"
    band_label = {
        "ci":   " (median ± 95% CI)",
        "iqr":  " (median ± IQR)",
        "sem":  " (mean ± SEM)" if ylabel_centre == "mean" else " (median ± 95% CI)",
        "none": "",
    }[error]
    axes[0].set_ylabel(
        rf"{ylabel_centre} $\Delta F / F_0$" + band_label
    )

    if title is None and stimulus_name:
        title = f"Response curves — {stimulus_name}"
    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper for batch reuse
# ─────────────────────────────────────────────────────────────────


@dataclass
class ResponseCurves:
    """Callable wrapper holding default styling.

    Useful when rendering many figures (one per stimulus protocol) with
    consistent kwargs::

        plotter = ResponseCurves(figsize=(12, 5))
        for stim in ("ascAmp", "descAmp"):
            fig = plotter(conn, stimulus_name=stim)
            plotter.save(fig, output_dir / f"resp_{stim}.png")
    """

    cell_types: tuple[str, ...] = ("CC", "HC")
    by_x: str = "delta_target_c"
    error: ErrorBand = "ci"
    figsize: tuple[float, float] = (10, 5)
    dpi: int = FIGURE_DPI
    strains: tuple[str, ...] | None = None

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
            "by_x": self.by_x,
            "error": self.error,
            "figsize": self.figsize,
            "strains": self.strains,
        }
        kwargs.update(overrides)
        return plot_response_curves(
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
