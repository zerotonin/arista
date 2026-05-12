# ─────────────────────────────────────────────────────────────────
#  Regression tests: arista.preprocess vs _legacy/aristaSingleCellData
# ─────────────────────────────────────────────────────────────────
"""Verify the new headless pipeline produces output numerically
equivalent to the legacy ``aristaSingleCellData.py`` on the bundled
fixtures (within float tolerance).

The legacy script's output columns are: ``frame``, ``epoch time``,
``sensor T``, ``target T``, ``drive T``, ``df/f``, ``time_s``,
``sensor TF`` (Butterworth-filtered sensor T). We compare ``sensor_t_c``,
``target_t_c``, ``drive_t_c``, ``dfbf`` and ``time_s`` — the channels
the new pipeline computes. The Butterworth-filtered sensor T is a
display-only convenience the new pipeline omits.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from arista.preprocess import assemble_recording, read_fiji_csv, read_sensor_mat

REPO_ROOT = Path(__file__).resolve().parents[1]

# The legacy aristaSingleCellData.py parses the parent directory name as
# <strain>_<num>_<sex> and the Fiji filename as <hemisphere>_<celltype><num>,
# so the regression must point at a layout-conformant fixture rather than
# the loose data/fiji/ + data/sensor/ pair.
_ANIMAL_DIR = REPO_ROOT / "data" / "raw" / "alex" / "641" / "WT_02_m"


@pytest.fixture(scope="module")
def legacy_ascd():
    """Import the legacy aristaSingleCellData class from _legacy/."""
    legacy_dir = REPO_ROOT / "_legacy"
    sys.path.insert(0, str(legacy_dir))
    spec = importlib.util.spec_from_file_location(
        "_legacy_ascd_for_regression",
        legacy_dir / "aristaSingleCellData.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.aristaSingleCellData


def _run_legacy(fiji_path: Path, sensor_path: Path, scratch: Path, ascd_class) -> pd.DataFrame:
    """Invoke the legacy pipeline and return its output DataFrame."""
    ascd = ascd_class(str(fiji_path), str(sensor_path))
    ascd.main(str(scratch))
    out_csvs = list(scratch.glob("*.csv"))
    assert len(out_csvs) == 1, f"expected one CSV, got {out_csvs}"
    return pd.read_csv(out_csvs[0])


@pytest.fixture(scope="module")
def fiji_path() -> Path:
    return _ANIMAL_DIR / "l_HC01.csv"


@pytest.fixture(scope="module")
def sensor_path() -> Path:
    return _ANIMAL_DIR / "temperature_data_2021_12_20-12_40.mat"


def test_new_pipeline_matches_legacy_sensor_t(
    fiji_path: Path, sensor_path: Path, legacy_ascd, tmp_path_factory
) -> None:
    """Per-frame sensor_T from new pipeline matches legacy within float eps."""
    scratch = tmp_path_factory.mktemp("legacy_out")
    legacy_df = _run_legacy(fiji_path, sensor_path, scratch, legacy_ascd)

    fiji = read_fiji_csv(fiji_path)
    sensor = read_sensor_mat(sensor_path)
    new_rec = assemble_recording(fiji, sensor)

    # The legacy output is indexed from 0; cap both to the shorter length.
    n = min(len(legacy_df), new_rec.n_frames)
    np.testing.assert_allclose(
        new_rec.sensor_t_c[:n], legacy_df["sensor T"].to_numpy()[:n],
        rtol=1e-9, atol=1e-9,
        err_msg="sensor_t_c diverges from legacy aristaSingleCellData output",
    )


def test_new_pipeline_matches_legacy_target_t(
    fiji_path: Path, sensor_path: Path, legacy_ascd, tmp_path_factory
) -> None:
    scratch = tmp_path_factory.mktemp("legacy_out")
    legacy_df = _run_legacy(fiji_path, sensor_path, scratch, legacy_ascd)

    fiji = read_fiji_csv(fiji_path)
    sensor = read_sensor_mat(sensor_path)
    new_rec = assemble_recording(fiji, sensor)

    n = min(len(legacy_df), new_rec.n_frames)
    np.testing.assert_allclose(
        new_rec.target_t_c[:n], legacy_df["target T"].to_numpy()[:n],
        rtol=1e-9, atol=1e-9,
    )


def test_new_pipeline_matches_legacy_dfbf(
    fiji_path: Path, sensor_path: Path, legacy_ascd, tmp_path_factory
) -> None:
    scratch = tmp_path_factory.mktemp("legacy_out")
    legacy_df = _run_legacy(fiji_path, sensor_path, scratch, legacy_ascd)

    fiji = read_fiji_csv(fiji_path)
    sensor = read_sensor_mat(sensor_path)
    new_rec = assemble_recording(fiji, sensor)

    n = min(len(legacy_df), new_rec.n_frames)
    np.testing.assert_allclose(
        new_rec.dfbf[:n], legacy_df["df/f"].to_numpy()[:n],
        rtol=1e-9, atol=1e-9,
    )


def test_new_pipeline_matches_legacy_time_s(
    fiji_path: Path, sensor_path: Path, legacy_ascd, tmp_path_factory
) -> None:
    """Elapsed time conversion (MATLAB datenum → cumulative seconds) matches."""
    scratch = tmp_path_factory.mktemp("legacy_out")
    legacy_df = _run_legacy(fiji_path, sensor_path, scratch, legacy_ascd)

    fiji = read_fiji_csv(fiji_path)
    sensor = read_sensor_mat(sensor_path)
    new_rec = assemble_recording(fiji, sensor)

    n = min(len(legacy_df), new_rec.n_frames)
    np.testing.assert_allclose(
        new_rec.time_s[:n], legacy_df["time_s"].to_numpy()[:n],
        rtol=1e-6, atol=1e-6,
    )


def test_new_pipeline_drive_t_matches_legacy(
    fiji_path: Path, sensor_path: Path, legacy_ascd, tmp_path_factory
) -> None:
    scratch = tmp_path_factory.mktemp("legacy_out")
    legacy_df = _run_legacy(fiji_path, sensor_path, scratch, legacy_ascd)

    fiji = read_fiji_csv(fiji_path)
    sensor = read_sensor_mat(sensor_path)
    new_rec = assemble_recording(fiji, sensor)

    n = min(len(legacy_df), new_rec.n_frames)
    np.testing.assert_allclose(
        new_rec.drive_t_c[:n], legacy_df["drive T"].to_numpy()[:n],
        rtol=1e-9, atol=1e-9,
    )
