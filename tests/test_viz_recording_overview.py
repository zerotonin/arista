# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz.recording_overview
# ─────────────────────────────────────────────────────────────────
"""Smoke + integration tests for the dual-y-axis session plotter."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from arista.preprocess.io import Recording
from arista.viz import SessionOverview, plot_session_overview


def _synthetic_recording(seed: int, n: int = 200) -> Recording:
    """Build a synthetic Recording mimicking a 200-frame Ca²⁺ trace."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 20.0, n)
    # square-wave target T (22 ↔ 26)
    target = 22.0 + 4.0 * (np.sin(2 * np.pi * t / 10.0) > 0).astype(float)
    sensor = target + rng.normal(0, 0.05, n)
    dfbf = rng.normal(0, 0.01, n)
    dfbf_corr = rng.normal(0, 0.005, n)
    return Recording(
        frame=np.arange(n),
        time_s=t,
        sensor_t_c=sensor,
        target_t_c=target,
        drive_t_c=sensor - 4.0,
        dfbf=dfbf,
        dfbf_drift_corrected=dfbf_corr,
        drift_method="auto",
    )


# ─────────────────────────────────────────────────────────────────
#  plot_session_overview
# ─────────────────────────────────────────────────────────────────

def test_plot_session_overview_returns_figure() -> None:
    recordings = {
        "l_CC01": _synthetic_recording(0),
        "l_HC01": _synthetic_recording(1),
    }
    fig = plot_session_overview(recordings, title="test session")
    assert fig is not None
    # One temperature axis + its twin → exactly two Axes objects
    assert len(fig.axes) == 2
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_session_overview_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one Recording"):
        plot_session_overview({})


def test_plot_uses_drift_corrected_when_present() -> None:
    rec = _synthetic_recording(0)
    fig = plot_session_overview({"l_CC01": rec})
    cell_lines = [line for line in fig.axes[1].get_lines() if "0" in str(line.get_label())]
    # The cell line should match dfbf_drift_corrected, not dfbf
    line_y = cell_lines[0].get_ydata()
    np.testing.assert_allclose(line_y, rec.dfbf_drift_corrected)
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_falls_back_to_raw_dfbf_when_no_drift() -> None:
    raw_only = Recording(
        frame=np.arange(50),
        time_s=np.linspace(0.0, 5.0, 50),
        sensor_t_c=np.full(50, 22.0),
        target_t_c=np.full(50, 22.0),
        drive_t_c=np.full(50, 18.0),
        dfbf=np.linspace(0.0, 1.0, 50),
        dfbf_drift_corrected=None,
        drift_method="none",
    )
    fig = plot_session_overview({"l_CC01": raw_only})
    line = [line for line in fig.axes[1].get_lines() if "l_CC01" in str(line.get_label())][0]
    np.testing.assert_allclose(line.get_ydata(), raw_only.dfbf)
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_assigns_distinct_colours_per_cell_within_type() -> None:
    """Two CC cells must get different colours from CC_GRADIENT."""
    recordings = {
        "l_CC01": _synthetic_recording(0),
        "l_CC02": _synthetic_recording(1),
        "l_HC01": _synthetic_recording(2),
        "l_HC02": _synthetic_recording(3),
    }
    fig = plot_session_overview(recordings)
    cell_lines = {
        line.get_label().split()[0]: line
        for line in fig.axes[1].get_lines()
        if line.get_label() and not line.get_label().startswith("_")
    }
    assert cell_lines["l_CC01"].get_color() != cell_lines["l_CC02"].get_color()
    assert cell_lines["l_HC01"].get_color() != cell_lines["l_HC02"].get_color()
    # CC and HC must use disjoint colours
    assert cell_lines["l_CC01"].get_color() != cell_lines["l_HC01"].get_color()
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_handles_five_cells_with_palette_clamp() -> None:
    """Five HC cells: palette has 4, so cell 5 reuses the last colour."""
    recordings = {f"l_HC0{i}": _synthetic_recording(i) for i in range(1, 6)}
    fig = plot_session_overview(recordings)
    # Should not raise; expect five cell lines plus target + sensor
    cell_count = sum(
        1 for line in fig.axes[1].get_lines() if "HC" in str(line.get_label())
    )
    assert cell_count == 5
    import matplotlib.pyplot as plt

    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  SessionOverview class wrapper
# ─────────────────────────────────────────────────────────────────

def test_session_overview_class_is_callable() -> None:
    plotter = SessionOverview(figsize=(8, 4))
    recordings = {"l_CC01": _synthetic_recording(0)}
    fig = plotter(recordings, title="callable test")
    assert fig is not None
    # Instance default propagated
    assert tuple(fig.get_size_inches()) == (8, 4)
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_session_overview_overrides_win() -> None:
    plotter = SessionOverview(figsize=(8, 4))
    recordings = {"l_CC01": _synthetic_recording(0)}
    fig = plotter.plot(recordings, figsize=(12, 6))
    assert tuple(fig.get_size_inches()) == (12, 6)
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_session_overview_save_writes_png(tmp_path: Path) -> None:
    plotter = SessionOverview()
    recordings = {"l_CC01": _synthetic_recording(0)}
    fig = plotter(recordings)
    target = tmp_path / "overview.png"
    written = plotter.save(fig, target)
    assert written == target
    assert target.exists()
    # PNG magic bytes
    assert target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_session_overview_save_forces_png_extension(tmp_path: Path) -> None:
    plotter = SessionOverview()
    recordings = {"l_CC01": _synthetic_recording(0)}
    fig = plotter(recordings)
    written = plotter.save(fig, tmp_path / "wrong.svg")
    # .svg is silently corrected to .png — smallest disk size
    assert written.suffix == ".png"
    assert not (tmp_path / "wrong.svg").exists()
