# ─────────────────────────────────────────────────────────────────
#  arista.ingest.orchestrator
#  « insert IngestRecord stream into SQLite, idempotently »
# ─────────────────────────────────────────────────────────────────
"""Insert :class:`IngestRecord` instances into an arista SQLite DB.

The orchestrator runs once per ingest invocation. It is idempotent —
re-running over a corpus that is already in the database is a no-op,
because every INSERT uses ``OR IGNORE`` and natural-key UNIQUE
constraints already protect every dimension table (see
[[Database Schema]]).

Provenance: each ingested CSV is registered in ``source_files`` with
its sha256 + byte size. The ``recordings.processed_file_id`` FK ties
the recording back to the preprocessed CSV; the original Fiji ROI
and sensor MAT are added in a later sprint once
:func:`arista.preprocess.write_recording_csv` also persists those
source paths.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from arista.db.schema import build_schema
from arista.db.seeds import seed_dimensions
from arista.ingest.parsers.alex import IngestRecord

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    """Result tally for one ingest run."""

    inserted_recordings: int = 0
    skipped_duplicates: int = 0
    errors: int = 0
    inserted_samples: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "inserted_recordings": self.inserted_recordings,
            "skipped_duplicates": self.skipped_duplicates,
            "errors": self.errors,
            "inserted_samples": self.inserted_samples,
        }


# ─────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────


def _sha256_of(path: Path, *, chunk_size: int = 1 << 20) -> str:
    """Stream sha256 of a file. 1 MiB chunks; covers any size sensibly."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _scalar(cur: sqlite3.Cursor, sql: str, params: tuple = ()) -> int | None:
    """Return the first column of the first row, or ``None`` if no rows."""
    row = cur.execute(sql, params).fetchone()
    return None if row is None else row[0]


def _lookup_or_insert_source_file(
    cur: sqlite3.Cursor, path: Path, *, kind: str = "processed_csv"
) -> int:
    """Return source_files.file_id for *path*, inserting if needed.

    Re-uses an existing row when the path is already registered; the
    schema's UNIQUE constraint on ``source_files.path`` keeps us honest.
    """
    existing = _scalar(
        cur, "SELECT file_id FROM source_files WHERE path = ?", (str(path),)
    )
    if existing is not None:
        return int(existing)
    cur.execute(
        """
        INSERT INTO source_files (path, kind, sha256, size_bytes)
        VALUES (?, ?, ?, ?)
        """,
        (str(path), kind, _sha256_of(path), path.stat().st_size),
    )
    return int(cur.lastrowid)


def _lookup_or_insert_animal(cur: sqlite3.Cursor, record: IngestRecord) -> int:
    """Resolve (researcher, date, sex, animal_number, suffix) → animal_id."""
    researcher_id = _scalar(
        cur, "SELECT researcher_id FROM researchers WHERE name = ?",
        (record.researcher_name,),
    )
    if researcher_id is None:
        raise LookupError(
            f"researcher {record.researcher_name!r} not seeded; "
            f"run seed_dimensions() first"
        )
    strain_id = _scalar(
        cur, "SELECT strain_id FROM strains WHERE strain_name = ?",
        (record.strain_name,),
    )
    if strain_id is None:
        cur.execute(
            "INSERT INTO strains (strain_name) VALUES (?)",
            (record.strain_name,),
        )
        strain_id = int(cur.lastrowid)

    # SQLite treats NULL values in UNIQUE constraints as distinct, so
    # naive INSERT OR IGNORE will create a fresh animal row per cell
    # whenever ``arista_suffix`` is NULL (which it almost always is in
    # Alex's tree). Lookup-first sidesteps that: we explicitly match
    # with IS NULL so a second cell from the same animal resolves to
    # the existing row rather than allocating a new one.
    suffix_clause = (
        "arista_suffix IS NULL" if record.arista_suffix is None
        else "arista_suffix = ?"
    )
    lookup_params: tuple = (
        researcher_id, record.recording_date, record.sex, record.animal_number,
    )
    if record.arista_suffix is not None:
        lookup_params = (*lookup_params, record.arista_suffix)

    animal_id = _scalar(
        cur,
        f"""
        SELECT animal_id FROM animals
        WHERE researcher_id = ? AND recording_date = ? AND sex = ?
              AND animal_number = ? AND {suffix_clause}
        """,
        lookup_params,
    )
    if animal_id is not None:
        return int(animal_id)

    cur.execute(
        """
        INSERT INTO animals
            (researcher_id, strain_id, recording_date, sex,
             animal_number, arista_suffix)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (researcher_id, strain_id, record.recording_date, record.sex,
         record.animal_number, record.arista_suffix),
    )
    return int(cur.lastrowid)


def _lookup_or_insert_recording(
    cur: sqlite3.Cursor,
    record: IngestRecord,
    animal_id: int,
    processed_file_id: int,
) -> tuple[int, bool]:
    """Insert the recording row if new, return ``(recording_id, was_new)``."""
    cell_type_id = _scalar(
        cur, "SELECT cell_type_id FROM cell_types WHERE code = ?",
        (record.cell_type_code,),
    )
    if cell_type_id is None:
        raise LookupError(f"cell_type {record.cell_type_code!r} not seeded")
    stimulus_id = _scalar(
        cur, "SELECT stimulus_id FROM stimulus_protocols WHERE name = ?",
        (record.stimulus_name,),
    )
    if stimulus_id is None:
        raise LookupError(f"stimulus {record.stimulus_name!r} not seeded")

    # hemisphere is part of the recordings natural key (left vs right
    # arista with the same cell_number are different cells). NULL
    # hemispheres compare non-equal in SQLite UNIQUE, so we use IS to
    # match them explicitly in the existing-row lookup.
    hemisphere_clause = (
        "hemisphere IS NULL" if record.hemisphere is None
        else "hemisphere = ?"
    )
    existing_params: tuple = (
        animal_id, cell_type_id, record.cell_number, stimulus_id,
    )
    if record.hemisphere is not None:
        existing_params = (*existing_params, record.hemisphere)
    existing = _scalar(
        cur,
        f"""
        SELECT recording_id FROM recordings
        WHERE animal_id = ? AND cell_type_id = ? AND cell_number = ?
              AND stimulus_id = ? AND {hemisphere_clause}
        """,
        existing_params,
    )
    if existing is not None:
        return int(existing), False

    cur.execute(
        """
        INSERT INTO recordings
            (animal_id, cell_type_id, cell_number, stimulus_id, hemisphere,
             fps, n_samples, duration_s, drift_correction,
             processed_file_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (animal_id, cell_type_id, record.cell_number, stimulus_id,
         record.hemisphere, record.fps, record.n_samples, record.duration_s,
         record.drift_method, processed_file_id, record.notes),
    )
    return int(cur.lastrowid), True


def _bulk_insert_samples(
    cur: sqlite3.Cursor, recording_id: int, record: IngestRecord
) -> int:
    """Bulk-insert the samples for one recording; returns row count inserted."""
    df = record.samples_df
    columns = [
        "frame", "time_s", "sensor_t_c", "target_t_c",
        "drive_t_c", "dfbf", "dfbf_drift_corrected",
    ]
    # Provide NULL for absent optional columns rather than KeyError.
    for col in ("drive_t_c", "dfbf_drift_corrected"):
        if col not in df.columns:
            df = df.assign(**{col: None})
    rows = [
        (
            recording_id,
            int(r["frame"]),
            float(r["time_s"]),
            None if (v := r["sensor_t_c"]) is None or _isnan(v) else float(v),
            None if (v := r["target_t_c"]) is None or _isnan(v) else float(v),
            None if (v := r["drive_t_c"]) is None or _isnan(v) else float(v),
            float(r["dfbf"]),
            None if (v := r["dfbf_drift_corrected"]) is None or _isnan(v) else float(v),
        )
        for _, r in df[columns].iterrows()
    ]
    cur.executemany(
        """
        INSERT OR IGNORE INTO samples
            (recording_id, frame, time_s, sensor_t_c, target_t_c,
             drive_t_c, dfbf, dfbf_drift_corrected)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return cur.rowcount if cur.rowcount >= 0 else len(rows)


def _isnan(value) -> bool:
    """``math.isnan`` but tolerant of None / non-numeric."""
    try:
        return value != value  # NaN ≠ NaN
    except TypeError:
        return False


# ─────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────


def prepare_db(conn: sqlite3.Connection) -> None:
    """Apply schema + seeds. Safe to call on a fresh or populated DB."""
    build_schema(conn)
    seed_dimensions(conn)


def ingest_one(conn: sqlite3.Connection, record: IngestRecord) -> tuple[int, bool, int]:
    """Insert one :class:`IngestRecord` and commit.

    Returns:
        Triple ``(recording_id, was_new, n_samples_inserted)``.
        ``was_new`` is ``False`` when the recording's natural key was
        already present (re-ingest skipped); in that case samples are
        also not re-inserted.
    """
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        processed_file_id = _lookup_or_insert_source_file(cur, record.source_csv)
        animal_id = _lookup_or_insert_animal(cur, record)
        recording_id, was_new = _lookup_or_insert_recording(
            cur, record, animal_id, processed_file_id
        )
        n_samples = 0
        if was_new:
            n_samples = _bulk_insert_samples(cur, recording_id, record)
        conn.commit()
        return recording_id, was_new, n_samples
    except Exception:
        conn.rollback()
        raise


def ingest_stream(
    conn: sqlite3.Connection,
    records: Iterable[IngestRecord],
) -> IngestStats:
    """Ingest every record from *records*. Survives per-record failures.

    Errors are logged and counted; the orchestrator does not abort the
    whole run on one bad recording so a corpus-wide ingest can complete
    even if a handful of files are malformed.
    """
    stats = IngestStats()
    for record in records:
        try:
            _, was_new, n_samples = ingest_one(conn, record)
            if was_new:
                stats.inserted_recordings += 1
                stats.inserted_samples += n_samples
            else:
                stats.skipped_duplicates += 1
        except Exception as exc:  # noqa: BLE001
            log.error(
                "FAIL recording %s: %s",
                record.source_csv,
                exc,
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            stats.errors += 1
    return stats
