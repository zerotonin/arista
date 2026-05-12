# ─────────────────────────────────────────────────────────────────
#  arista.preprocess.align  « stages A + B + C »
# ─────────────────────────────────────────────────────────────────
"""Frame-align a sensor record against a Fiji ΔF/F trace.

Stages from [[Preprocessing Pipeline]]:

* A — ``collapse_to_frames``: group continuous sensor log rows by their
  imaging frame number and take the per-frame mean
* B — :func:`arista.preprocess.interpolate.interpolate_missing_frames`:
  fill any frames the DAQ dropped
* C — ``assemble_recording``: cut the sensor record down to the
  imaged window, merge with the Fiji ΔF/F trace, convert MATLAB
  datenums to elapsed seconds

The implementation matches the legacy ``_legacy/aristaSingleCellData.py``
behaviour: per-frame **mean** (not median), pandas ``interpolate``
(not scipy ``interp1d``), so byte-level regression against legacy
outputs holds within float tolerance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from arista.preprocess.interpolate import interpolate_missing_frames
from arista.preprocess.io import FijiRecording, Recording, SensorRecord

if TYPE_CHECKING:
    pass

# MATLAB epoch offset: serial day 1 == 0000-01-01 in MATLAB, vs
# Unix 1970-01-01 in Python. The difference is 719529 days.
_MATLAB_TO_UNIX_DAYS: int = 719529


# ─────────────────────────────────────────────────────────────────
#  Stage A: collapse sensor log into one row per imaging frame
# ─────────────────────────────────────────────────────────────────


def collapse_to_frames(sensor: SensorRecord) -> pd.DataFrame:
    """Group the continuous sensor log by frame, take the per-frame mean.

    Sensor rows where ``frame == 0`` are pre-stimulus calibration data
    and dropped (matches the ``frame > 0`` cut in the legacy pipeline).
    Frame numbers are decremented by 1 so the result is 0-indexed,
    aligning with Fiji's frame numbering.

    Args:
        sensor: Raw :class:`SensorRecord` straight from
            :func:`arista.preprocess.io.read_sensor_mat`.

    Returns:
        A DataFrame indexed by integer 0-based frame number, with
        columns ``epoch_time``, ``sensor_t_c``, ``target_t_c``,
        ``drive_t_c``. NaN-padded over any missing intermediate frames
        so :func:`interpolate_missing_frames` can fill them.
    """
    df = pd.DataFrame(
        {
            "epoch_time": sensor.epoch_time,
            "frame": sensor.frame.astype(int),
            "sensor_t_c": sensor.sensor_t_c,
            "target_t_c": sensor.target_t_c,
            "drive_t_c": sensor.drive_t_c,
        }
    )
    # Drop the pre-stimulus calibration rows (frame == 0 in the raw log).
    df = df.loc[df["frame"] > 0].copy()
    # Re-index to 0-based to match Fiji.
    df["frame"] = df["frame"] - 1
    grouped = df.groupby("frame", as_index=True).mean(numeric_only=True)
    # Reindex to a contiguous frame range so interpolation can fill gaps.
    if grouped.empty:
        return grouped
    full = range(int(grouped.index.min()), int(grouped.index.max()) + 1)
    return grouped.reindex(full)


# ─────────────────────────────────────────────────────────────────
#  Stage C: assemble Recording from Fiji + collapsed sensor
# ─────────────────────────────────────────────────────────────────


def _matlab_datenum_to_elapsed_seconds(matlab_datenum: np.ndarray) -> np.ndarray:
    """Convert a MATLAB serial-date column into elapsed seconds from frame 0."""
    epoch = pd.to_datetime(
        matlab_datenum - _MATLAB_TO_UNIX_DAYS, unit="D", origin="unix"
    )
    # Under NumPy 2 + recent pandas, .to_numpy() returns a read-only view
    # of the underlying ndarray; copy=True so we can patch deltas_s[0].
    deltas_s = epoch.to_series().diff().dt.total_seconds().to_numpy(copy=True)
    deltas_s[0] = 0.0
    return np.cumsum(deltas_s)


def _matlab_datenum_to_iso_date(matlab_datenum: float) -> str:
    """Convert one MATLAB serial-date scalar into an ISO ``YYYY-MM-DD`` string."""
    ts = pd.to_datetime(
        matlab_datenum - _MATLAB_TO_UNIX_DAYS, unit="D", origin="unix"
    )
    return ts.strftime("%Y-%m-%d")


def assemble_recording(
    fiji: FijiRecording,
    sensor: SensorRecord,
) -> Recording:
    """Run stages A + B + C and return a frame-aligned :class:`Recording`.

    Drift correction is **not** applied here — that is
    :mod:`arista.preprocess.drift`'s job. The returned recording has
    ``dfbf_drift_corrected = None`` and ``drift_method = "none"``.

    The output length is the intersection of the Fiji frame range
    and the (post-collapse, post-interp) sensor frame range. Any Fiji
    frames without a matching sensor frame are dropped silently — this
    matches legacy behaviour and only ever clips a handful of trailing
    frames in well-formed recordings.

    Args:
        fiji: Fiji ΔF/F₀ trace.
        sensor: Raw sensor record.

    Returns:
        A :class:`Recording` aligned to Fiji's frame numbers.
    """
    per_frame = collapse_to_frames(sensor)
    per_frame = interpolate_missing_frames(per_frame)

    fiji_df = pd.DataFrame({"frame": fiji.frame, "dfbf": fiji.dfbf})
    fiji_df = fiji_df.set_index("frame")

    merged = per_frame.join(fiji_df, how="inner")
    merged = merged.sort_index()
    merged.index = merged.index.astype(int)

    epoch_column = merged["epoch_time"].to_numpy()
    time_s = _matlab_datenum_to_elapsed_seconds(epoch_column)
    recording_date = (
        _matlab_datenum_to_iso_date(float(epoch_column[0]))
        if epoch_column.size > 0
        else None
    )

    return Recording(
        frame=merged.index.to_numpy().astype(int),
        time_s=time_s,
        sensor_t_c=merged["sensor_t_c"].to_numpy(),
        target_t_c=merged["target_t_c"].to_numpy(),
        drive_t_c=merged["drive_t_c"].to_numpy(),
        dfbf=merged["dfbf"].to_numpy(),
        recording_date=recording_date,
    )
