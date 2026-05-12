# ─────────────────────────────────────────────────────────────────
#  Tests for arista.preprocess.align + interpolate
# ─────────────────────────────────────────────────────────────────
"""Frame-alignment and interpolation behaviour tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from arista.constants import FIJI_FIXTURE_DIR, SENSOR_FIXTURE_DIR
from arista.preprocess.align import (
    _matlab_datenum_to_elapsed_seconds,
    assemble_recording,
    collapse_to_frames,
)
from arista.preprocess.interpolate import interpolate_missing_frames
from arista.preprocess.io import (
    FijiRecording,
    SensorRecord,
    read_fiji_csv,
    read_sensor_mat,
)


def _toy_sensor(n_frames_real: int = 50, n_per_frame: int = 5) -> SensorRecord:
    """Build a synthetic SensorRecord: ``n_per_frame`` log rows per imaging frame."""
    frames = np.repeat(np.arange(n_frames_real + 1), n_per_frame).astype(int)
    n = frames.size
    return SensorRecord(
        epoch_time=738510.0 + np.arange(n) / 86400.0,  # one sec apart
        frame=frames,
        sensor_t_c=22.0 + np.sin(frames * 0.1),
        target_t_c=np.full(n, 22.0),
        drive_t_c=18.0 + np.cos(frames * 0.05),
    )


# ─────────────────────────────────────────────────────────────────
#  collapse_to_frames
# ─────────────────────────────────────────────────────────────────

def test_collapse_drops_frame_zero_calibration() -> None:
    """Sensor rows logged before frame 1 are pre-stimulus and must be dropped."""
    sensor = _toy_sensor(n_frames_real=10, n_per_frame=3)
    per_frame = collapse_to_frames(sensor)
    # 0-based index after the -1 shift; no negative frames
    assert per_frame.index.min() == 0
    assert per_frame.index.max() == 9


def test_collapse_returns_one_row_per_frame() -> None:
    sensor = _toy_sensor(n_frames_real=20, n_per_frame=7)
    per_frame = collapse_to_frames(sensor)
    assert len(per_frame) == 20  # frames 1..20 → 0..19 after -1 shift
    assert list(per_frame.columns) == [
        "epoch_time", "sensor_t_c", "target_t_c", "drive_t_c",
    ]


def test_collapse_per_frame_value_is_mean() -> None:
    """Multiple sensor rows for the same frame collapse via mean (matches legacy)."""
    sensor = SensorRecord(
        epoch_time=np.array([0.0, 1.0, 2.0]),
        frame=np.array([1, 1, 1]),
        sensor_t_c=np.array([20.0, 22.0, 24.0]),
        target_t_c=np.array([22.0, 22.0, 22.0]),
        drive_t_c=np.array([18.0, 18.0, 18.0]),
    )
    per_frame = collapse_to_frames(sensor)
    assert per_frame.loc[0, "sensor_t_c"] == 22.0  # (20 + 22 + 24) / 3


# ─────────────────────────────────────────────────────────────────
#  interpolate_missing_frames
# ─────────────────────────────────────────────────────────────────

def test_interpolate_fills_nan_linearly() -> None:
    df = pd.DataFrame(
        {"x": [1.0, np.nan, np.nan, 4.0]},
        index=[0, 1, 2, 3],
    )
    out = interpolate_missing_frames(df)
    np.testing.assert_allclose(out["x"].to_numpy(), [1.0, 2.0, 3.0, 4.0])


def test_interpolate_no_op_when_clean() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    out = interpolate_missing_frames(df)
    pd.testing.assert_frame_equal(out, df)


# ─────────────────────────────────────────────────────────────────
#  assemble_recording end-to-end on bundled fixtures
# ─────────────────────────────────────────────────────────────────

def test_assemble_on_bundled_fixtures() -> None:
    fiji = read_fiji_csv(FIJI_FIXTURE_DIR / "HC01.csv")
    sensor = read_sensor_mat(
        SENSOR_FIXTURE_DIR / "temperature_data_2021_12_20-12_40.mat"
    )
    rec = assemble_recording(fiji, sensor)

    # Aligned length matches Fiji frame count (modulo a handful clipped at end)
    assert abs(rec.n_frames - fiji.n_frames) < 10
    # Sensor T is in the expected ascAmp range (18-26 °C ± slop)
    assert 15 < rec.sensor_t_c.min() < 20
    assert 24 < rec.sensor_t_c.max() < 28
    # Drift correction not applied yet
    assert rec.dfbf_drift_corrected is None
    assert rec.drift_method == "none"
    # time_s starts at 0 and is monotonically increasing
    assert rec.time_s[0] == 0.0
    assert np.all(np.diff(rec.time_s) > 0)
    # Recording length ≈ 600 s (10 fps × 60 s × 10 step protocol)
    assert 500 < rec.time_s[-1] < 700


def test_assemble_drops_unmatched_fiji_frames() -> None:
    """Fiji frames without a sensor counterpart are dropped, not NaN-padded."""
    fiji = FijiRecording(
        frame=np.arange(100),
        dfbf=np.random.default_rng(0).normal(0, 0.01, 100),
    )
    sensor = _toy_sensor(n_frames_real=50, n_per_frame=3)
    rec = assemble_recording(fiji, sensor)
    # Only the 50 frames where the sensor has data survive
    assert rec.n_frames == 50
    assert rec.frame[-1] == 49


# ─────────────────────────────────────────────────────────────────
#  MATLAB datenum conversion
# ─────────────────────────────────────────────────────────────────

def test_matlab_datenum_starts_at_zero() -> None:
    """Convert a 5-row MATLAB datenum to elapsed seconds, 1 s apart.

    pandas ``to_datetime(unit="D")`` carries ~5 µs of float-precision noise
    per second when fed fractional days; tolerate it. The legacy pipeline
    has the same noise, so regression against it is unaffected.
    """
    matlab_datenum = 738510.0 + np.arange(5) / 86400.0  # five seconds apart
    elapsed = _matlab_datenum_to_elapsed_seconds(matlab_datenum)
    assert elapsed[0] == 0.0
    np.testing.assert_allclose(np.diff(elapsed), 1.0, atol=1e-4)
