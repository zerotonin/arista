# ─────────────────────────────────────────────────────────────────
#  Tests for arista.ingest.orchestrator
# ─────────────────────────────────────────────────────────────────
"""End-to-end ingest tests on synthetic and bundled fixtures."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from arista.db.connection import open_db
from arista.ingest import (
    IngestRecord,
    discover_alex_records,
    ingest_one,
    ingest_stream,
    prepare_db,
)
from arista.preprocess.io import Recording, write_recording_csv

REPO_ROOT = Path(__file__).resolve().parents[1]


# ─────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────


def _synthetic_recording(frames: int = 20) -> Recording:
    rng = np.random.default_rng(0)
    return Recording(
        frame=np.arange(frames),
        time_s=np.linspace(0.0, 2.0, frames),
        sensor_t_c=22.0 + rng.normal(0, 0.05, frames),
        target_t_c=np.full(frames, 22.0),
        drive_t_c=20.0 + rng.normal(0, 0.05, frames),
        dfbf=rng.normal(0, 0.01, frames),
        dfbf_drift_corrected=rng.normal(0, 0.005, frames),
        drift_method="poly",
        recording_date="2021-12-20",
    )


def _ingest_record(
    *,
    csv_path: Path,
    cell_type: str = "CC",
    cell_number: int = 1,
    hemisphere: str | None = "l",
    animal_number: int = 1,
    sex: str = "f",
    arista_suffix: str | None = None,
    notes: str | None = None,
) -> IngestRecord:
    rec = _synthetic_recording()
    write_recording_csv(rec, csv_path)
    return IngestRecord(
        researcher_name="Alexander Busch",
        strain_name="641",
        recording_date="2021-12-20",
        sex=sex,
        animal_number=animal_number,
        arista_suffix=arista_suffix,
        cell_type_code=cell_type,
        cell_number=cell_number,
        hemisphere=hemisphere,
        stimulus_name="ascAmp",
        fps=10.0,
        n_samples=rec.n_frames,
        duration_s=float(rec.time_s[-1]),
        drift_method=rec.drift_method,
        samples_df=rec.to_dataframe(),
        source_csv=csv_path.resolve(),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────
#  ingest_one
# ─────────────────────────────────────────────────────────────────


def test_ingest_one_populates_each_table(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    record = _ingest_record(csv_path=tmp_path / "l_CC01.csv")
    with open_db(db_path) as conn:
        prepare_db(conn)
        recording_id, was_new, n_samples = ingest_one(conn, record)
        assert was_new is True
        assert recording_id > 0
        assert n_samples == 20

        assert conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 20
        assert conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 1


def test_ingest_one_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    record = _ingest_record(csv_path=tmp_path / "l_CC01.csv")
    with open_db(db_path) as conn:
        prepare_db(conn)
        _, was_new_1, _ = ingest_one(conn, record)
        _, was_new_2, _ = ingest_one(conn, record)
        assert was_new_1 is True
        assert was_new_2 is False
        assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 20


def test_left_and_right_same_cell_number_are_distinct(tmp_path: Path) -> None:
    """The hemisphere belongs in the recordings natural key."""
    db_path = tmp_path / "arista.db"
    rec_l = _ingest_record(
        csv_path=tmp_path / "l_CC01.csv", hemisphere="l"
    )
    rec_r = _ingest_record(
        csv_path=tmp_path / "r_CC01.csv", hemisphere="r"
    )
    with open_db(db_path) as conn:
        prepare_db(conn)
        _, was_new_l, _ = ingest_one(conn, rec_l)
        _, was_new_r, _ = ingest_one(conn, rec_r)
        assert was_new_l and was_new_r
        # Same animal but two distinct recordings
        assert conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 2


def test_two_cells_share_one_animal(tmp_path: Path) -> None:
    """CC01 + HC01 from the same fly produce two recordings under one animal."""
    db_path = tmp_path / "arista.db"
    cc = _ingest_record(csv_path=tmp_path / "l_CC01.csv", cell_type="CC")
    hc = _ingest_record(csv_path=tmp_path / "l_HC01.csv", cell_type="HC")
    with open_db(db_path) as conn:
        prepare_db(conn)
        ingest_one(conn, cc)
        ingest_one(conn, hc)
        assert conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 2


def test_two_animals_distinct(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    a1 = _ingest_record(
        csv_path=tmp_path / "f1.csv", animal_number=1, sex="f",
    )
    a2 = _ingest_record(
        csv_path=tmp_path / "f2.csv", animal_number=2, sex="m",
    )
    with open_db(db_path) as conn:
        prepare_db(conn)
        ingest_one(conn, a1)
        ingest_one(conn, a2)
        assert conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0] == 2


def test_source_file_carries_sha256_and_size(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    csv_path = tmp_path / "l_CC01.csv"
    record = _ingest_record(csv_path=csv_path)
    with open_db(db_path) as conn:
        prepare_db(conn)
        ingest_one(conn, record)
        row = conn.execute(
            "SELECT path, kind, sha256, size_bytes FROM source_files"
        ).fetchone()
        assert row[0] == str(csv_path.resolve())
        assert row[1] == "processed_csv"
        assert len(row[2]) == 64  # sha256 hex digest
        assert row[3] == csv_path.stat().st_size


def test_notes_are_persisted_verbatim(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    notes = "Use frames 2-6003. Skip first 18."
    record = _ingest_record(csv_path=tmp_path / "l_CC01.csv", notes=notes)
    with open_db(db_path) as conn:
        prepare_db(conn)
        ingest_one(conn, record)
        stored = conn.execute("SELECT notes FROM recordings").fetchone()[0]
        assert stored == notes


def test_ingest_one_resolves_drift_method(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    record = _ingest_record(csv_path=tmp_path / "l_CC01.csv")
    with open_db(db_path) as conn:
        prepare_db(conn)
        ingest_one(conn, record)
        method = conn.execute(
            "SELECT drift_correction FROM recordings"
        ).fetchone()[0]
    assert method == "poly"


def test_ingest_one_persists_samples_in_order(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    record = _ingest_record(csv_path=tmp_path / "l_CC01.csv")
    with open_db(db_path) as conn:
        prepare_db(conn)
        rec_id, _, _ = ingest_one(conn, record)
        rows = conn.execute(
            "SELECT frame, time_s, sensor_t_c, dfbf FROM samples "
            "WHERE recording_id = ? ORDER BY frame",
            (rec_id,),
        ).fetchall()
    assert len(rows) == 20
    np.testing.assert_array_equal([r[0] for r in rows], np.arange(20))


# ─────────────────────────────────────────────────────────────────
#  ingest_stream
# ─────────────────────────────────────────────────────────────────


def test_ingest_stream_returns_stats(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    records = [
        _ingest_record(csv_path=tmp_path / "l_CC01.csv", cell_type="CC"),
        _ingest_record(csv_path=tmp_path / "l_HC01.csv", cell_type="HC"),
    ]
    with open_db(db_path) as conn:
        prepare_db(conn)
        stats = ingest_stream(conn, records)
    assert stats.inserted_recordings == 2
    assert stats.skipped_duplicates == 0
    assert stats.errors == 0
    assert stats.inserted_samples == 40


def test_ingest_stream_survives_per_record_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "arista.db"
    good = _ingest_record(csv_path=tmp_path / "l_CC01.csv")
    # Force an FK failure with a bogus stimulus name
    bad = _ingest_record(csv_path=tmp_path / "l_HC01.csv", cell_type="HC")
    bad = IngestRecord(
        **{**bad.__dict__, "stimulus_name": "not_a_real_protocol"}
    )
    with open_db(db_path) as conn:
        prepare_db(conn)
        stats = ingest_stream(conn, [good, bad])
    assert stats.inserted_recordings == 1
    assert stats.errors == 1


# ─────────────────────────────────────────────────────────────────
#  End-to-end on the bundled corpus
# ─────────────────────────────────────────────────────────────────


def _bundled_preprocessed_root() -> Path:
    """Preprocess the bundled raw data into a tmp scratch dir for ingest."""
    raise NotImplementedError  # handled in fixture


@pytest.fixture(scope="module")
def bundled_preprocessed(tmp_path_factory) -> Path:
    """Run the POC runner on the in-repo data and return the output root."""
    from arista.preprocess import (
        assemble_recording,
        correct_drift,
        read_fiji_csv,
        read_sensor_mat,
    )

    raw_root = REPO_ROOT / "data" / "raw" / "alex"
    out_root = tmp_path_factory.mktemp("preprocessed_alex")

    for animal_dir in sorted(raw_root.glob("*/*")):
        if not animal_dir.is_dir():
            continue
        mats = list(animal_dir.glob("temperature_data_*.mat"))
        if len(mats) != 1:
            continue
        sensor = read_sensor_mat(mats[0])
        target_dir = out_root / animal_dir.relative_to(raw_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        for csv_path in sorted(animal_dir.glob("[lr]_*.csv")):
            fiji = read_fiji_csv(csv_path)
            rec = assemble_recording(fiji, sensor)
            rec = correct_drift(rec, method="auto")
            from arista.preprocess.io import write_recording_csv
            write_recording_csv(rec, target_dir / csv_path.name)
    return out_root


def test_full_ingest_of_bundled_subset(
    bundled_preprocessed: Path, tmp_path: Path
) -> None:
    """End-to-end: 2 animals (WT_01_f + WT_02_m) → 12 recordings."""
    db_path = tmp_path / "arista.db"
    records = [
        r.record for r in discover_alex_records(bundled_preprocessed)
        if r.record is not None
    ]
    assert len(records) == 12

    with open_db(db_path) as conn:
        prepare_db(conn)
        stats = ingest_stream(conn, records)

    assert stats.errors == 0
    assert stats.inserted_recordings == 12
    assert stats.skipped_duplicates == 0

    with open_db(db_path) as conn:
        animal_count = conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0]
        recording_count = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        sample_count = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    assert animal_count == 2
    assert recording_count == 12
    # Each cell ≈ 6000 samples; allow slop for the post-alignment clip
    assert 70_000 < sample_count < 75_000
