# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — preprocess                                             ║
# ║  « headless rebuild of pytci stages A-I »                        ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Pure-function pipeline that takes raw Fiji ΔF/F exports plus    ║
# ║  MATLAB sensor MATs and produces drift-corrected, frame-aligned  ║
# ║  CSVs identical in maths to the legacy pytci package.            ║
# ║                                                                  ║
# ║  Stages A-I documented in [[Preprocessing Pipeline]]; see        ║
# ║  align.py, interpolate.py, drift.py, template_rescue.py.         ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Headless preprocessing pipeline — public API re-exports."""

from __future__ import annotations

from arista.preprocess.align import (
    assemble_recording,
    collapse_to_frames,
)
from arista.preprocess.drift import (
    DriftFit,
    DriftMethod,
    apply_drift,
    correct_drift,
    fit_all,
    fit_exponential,
    fit_linear,
    fit_polynomial,
    pick_best,
)
from arista.preprocess.interpolate import interpolate_missing_frames
from arista.preprocess.io import (
    FijiRecording,
    Recording,
    SensorRecord,
    read_fiji_csv,
    read_recording_csv,
    read_sensor_mat,
    write_recording_csv,
)
from arista.preprocess.template_rescue import (
    is_broken_sensor,
    load_template,
)

__all__ = [
    # io
    "FijiRecording",
    "SensorRecord",
    "Recording",
    "read_fiji_csv",
    "read_sensor_mat",
    "write_recording_csv",
    "read_recording_csv",
    # align + interp
    "collapse_to_frames",
    "interpolate_missing_frames",
    "assemble_recording",
    # drift
    "DriftFit",
    "DriftMethod",
    "fit_linear",
    "fit_polynomial",
    "fit_exponential",
    "fit_all",
    "pick_best",
    "apply_drift",
    "correct_drift",
    # template rescue
    "is_broken_sensor",
    "load_template",
]
