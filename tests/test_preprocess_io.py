# ─────────────────────────────────────────────────────────────────
#  Tests for arista.preprocess.io
# ─────────────────────────────────────────────────────────────────
"""Round-trip tests for the Fiji / sensor / canonical-CSV I/O."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from arista.constants import FIJI_FIXTURE_DIR, SENSOR_FIXTURE_DIR
from arista.preprocess.io import (
    FijiRecording,
    Recording,
    SensorRecord,
    read_fiji_csv,
    read_recording_csv,
    read_sensor_mat,
    write_recording_csv,
)

# ─────────────────────────────────────────────────────────────────
#  Fiji reader
# ─────────────────────────────────────────────────────────────────

def test_read_fiji_csv_xy_header() -> None:
    rec = read_fiji_csv(FIJI_FIXTURE_DIR / "HC01.csv")
    assert isinstance(rec, FijiRecording)
    assert rec.n_frames > 1000
    assert rec.frame.dtype.kind == "i"
    assert rec.dfbf.dtype.kind == "f"
    assert rec.frame[0] == 0
    # ΔF/F values should sit in a sensible physiological range
    assert -1.0 < rec.dfbf.min() and rec.dfbf.max() < 1.0


def test_read_fiji_csv_frame_mean_header(tmp_path: Path) -> None:
    """Alex's later fixtures use 'Frame,Mean' headers."""
    csv = tmp_path / "alex_style.csv"
    csv.write_text("Frame,Mean\n0,0.001\n1,-0.002\n2,0.003\n")
    rec = read_fiji_csv(csv)
    assert rec.n_frames == 3
    np.testing.assert_array_equal(rec.frame, [0, 1, 2])
    np.testing.assert_allclose(rec.dfbf, [0.001, -0.002, 0.003])


def test_read_fiji_csv_rejects_unknown_header(tmp_path: Path) -> None:
    csv = tmp_path / "weird.csv"
    csv.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError, match="missing a frame column"):
        read_fiji_csv(csv)


def test_read_fiji_csv_rejects_non_monotonic(tmp_path: Path) -> None:
    csv = tmp_path / "shuffled.csv"
    csv.write_text("X,Y\n3,0.1\n1,0.2\n2,0.3\n")
    with pytest.raises(ValueError, match="not monotonically increasing"):
        read_fiji_csv(csv)


# ─────────────────────────────────────────────────────────────────
#  Sensor MAT reader
# ─────────────────────────────────────────────────────────────────

def test_read_sensor_mat_returns_five_columns() -> None:
    rec = read_sensor_mat(SENSOR_FIXTURE_DIR / "temperature_data_2021_12_20-12_40.mat")
    assert isinstance(rec, SensorRecord)
    assert rec.n_samples > 1000
    # All columns have the same length
    assert (
        rec.epoch_time.size
        == rec.frame.size
        == rec.sensor_t_c.size
        == rec.target_t_c.size
        == rec.drive_t_c.size
    )
    # Sensor T should sit in the physiological / experimental range
    assert 10 < rec.sensor_t_c.mean() < 35


def test_read_sensor_mat_rejects_missing_data_key(tmp_path: Path) -> None:
    import scipy.io as sio
    bad = tmp_path / "no_data.mat"
    sio.savemat(str(bad), {"other_var": np.ones(5)})
    with pytest.raises(KeyError, match="missing required 'data' variable"):
        read_sensor_mat(bad)


def test_read_sensor_mat_rejects_wrong_column_count(tmp_path: Path) -> None:
    import scipy.io as sio
    bad = tmp_path / "wrong_cols.mat"
    sio.savemat(str(bad), {"data": np.ones((10, 3))})
    with pytest.raises(ValueError, match="expected .* 5"):
        read_sensor_mat(bad)


# ─────────────────────────────────────────────────────────────────
#  Recording dataclass + CSV round trip
# ─────────────────────────────────────────────────────────────────

def _toy_recording(drift: bool = False) -> Recording:
    n = 100
    return Recording(
        frame=np.arange(n),
        time_s=np.linspace(0.0, 10.0, n),
        sensor_t_c=22.0 + np.random.default_rng(0).normal(0, 0.1, n),
        target_t_c=np.full(n, 22.0),
        drive_t_c=20.0 + np.random.default_rng(1).normal(0, 0.05, n),
        dfbf=np.random.default_rng(2).normal(0, 0.01, n),
        dfbf_drift_corrected=(
            np.random.default_rng(3).normal(0, 0.01, n) if drift else None
        ),
        drift_method="poly" if drift else "none",
    )


def test_recording_to_dataframe_has_db_schema_columns() -> None:
    rec = _toy_recording(drift=True)
    df = rec.to_dataframe()
    assert set(df.columns) == {
        "frame", "time_s", "sensor_t_c", "target_t_c",
        "drive_t_c", "dfbf", "dfbf_drift_corrected",
    }


def test_recording_to_dataframe_omits_drift_when_absent() -> None:
    rec = _toy_recording(drift=False)
    df = rec.to_dataframe()
    assert "dfbf_drift_corrected" not in df.columns


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    src = _toy_recording(drift=True)
    out = tmp_path / "recording.csv"
    write_recording_csv(src, out)

    back = read_recording_csv(out)
    assert back.drift_method == src.drift_method
    np.testing.assert_array_equal(back.frame, src.frame)
    np.testing.assert_allclose(back.time_s, src.time_s)
    np.testing.assert_allclose(back.sensor_t_c, src.sensor_t_c)
    np.testing.assert_allclose(back.target_t_c, src.target_t_c)
    np.testing.assert_allclose(back.drive_t_c, src.drive_t_c)
    np.testing.assert_allclose(back.dfbf, src.dfbf)
    np.testing.assert_allclose(back.dfbf_drift_corrected, src.dfbf_drift_corrected)


def test_write_includes_drift_method_header(tmp_path: Path) -> None:
    rec = _toy_recording(drift=True)
    out = tmp_path / "rec.csv"
    write_recording_csv(rec, out)
    first_line = out.read_text().splitlines()[0]
    assert first_line.startswith("# drift_method:")
    assert "poly" in first_line


def test_recording_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="matching shapes"):
        FijiRecording(frame=np.array([0, 1, 2]), dfbf=np.array([0.0, 1.0]))
