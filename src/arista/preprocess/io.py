# ─────────────────────────────────────────────────────────────────
#  arista.preprocess.io  « read Fiji / sensor MAT, write CSV »
# ─────────────────────────────────────────────────────────────────
"""File I/O for raw inputs and preprocessed outputs.

This module replaces the I/O sprinkled across ``_legacy/pytci/tempFileIO.py``
and ``_legacy/aristaSingleCellData.py`` with pure functions that return
typed dataclasses instead of mutating ``self``.

Three input formats are accepted for Fiji ΔF/F exports:

* ``X,Y`` header (Alex Busch's older fixtures)
* ``Frame,Mean`` header (Alex Busch's later fixtures)
* ``frame,df/f`` header (legacy `aristaSingleCellData.py` output)

All three collapse to the same :class:`FijiRecording` dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import scipy.io as sio

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────
#  Dataclasses
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FijiRecording:
    """Raw Fiji ROI export — one ΔF/F₀ value per imaging frame."""

    frame: np.ndarray  # int, shape (N,)
    dfbf: np.ndarray   # float, shape (N,)

    def __post_init__(self) -> None:
        if self.frame.shape != self.dfbf.shape:
            raise ValueError(
                f"frame and dfbf must have matching shapes; got "
                f"{self.frame.shape} vs {self.dfbf.shape}"
            )

    @property
    def n_frames(self) -> int:
        return int(self.frame.size)


@dataclass(frozen=True)
class SensorRecord:
    """Raw MATLAB sensor record — continuously logged 5-column array.

    Each MAT file holds a ``data`` matrix whose columns are, in order:
    epoch_time (MATLAB serial datenum), frame index (1-based!),
    sensor_T (°C, actually measured), target_T (°C, set-point) and
    drive_T (°C, applied to the Peltier element). The log rate is
    higher than the imaging rate so multiple sensor rows share the
    same frame number; :func:`arista.preprocess.align` collapses them.
    """

    epoch_time: np.ndarray   # MATLAB datenum, float
    frame: np.ndarray        # int, 1-based in the raw file
    sensor_t_c: np.ndarray   # measured arista-adjacent temperature
    target_t_c: np.ndarray   # PID set-point
    drive_t_c: np.ndarray    # Peltier drive temperature

    @property
    def n_samples(self) -> int:
        return int(self.epoch_time.size)


@dataclass(frozen=True)
class Recording:
    """Frame-aligned, optionally drift-corrected Ca²⁺ recording.

    One row per imaging frame. Matches the column layout of the
    ``samples`` table in [[Database Schema]] so the ingester can
    bulk-insert directly.

    ``dfbf_drift_corrected`` is ``None`` whenever ``drift_method == "none"``.
    """

    frame: np.ndarray
    time_s: np.ndarray
    sensor_t_c: np.ndarray
    target_t_c: np.ndarray
    drive_t_c: np.ndarray | None
    dfbf: np.ndarray
    dfbf_drift_corrected: np.ndarray | None = None
    drift_method: str = "none"

    @property
    def n_frames(self) -> int:
        return int(self.frame.size)

    def to_dataframe(self) -> pd.DataFrame:
        """Return the recording as a pandas DataFrame with DB-schema columns."""
        data: dict[str, np.ndarray] = {
            "frame": self.frame.astype(int),
            "time_s": self.time_s,
            "sensor_t_c": self.sensor_t_c,
            "target_t_c": self.target_t_c,
            "dfbf": self.dfbf,
        }
        if self.drive_t_c is not None:
            data["drive_t_c"] = self.drive_t_c
        if self.dfbf_drift_corrected is not None:
            data["dfbf_drift_corrected"] = self.dfbf_drift_corrected
        return pd.DataFrame(data)


# ─────────────────────────────────────────────────────────────────
#  Readers
# ─────────────────────────────────────────────────────────────────

_FIJI_FRAME_ALIASES: tuple[str, ...] = ("frame", "Frame", "X", "x", "FrameIndex")
_FIJI_DFBF_ALIASES: tuple[str, ...] = ("df/f", "dfbf", "Mean", "Y", "y", "Value", "ΔF/F")


def _pick_column(columns: list[str], aliases: tuple[str, ...], kind: str) -> str:
    for alias in aliases:
        if alias in columns:
            return alias
    raise ValueError(
        f"Fiji CSV is missing a {kind} column; tried {aliases!r}, got {columns!r}"
    )


def read_fiji_csv(path: Path | str) -> FijiRecording:
    """Read a Fiji ΔF/F₀ ROI export into a :class:`FijiRecording`.

    Accepts any of the three header conventions documented in the
    module docstring. Header is *required* (no headerless CSV
    support; that would silently re-interpret the first frame as a
    column name and corrupt downstream alignment).

    Args:
        path: Path to the CSV file.

    Returns:
        Frozen :class:`FijiRecording` with frame and dfbf as numpy arrays.

    Raises:
        ValueError: If neither a frame-like nor a value-like column is
            present, or if frame indices are not monotonically increasing.
    """
    path = Path(path)
    df = pd.read_csv(path)
    columns = list(df.columns)
    frame_col = _pick_column(columns, _FIJI_FRAME_ALIASES, "frame")
    dfbf_col = _pick_column(columns, _FIJI_DFBF_ALIASES, "ΔF/F")

    frame = df[frame_col].to_numpy().astype(int)
    dfbf = df[dfbf_col].to_numpy().astype(float)
    if frame.size > 1 and not np.all(np.diff(frame) >= 0):
        raise ValueError(
            f"Fiji CSV {path} frame column is not monotonically increasing"
        )
    return FijiRecording(frame=frame, dfbf=dfbf)


def read_sensor_mat(path: Path | str) -> SensorRecord:
    """Read a MATLAB ``temperature_data_*.mat`` sensor record.

    The MAT file must contain a top-level variable ``data`` shaped
    ``(n_samples, 5)``: ``[epoch_time, frame, sensor_T, target_T, drive_T]``.

    Args:
        path: Path to the .mat file.

    Returns:
        Frozen :class:`SensorRecord` with the five columns as separate arrays.

    Raises:
        KeyError: If the MAT file lacks a ``data`` variable.
        ValueError: If the ``data`` matrix is not 5 columns wide.
    """
    path = Path(path)
    mat = sio.loadmat(str(path))
    if "data" not in mat:
        raise KeyError(
            f"Sensor MAT {path} missing required 'data' variable; "
            f"found keys: {sorted(mat.keys())}"
        )
    data = np.asarray(mat["data"])
    if data.ndim != 2 or data.shape[1] != 5:
        raise ValueError(
            f"Sensor MAT {path} expected (N, 5) data shape, got {data.shape}"
        )
    return SensorRecord(
        epoch_time=data[:, 0].astype(float),
        frame=data[:, 1].astype(int),
        sensor_t_c=data[:, 2].astype(float),
        target_t_c=data[:, 3].astype(float),
        drive_t_c=data[:, 4].astype(float),
    )


# ─────────────────────────────────────────────────────────────────
#  Writer + reader for our own canonical CSV
# ─────────────────────────────────────────────────────────────────


def write_recording_csv(recording: Recording, path: Path | str) -> Path:
    """Persist a :class:`Recording` to disk as a canonical CSV.

    Column order matches the ``samples`` table in [[Database Schema]] so
    ``arista-ingest`` can ``COPY``-style load without remapping. A
    one-line ``#``-prefixed header records the drift-correction method
    for downstream provenance.

    Args:
        recording: The recording to write.
        path: Destination CSV path.

    Returns:
        The resolved path the file was written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# drift_method: {recording.drift_method}\n")
        recording.to_dataframe().to_csv(fh, index=False)
    return path


def read_recording_csv(path: Path | str) -> Recording:
    """Re-read a canonical :func:`write_recording_csv` output."""
    path = Path(path)
    drift_method = "none"
    with path.open(encoding="utf-8") as fh:
        first_line = fh.readline().strip()
        if first_line.startswith("# drift_method:"):
            drift_method = first_line.split(":", 1)[1].strip()
        else:
            fh.seek(0)
        df = pd.read_csv(fh)

    drive = df["drive_t_c"].to_numpy() if "drive_t_c" in df.columns else None
    drift_corrected = (
        df["dfbf_drift_corrected"].to_numpy()
        if "dfbf_drift_corrected" in df.columns
        else None
    )
    return Recording(
        frame=df["frame"].to_numpy().astype(int),
        time_s=df["time_s"].to_numpy(),
        sensor_t_c=df["sensor_t_c"].to_numpy(),
        target_t_c=df["target_t_c"].to_numpy(),
        drive_t_c=drive,
        dfbf=df["dfbf"].to_numpy(),
        dfbf_drift_corrected=drift_corrected,
        drift_method=drift_method,
    )
