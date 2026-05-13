# ─────────────────────────────────────────────────────────────────
#  Tests for arista.processing.orchestrator
# ─────────────────────────────────────────────────────────────────
"""End-to-end processing run against a synthetic populated database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from arista.constants import STIMULUS_PROTOCOLS
from arista.db.connection import open_db
from arista.ingest import ingest_one, prepare_db
from arista.ingest.parsers.alex import IngestRecord
from arista.preprocess.io import Recording, write_recording_csv
from arista.processing.orchestrator import process_all


def _ascamp_samples_df(amplitude: float = 0.2, n_frames: int | None = None) -> pd.DataFrame:
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    if n_frames is None:
        n_frames = int(
            (proto.baseline_duration_s + proto.step_duration_s * len(proto.target_sequence))
            * 10.0
        )
    time_s = np.arange(n_frames) / 10.0
    sensor_t = np.full(n_frames, proto.baseline_t_c)
    target_t = np.full(n_frames, proto.baseline_t_c)
    dfbf = np.zeros(n_frames)
    for step_index, target in enumerate(proto.target_sequence):
        step_start = proto.baseline_duration_s + step_index * proto.step_duration_s
        step_end = step_start + proto.step_duration_s
        mask = (time_s >= step_start) & (time_s < step_end)
        sensor_t[mask] = target
        target_t[mask] = target
        dfbf[mask] = amplitude * (target - proto.baseline_t_c) / 4.0
    return pd.DataFrame({
        "frame": np.arange(n_frames),
        "time_s": time_s,
        "sensor_t_c": sensor_t,
        "target_t_c": target_t,
        "drive_t_c": sensor_t - 4.0,
        "dfbf": dfbf,
        "dfbf_drift_corrected": dfbf,
    })


def _ingest_ascamp(conn: sqlite3.Connection, csv_path: Path) -> int:
    samples_df = _ascamp_samples_df()
    rec = Recording(
        frame=samples_df["frame"].to_numpy(),
        time_s=samples_df["time_s"].to_numpy(),
        sensor_t_c=samples_df["sensor_t_c"].to_numpy(),
        target_t_c=samples_df["target_t_c"].to_numpy(),
        drive_t_c=samples_df["drive_t_c"].to_numpy(),
        dfbf=samples_df["dfbf"].to_numpy(),
        dfbf_drift_corrected=samples_df["dfbf_drift_corrected"].to_numpy(),
        drift_method="poly",
        recording_date="2021-12-20",
    )
    write_recording_csv(rec, csv_path)
    record = IngestRecord(
        researcher_name="Alexander Busch",
        strain_name="641",
        recording_date="2021-12-20",
        sex="f",
        animal_number=1,
        arista_suffix=None,
        cell_type_code="CC",
        cell_number=1,
        hemisphere="l",
        stimulus_name="ascAmp",
        fps=10.0,
        n_samples=len(samples_df),
        duration_s=float(samples_df["time_s"].iloc[-1]),
        drift_method="poly",
        samples_df=samples_df,
        source_csv=csv_path.resolve(),
        notes=None,
    )
    recording_id, _, _ = ingest_one(conn, record)
    return recording_id


def _ingest_bending(conn: sqlite3.Connection, csv_path: Path) -> int:
    """A no-aggregates control: stimulus family = mechanical."""
    samples_df = _ascamp_samples_df()
    rec = Recording(
        frame=samples_df["frame"].to_numpy(),
        time_s=samples_df["time_s"].to_numpy(),
        sensor_t_c=samples_df["sensor_t_c"].to_numpy(),
        target_t_c=samples_df["target_t_c"].to_numpy(),
        drive_t_c=samples_df["drive_t_c"].to_numpy(),
        dfbf=samples_df["dfbf"].to_numpy(),
        dfbf_drift_corrected=samples_df["dfbf_drift_corrected"].to_numpy(),
        drift_method="poly",
        recording_date="2021-12-20",
    )
    write_recording_csv(rec, csv_path)
    record = IngestRecord(
        researcher_name="Alexander Busch",
        strain_name="641",
        recording_date="2021-12-20",
        sex="f",
        animal_number=2,
        arista_suffix=None,
        cell_type_code="HC",
        cell_number=1,
        hemisphere="l",
        stimulus_name="Bending",
        fps=10.0,
        n_samples=len(samples_df),
        duration_s=float(samples_df["time_s"].iloc[-1]),
        drift_method="poly",
        samples_df=samples_df,
        source_csv=csv_path.resolve(),
        notes=None,
    )
    recording_id, _, _ = ingest_one(conn, record)
    return recording_id


# ─────────────────────────────────────────────────────────────────
#  Happy path
# ─────────────────────────────────────────────────────────────────

def test_process_all_populates_stimulus_responses(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        _ingest_ascamp(conn, tmp_path / "l_CC01.csv")
        stats = process_all(conn, progress=False)
        n_responses = conn.execute(
            "SELECT COUNT(*) FROM stimulus_responses"
        ).fetchone()[0]
    expected = len(STIMULUS_PROTOCOLS["ascAmp"].target_sequence)
    assert stats.inserted_responses == expected
    assert n_responses == expected


def test_process_all_skips_bending_recordings(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        _ingest_bending(conn, tmp_path / "l_HC01.csv")
        stats = process_all(conn, progress=False)
        n_responses = conn.execute(
            "SELECT COUNT(*) FROM stimulus_responses"
        ).fetchone()[0]
    assert stats.inserted_responses == 0
    assert stats.inserted_adaptations == 0
    assert n_responses == 0


def test_process_all_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        _ingest_ascamp(conn, tmp_path / "l_CC01.csv")
        process_all(conn, progress=False)
        # second run shouldn't add anything
        stats = process_all(conn, progress=False)
    assert stats.inserted_responses == 0
    assert stats.skipped_already_done >= 1


def test_reprocess_clears_and_recomputes(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        _ingest_ascamp(conn, tmp_path / "l_CC01.csv")
        first = process_all(conn, progress=False)
        second = process_all(conn, progress=False, reprocess=True)
    assert second.inserted_responses == first.inserted_responses
    assert second.inserted_responses > 0


def test_process_all_handles_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        stats = process_all(conn, progress=False)
    assert stats.inserted_responses == 0
    assert stats.inserted_adaptations == 0
    assert stats.skipped_already_done == 0


# ─────────────────────────────────────────────────────────────────
#  Result inspection
# ─────────────────────────────────────────────────────────────────

def test_inserted_rows_carry_step_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    with open_db(db_path) as conn:
        prepare_db(conn)
        rec_id = _ingest_ascamp(conn, tmp_path / "l_CC01.csv")
        process_all(conn, progress=False)
        rows = conn.execute(
            """
            SELECT step_index, target_temp_c, delta_target_c,
                   observed_temp_median, dfbf_response_median,
                   n_frames_in_window
            FROM stimulus_responses
            WHERE recording_id = ?
            ORDER BY step_index
            """,
            (rec_id,),
        ).fetchall()
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    assert len(rows) == len(proto.target_sequence)
    for step_index, target_temp_c, delta_target_c, observed_temp_median, _, n in rows:
        assert target_temp_c == proto.target_sequence[step_index]
        assert delta_target_c == proto.target_sequence[step_index] - proto.baseline_t_c
        assert observed_temp_median == pytest.approx(target_temp_c)
        assert 590 <= n <= 600
