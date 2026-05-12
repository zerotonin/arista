# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — db.schema                                              ║
# ║  « SQLite CREATE statements + build_schema(conn) »               ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Single source of truth for the arista.db structure.             ║
# ║                                                                  ║
# ║  Five dimensions (researchers, strains, cell_types,              ║
# ║  stimulus_protocols, source_files) plus the half-dimension       ║
# ║  animals, the recordings fact table, the samples long fact, and  ║
# ║  the per-step stimulus_responses table.                          ║
# ║                                                                  ║
# ║  Mirrors [[Database Schema]] in the project notebook; the SQL    ║
# ║  below is the canonical form. Foreign keys are enforced.         ║
# ╚══════════════════════════════════════════════════════════════════╝
"""SQLite schema for the arista calcium-imaging corpus."""

from __future__ import annotations

import sqlite3

SCHEMA_SQL: str = """
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────
--  Dimension tables
-- ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS researchers (
    researcher_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    role          TEXT,
    period        TEXT
);

CREATE TABLE IF NOT EXISTS strains (
    strain_id   INTEGER PRIMARY KEY,
    strain_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS cell_types (
    cell_type_id INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS stimulus_protocols (
    stimulus_id          INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL UNIQUE,
    family               TEXT NOT NULL
                            CHECK (family IN ('thermal_step',
                                              'thermal_adapt',
                                              'mechanical')),
    description          TEXT,
    target_sequence_json TEXT
);

CREATE TABLE IF NOT EXISTS source_files (
    file_id      INTEGER PRIMARY KEY,
    path         TEXT NOT NULL UNIQUE,
    kind         TEXT NOT NULL
                    CHECK (kind IN ('fiji_csv',
                                    'fiji_txt',
                                    'sensor_mat',
                                    'sensor_txt',
                                    'processed_csv',
                                    'processed_txt',
                                    'raw_movie',
                                    'raw_movie_tar')),
    archive_path TEXT,
    sha256       TEXT,
    size_bytes   INTEGER,
    ingested_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────────
--  Half-dimension / fact tables
-- ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS animals (
    animal_id      INTEGER PRIMARY KEY,
    researcher_id  INTEGER NOT NULL REFERENCES researchers(researcher_id),
    strain_id      INTEGER NOT NULL REFERENCES strains(strain_id),
    recording_date TEXT    NOT NULL,
    sex            TEXT    NOT NULL CHECK (sex IN ('m','f','u')),
    animal_number  INTEGER NOT NULL,
    arista_suffix  TEXT,
    notes          TEXT,
    UNIQUE (researcher_id, recording_date, sex, animal_number, arista_suffix)
);

CREATE TABLE IF NOT EXISTS recordings (
    recording_id        INTEGER PRIMARY KEY,
    animal_id           INTEGER NOT NULL REFERENCES animals(animal_id),
    cell_type_id        INTEGER NOT NULL REFERENCES cell_types(cell_type_id),
    cell_number         INTEGER NOT NULL,
    stimulus_id         INTEGER NOT NULL REFERENCES stimulus_protocols(stimulus_id),
    hemisphere          TEXT CHECK (hemisphere IN ('l','r') OR hemisphere IS NULL),
    fps                 REAL    NOT NULL DEFAULT 10.0,
    n_samples           INTEGER,
    duration_s          REAL,
    drift_correction    TEXT CHECK (drift_correction IN
                            ('linear','poly','exp','none','unknown'))
                            DEFAULT 'unknown',
    temperature_source  TEXT CHECK (temperature_source IN
                            ('original','median_template','interpolated','none'))
                            DEFAULT 'original',
    qc_flag             TEXT,
    response_file_id    INTEGER REFERENCES source_files(file_id),
    sensor_file_id      INTEGER REFERENCES source_files(file_id),
    processed_file_id   INTEGER REFERENCES source_files(file_id),
    raw_movie_file_id   INTEGER REFERENCES source_files(file_id),
    notes               TEXT,
    UNIQUE (animal_id, cell_type_id, cell_number, stimulus_id)
);

CREATE TABLE IF NOT EXISTS samples (
    recording_id         INTEGER NOT NULL REFERENCES recordings(recording_id),
    frame                INTEGER NOT NULL,
    time_s               REAL    NOT NULL,
    sensor_t_c           REAL,
    target_t_c           REAL,
    drive_t_c            REAL,
    dfbf                 REAL    NOT NULL,
    dfbf_drift_corrected REAL,
    PRIMARY KEY (recording_id, frame)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS stimulus_responses (
    response_id          INTEGER PRIMARY KEY,
    recording_id         INTEGER NOT NULL REFERENCES recordings(recording_id),
    step_index           INTEGER NOT NULL,
    target_temp_c        REAL    NOT NULL,
    delta_target_c       REAL,
    observed_temp_median REAL,
    dfbf_response_median REAL    NOT NULL,
    n_frames_in_window   INTEGER,
    UNIQUE (recording_id, step_index)
);

-- ─────────────────────────────────────────────────────────────────
--  Indexes  « accelerate the dominant queries »
-- ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_rec_animal
    ON recordings (animal_id);

CREATE INDEX IF NOT EXISTS idx_rec_stim_cell
    ON recordings (stimulus_id, cell_type_id);

CREATE INDEX IF NOT EXISTS idx_rec_qc
    ON recordings (qc_flag) WHERE qc_flag IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_animal_strain
    ON animals (strain_id);

CREATE INDEX IF NOT EXISTS idx_animal_researcher_date
    ON animals (researcher_id, recording_date);

CREATE INDEX IF NOT EXISTS idx_resp_rec
    ON stimulus_responses (recording_id);

CREATE INDEX IF NOT EXISTS idx_source_kind
    ON source_files (kind);
"""


def build_schema(conn: sqlite3.Connection) -> None:
    """Apply the full schema to a fresh database connection.

    Idempotent — every ``CREATE`` uses ``IF NOT EXISTS`` so re-running
    against an already-populated database is a no-op. Foreign-key
    enforcement is enabled via ``PRAGMA``.

    Args:
        conn: An open SQLite connection (typically to ``arista.db`` or
            ``:memory:`` for tests).
    """
    conn.executescript(SCHEMA_SQL)
    conn.commit()
