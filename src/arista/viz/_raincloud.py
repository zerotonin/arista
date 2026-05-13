# ─────────────────────────────────────────────────────────────────
#  arista.viz._raincloud
#  « hand-rolled half-violin + box + strip primitive »
# ─────────────────────────────────────────────────────────────────
"""Raincloud plot primitive: half-violin + boxplot + jittered strip.

CLAUDE.md §7.3 mandates rainclouds over bar charts. We hand-roll the
primitive here rather than depending on ``ptitprince`` or ``seaborn``
to keep the package dependency footprint tight (no new third-party
deps for one figure family).

Layout per group::

    half-violin ◄─ │ ─► box ─► jittered strip
       (left)              (centre)        (right)

The half-violin is a KDE flipped so its density grows leftward from
the group's x-position. The boxplot sits on the group line. The
strip is a jittered scatter to the right, with optional
hemisphere-marker support (``<`` left, ``>`` right, ``o`` pooled).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

if TYPE_CHECKING:
    from matplotlib.axes import Axes


# ─────────────────────────────────────────────────────────────────
#  Primitives
# ─────────────────────────────────────────────────────────────────


def half_violin(
    ax: Axes,
    values: np.ndarray,
    position: float,
    *,
    side: str = "left",
    width: float = 0.35,
    color: str = "#888888",
    alpha: float = 0.5,
    kde_bw: float | str = "scott",
    n_grid: int = 200,
) -> None:
    """KDE drawn as a single-sided violin at ``x = position``.

    Silently no-ops when fewer than two finite values are supplied —
    a KDE needs spread to estimate from.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2 or np.allclose(values, values[0]):
        return
    kde = gaussian_kde(values, bw_method=kde_bw)
    y_grid = np.linspace(values.min(), values.max(), n_grid)
    density = kde(y_grid)
    density = density / density.max() * width
    if side == "left":
        ax.fill_betweenx(
            y_grid, position - density, position,
            color=color, alpha=alpha, linewidth=0,
        )
    else:
        ax.fill_betweenx(
            y_grid, position, position + density,
            color=color, alpha=alpha, linewidth=0,
        )


def boxplot_at(
    ax: Axes,
    values: np.ndarray,
    position: float,
    *,
    width: float = 0.12,
    color: str = "#222222",
    face_color: str = "#ffffff",
) -> None:
    """Thin boxplot at ``x = position``."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 1:
        return
    ax.boxplot(
        values,
        positions=[position],
        widths=width,
        showfliers=False,
        vert=True,
        patch_artist=True,
        boxprops={"facecolor": face_color, "edgecolor": color, "linewidth": 1.0},
        medianprops={"color": color, "linewidth": 1.4},
        whiskerprops={"color": color, "linewidth": 0.8},
        capprops={"color": color, "linewidth": 0.8},
    )


def jittered_strip(
    ax: Axes,
    values: np.ndarray,
    position: float,
    *,
    side: str = "right",
    width: float = 0.15,
    color: str = "#444444",
    marker: str = "o",
    size: float = 12.0,
    alpha: float = 0.7,
    rng: np.random.Generator | None = None,
    markers: np.ndarray | None = None,
) -> None:
    """Scatter of ``values`` jittered horizontally near ``position``.

    When ``markers`` is supplied it must have the same length as
    ``values``; points are then drawn one marker glyph at a time so
    hemisphere indicators (``<``, ``>``, ``o``) survive into the
    final figure.
    """
    if rng is None:
        rng = np.random.default_rng(0)
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    values = values[finite]
    if markers is not None:
        markers = np.asarray(markers)[finite]
    if len(values) == 0:
        return
    jitter = rng.uniform(0.0, width, size=len(values))
    x = position - jitter if side == "left" else position + jitter

    if markers is None:
        ax.scatter(
            x, values, c=color, s=size, alpha=alpha,
            marker=marker, edgecolors="none",
        )
        return

    for glyph in np.unique(markers):
        mask = markers == glyph
        ax.scatter(
            x[mask], values[mask], c=color, s=size, alpha=alpha,
            marker=str(glyph), edgecolors="none",
        )


# ─────────────────────────────────────────────────────────────────
#  Compound: raincloud
# ─────────────────────────────────────────────────────────────────


def raincloud(
    ax: Axes,
    values: np.ndarray,
    position: float,
    *,
    color: str,
    rng: np.random.Generator | None = None,
    hemispheres: np.ndarray | pd.Series | None = None,
    violin_width: float = 0.35,
    box_width: float = 0.12,
    strip_width: float = 0.15,
    strip_size: float = 12.0,
) -> None:
    """Half-violin (left) + boxplot (centre) + jittered strip (right).

    Args:
        ax: Target axes.
        values: 1-D array of values for the group.
        position: Group centre on the x-axis.
        color: Wong-palette hex for the violin and strip.
        rng: Optional ``np.random.Generator`` for reproducible jitter.
        hemispheres: Optional same-length array of ``"l"``/``"r"``/None
            labels. When supplied the strip uses ``<``/``>``/``o``
            markers instead of a single glyph.
        violin_width: Maximum half-width of the violin.
        box_width: Width of the boxplot.
        strip_width: Horizontal jitter range of the scatter.
        strip_size: Matplotlib ``s=`` for scatter markers.
    """
    from arista.constants import marker_for_hemisphere

    half_violin(
        ax, values, position,
        side="left", width=violin_width, color=color,
    )
    boxplot_at(ax, values, position, width=box_width)

    if hemispheres is not None:
        glyphs = np.array(
            [marker_for_hemisphere(h) for h in hemispheres],
            dtype=object,
        )
        jittered_strip(
            ax, values, position,
            side="right", width=strip_width, color=color,
            size=strip_size, rng=rng, markers=glyphs,
        )
    else:
        jittered_strip(
            ax, values, position,
            side="right", width=strip_width, color=color,
            size=strip_size, rng=rng,
        )
