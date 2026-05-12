# ─────────────────────────────────────────────────────────────────
#  arista.viz.recording_overview
#  « dual-y-axis session plot: temperature ↔ ΔF/F per cell »
# ─────────────────────────────────────────────────────────────────
"""Plot a multi-cell recording session as a dual-y-axis figure.

One panel per session. The left axis carries temperature (target T
solid, sensor T overlaid thin); the right axis carries ΔF/F₀ per cell.
Cells are colour-coded by type (CC / HC / WC) and graded by cell
number within type, using the colourblind-safe palettes in
:mod:`arista.constants`.

The same callable is used by ``scripts/preprocess_alex_data.py`` to
produce a per-session overview PNG during preprocessing and will be
reused by the future database-backed display layer — both consume
the same :class:`arista.preprocess.Recording` dataclass, so any
data source that loads into a Recording is plottable through this
module.

API:

* :func:`plot_session_overview` — pure function, primary surface
* :class:`SessionOverview` — class wrapper carrying default kwargs,
  useful when many sessions are plotted with the same styling
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from arista.constants import (
    FIGURE_DPI,
    colour_for_cell,
    infer_cell_type_from_filename,
)
from arista.preprocess.io import Recording

if TYPE_CHECKING:
    from matplotlib.figure import Figure


# ─────────────────────────────────────────────────────────────────
#  Function API  « primary surface »
# ─────────────────────────────────────────────────────────────────


def plot_session_overview(
    recordings: dict[str, Recording],
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 5),
    use_drift_corrected: bool = True,
    show_target: bool = True,
    show_sensor: bool = True,
    sensor_alpha: float = 0.55,
    cell_linewidth: float = 1.0,
) -> Figure:
    """Plot one recording session as a dual-y-axis figure.

    Args:
        recordings: Mapping ``cell_label → Recording``. The label is
            the Fiji ROI filename stem (e.g. ``"l_CC01"``, ``"HC02"``),
            used both for the legend and for inferring the cell type
            via :func:`arista.constants.infer_cell_type_from_filename`.
        title: Figure suptitle. Typically the recording-directory path.
        figsize: ``(width, height)`` in inches.
        use_drift_corrected: If ``True`` (default) and a recording
            carries ``dfbf_drift_corrected``, plot that; otherwise
            fall back to the raw ``dfbf``.
        show_target: Plot the target (set-point) temperature trace.
        show_sensor: Overlay the measured sensor temperature trace.
        sensor_alpha: Opacity of the sensor overlay.
        cell_linewidth: Stroke width of each cell's ΔF/F trace.

    Returns:
        The :class:`matplotlib.figure.Figure`. The caller is
        responsible for ``savefig`` / ``plt.close`` — keeping I/O out
        of this function lets the same code run in batch scripts,
        notebooks, and the future GUI layer.

    Raises:
        ValueError: If ``recordings`` is empty.
    """
    import matplotlib.pyplot as plt  # lazy: keep module import light

    if not recordings:
        raise ValueError("plot_session_overview needs at least one Recording")

    fig, ax_temp = plt.subplots(figsize=figsize)
    ax_dfbf = ax_temp.twinx()

    # Share the first recording's time + temperature traces as the
    # session-wide stimulus context. All cells in one session were
    # imaged simultaneously under the same Peltier control loop, so
    # any one of them carries the canonical trace.
    first_rec = next(iter(recordings.values()))

    temp_lines = []
    if show_target:
        (line,) = ax_temp.plot(
            first_rec.time_s,
            first_rec.target_t_c,
            color="#222222",
            linewidth=1.4,
            linestyle="-",
            label="target T",
            zorder=2,
        )
        temp_lines.append(line)
    if show_sensor:
        (line,) = ax_temp.plot(
            first_rec.time_s,
            first_rec.sensor_t_c,
            color="#666666",
            linewidth=0.7,
            alpha=sensor_alpha,
            label="sensor T",
            zorder=1,
        )
        temp_lines.append(line)

    ax_temp.set_xlabel("time (s)")
    ax_temp.set_ylabel("temperature (°C)", color="#222222")
    ax_temp.tick_params(axis="y", colors="#222222")
    ax_temp.grid(True, axis="x", linestyle=":", linewidth=0.4, alpha=0.5)

    # Group cells by type so colour gradients are assigned in
    # 0-based order within type, not insertion order.
    counts_by_type: dict[str, int] = {}
    cell_lines = []
    for label, recording in recordings.items():
        cell_type = infer_cell_type_from_filename(label + ".csv") or "??"
        index_within_type = counts_by_type.get(cell_type, 0)
        counts_by_type[cell_type] = index_within_type + 1
        colour = colour_for_cell(cell_type, index_within_type)

        y_trace = (
            recording.dfbf_drift_corrected
            if (use_drift_corrected and recording.dfbf_drift_corrected is not None)
            else recording.dfbf
        )
        (line,) = ax_dfbf.plot(
            recording.time_s,
            y_trace,
            color=colour,
            linewidth=cell_linewidth,
            label=f"{label}  ({cell_type})",
            zorder=3,
        )
        cell_lines.append(line)

    ax_dfbf.set_ylabel(r"$\Delta F / F_0$")
    ax_dfbf.axhline(0.0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)

    # Single combined legend — temperature lines first, then cells.
    all_lines = temp_lines + cell_lines
    ax_temp.legend(
        all_lines,
        [line.get_label() for line in all_lines],
        loc="upper right",
        fontsize=8,
        framealpha=0.9,
        ncols=1 if len(all_lines) <= 5 else 2,
    )

    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────
#  Class wrapper  « stateful reuse with default styling »
# ─────────────────────────────────────────────────────────────────


@dataclass
class SessionOverview:
    """Callable wrapper around :func:`plot_session_overview`.

    Useful when many sessions are rendered with the same styling
    (e.g. a batch script or the future DB-backed display layer):

    .. code-block:: python

        plotter = SessionOverview(figsize=(12, 6), use_drift_corrected=True)
        for session_name, cells in sessions.items():
            fig = plotter(cells, title=session_name)
            plotter.save(fig, output_dir / f"{session_name}.png")

    Defaults stored on the instance are forwarded to every call
    unless overridden in the call's kwargs.
    """

    figsize: tuple[float, float] = (10, 5)
    use_drift_corrected: bool = True
    show_target: bool = True
    show_sensor: bool = True
    sensor_alpha: float = 0.55
    cell_linewidth: float = 1.0
    dpi: int = FIGURE_DPI

    def plot(
        self,
        recordings: dict[str, Recording],
        *,
        title: str | None = None,
        **overrides,
    ) -> Figure:
        """Build the figure. ``overrides`` win over instance defaults."""
        kwargs = {
            "figsize": self.figsize,
            "use_drift_corrected": self.use_drift_corrected,
            "show_target": self.show_target,
            "show_sensor": self.show_sensor,
            "sensor_alpha": self.sensor_alpha,
            "cell_linewidth": self.cell_linewidth,
        }
        kwargs.update(overrides)
        return plot_session_overview(recordings, title=title, **kwargs)

    def __call__(self, recordings: dict[str, Recording], **kwargs) -> Figure:
        return self.plot(recordings, **kwargs)

    def save(
        self,
        fig: Figure,
        path: Path | str,
        *,
        dpi: int | None = None,
        close: bool = True,
    ) -> Path:
        """Save the figure as a PNG (smallest disk size for a line plot).

        Args:
            fig: Figure returned by :meth:`plot`.
            path: Output path (extension forced to ``.png``).
            dpi: Override the instance default DPI for this save.
            close: Close the figure after saving to free memory.

        Returns:
            The resolved output path.
        """
        import matplotlib.pyplot as plt

        path = Path(path).with_suffix(".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi if dpi is not None else self.dpi)
        if close:
            plt.close(fig)
        return path
