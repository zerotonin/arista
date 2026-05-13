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

# ─────────────────────────────────────────────────────────────────
#  Layout
# ─────────────────────────────────────────────────────────────────
# Schema build runs in two phases:
#
#   1. _TABLES_AND_VIEWS_SQL — tables + view in one executescript
#      (cheap regardless of corpus size).
#   2. _INDEX_DDL            — list of individual CREATE INDEX
#      statements run one at a time so build_schema() can drive a
#      tqdm progress bar. CREATE INDEX on a populated table can take
#      seconds to minutes at scale and going silent during that wait
#      makes the run look hung.
#
# SCHEMA_SQL combines both into the historical all-in-one string so
# external callers / docs / manual sqlite3 ".read" usage keep working.

_TABLES_AND_VIEWS_SQL: str = """
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
    -- hemisphere is part of the natural key: an animal can yield CC01
    -- in the left arista AND CC01 in the right arista, which are
    -- genuinely different cells under the same fly. NULL hemispheres
    -- (pooled / unspecified) compare non-equal in SQLite, so multiple
    -- pooled-hemisphere recordings with otherwise matching keys are
    -- still permitted.
    UNIQUE (animal_id, cell_type_id, cell_number, stimulus_id, hemisphere)
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

-- One exponential-decay fit per HotAdapt / ColdAdapt recording. The
-- table is intentionally narrow (one row per recording) with the
-- recording_id as PRIMARY KEY so re-running the processor with
-- ``OR REPLACE`` semantics is a single upsert. Recordings whose
-- stimulus is anything other than thermal_adapt never appear here.
CREATE TABLE IF NOT EXISTS adaptation_fits (
    recording_id       INTEGER PRIMARY KEY
                       REFERENCES recordings(recording_id),
    tau_s              REAL    NOT NULL,
    amplitude          REAL    NOT NULL,
    asymptote          REAL    NOT NULL,
    r_squared          REAL,
    fit_window_start_s REAL    NOT NULL,
    fit_window_end_s   REAL    NOT NULL,
    n_points           INTEGER NOT NULL
);

-- ─────────────────────────────────────────────────────────────────
--  Convenience views  « pre-joined recording metadata »
-- ─────────────────────────────────────────────────────────────────
--
-- recordings.animal_id is the only direct FK to the animal-side
-- dimensions; researcher / strain / etc. are reached transitively
-- through animals. That's the correct normalised design but it makes
-- ad-hoc SQL noisy ("which recordings are by Alex?" should not need
-- a four-table JOIN by hand). v_recordings flattens the chain so
-- every recording row exposes its researcher_name, strain_name,
-- cell-type code and stimulus name in one shot.

CREATE VIEW IF NOT EXISTS v_recordings AS
SELECT
    r.recording_id,
    r.animal_id,
    a.researcher_id,
    res.name           AS researcher_name,
    a.strain_id,
    s.strain_name,
    a.recording_date,
    a.sex,
    a.animal_number,
    a.arista_suffix,
    r.cell_type_id,
    ct.code            AS cell_type,
    r.cell_number,
    r.hemisphere,
    r.stimulus_id,
    sp.name            AS stimulus_name,
    sp.family          AS stimulus_family,
    r.fps,
    r.n_samples,
    r.duration_s,
    r.drift_correction,
    r.temperature_source,
    r.qc_flag,
    r.response_file_id,
    r.sensor_file_id,
    r.processed_file_id,
    r.raw_movie_file_id,
    r.notes
FROM recordings r
JOIN animals            a   ON a.animal_id       = r.animal_id
JOIN researchers        res ON res.researcher_id = a.researcher_id
JOIN strains            s   ON s.strain_id       = a.strain_id
JOIN cell_types         ct  ON ct.cell_type_id   = r.cell_type_id
JOIN stimulus_protocols sp  ON sp.stimulus_id    = r.stimulus_id;
"""


# ─────────────────────────────────────────────────────────────────
#  Index DDL  « one statement per item so tqdm can report progress »
# ─────────────────────────────────────────────────────────────────
# Each tuple is ``(short_label, sql)``. The label is what shows in the
# tqdm bar's postfix ("idx_rec_animal"), the sql is the statement to
# execute. CREATE INDEX IF NOT EXISTS makes every entry idempotent.

_INDEX_DDL: list[tuple[str, str]] = [
    # ── FK-acceleration indexes (Phase 1) ─────────────────────────
    ("idx_rec_animal",
        "CREATE INDEX IF NOT EXISTS idx_rec_animal ON recordings (animal_id)"),
    ("idx_rec_stim_cell",
        "CREATE INDEX IF NOT EXISTS idx_rec_stim_cell "
        "ON recordings (stimulus_id, cell_type_id)"),
    ("idx_rec_qc",
        "CREATE INDEX IF NOT EXISTS idx_rec_qc "
        "ON recordings (qc_flag) WHERE qc_flag IS NOT NULL"),
    ("idx_animal_strain",
        "CREATE INDEX IF NOT EXISTS idx_animal_strain ON animals (strain_id)"),
    ("idx_animal_researcher_date",
        "CREATE INDEX IF NOT EXISTS idx_animal_researcher_date "
        "ON animals (researcher_id, recording_date)"),
    ("idx_resp_rec",
        "CREATE INDEX IF NOT EXISTS idx_resp_rec ON stimulus_responses (recording_id)"),
    ("idx_source_kind",
        "CREATE INDEX IF NOT EXISTS idx_source_kind ON source_files (kind)"),
    # ── Analysis-time single-column filter indexes (Phase 5) ──────
    # idx_rec_stim_cell only helps queries filtering on BOTH columns;
    # analysis routinely filters on one alone. Single-column indexes
    # below give the planner a leaf-level scan rather than a table scan.
    ("idx_rec_cell_type",                    # "all CC cells", "all HC cells"
        "CREATE INDEX IF NOT EXISTS idx_rec_cell_type ON recordings (cell_type_id)"),
    ("idx_rec_stimulus",                     # "all ascAmp recordings"
        "CREATE INDEX IF NOT EXISTS idx_rec_stimulus ON recordings (stimulus_id)"),
    ("idx_rec_hemisphere",                   # "left vs right arista"
        "CREATE INDEX IF NOT EXISTS idx_rec_hemisphere "
        "ON recordings (hemisphere) WHERE hemisphere IS NOT NULL"),
    ("idx_rec_drift_correction",             # "all poly-corrected" / "unknown"
        "CREATE INDEX IF NOT EXISTS idx_rec_drift_correction "
        "ON recordings (drift_correction)"),
    ("idx_animal_sex",                       # "all female flies"
        "CREATE INDEX IF NOT EXISTS idx_animal_sex ON animals (sex)"),
    # ── stimulus_responses indexes (Phase 6 will populate this table)
    ("idx_resp_step_index",                  # "step 0 medians across corpus"
        "CREATE INDEX IF NOT EXISTS idx_resp_step_index "
        "ON stimulus_responses (step_index)"),
    ("idx_resp_target_temp",                 # "responses at +6 °C"
        "CREATE INDEX IF NOT EXISTS idx_resp_target_temp "
        "ON stimulus_responses (target_temp_c)"),
]


# All-in-one string preserved for callers that want to .read it via
# the sqlite3 CLI or quote it in docs. tqdm progress is unavailable
# from this form — use build_schema(conn, progress=...) for that.
SCHEMA_SQL: str = (
    _TABLES_AND_VIEWS_SQL.rstrip()
    + "\n\n-- ─── Indexes ───\n"
    + "\n".join(sql + ";" for _, sql in _INDEX_DDL)
    + "\n"
)


def build_schema(
    conn: sqlite3.Connection,
    *,
    progress: bool | None = None,
) -> None:
    """Apply the full schema to a database connection.

    Idempotent: every ``CREATE`` uses ``IF NOT EXISTS`` so re-running
    against an already-populated database is a no-op. Foreign-key
    enforcement is enabled via ``PRAGMA``.

    Tables and the ``v_recordings`` view are applied in one
    ``executescript`` call (cheap regardless of corpus size). Indexes
    are applied one at a time so a tqdm progress bar can report which
    index is currently being built — at scale a single ``CREATE
    INDEX`` on a populated table can take seconds to minutes and
    going silent during that wait makes the run look hung.

    Args:
        conn: An open SQLite connection (typically to ``arista.db`` or
            ``:memory:`` for tests).
        progress: Controls the index-creation progress bar.
            ``None`` (default) auto-detects: shows when stdout is a
            TTY, hides otherwise (the typical pytest setup, so test
            fixtures don't need to pass anything).
            ``True`` forces the bar on; ``False`` forces it off.
    """
    conn.executescript(_TABLES_AND_VIEWS_SQL)
    _build_indexes(conn, progress=progress)
    conn.commit()


def _build_indexes(
    conn: sqlite3.Connection,
    *,
    progress: bool | None = None,
) -> None:
    """Create every index in :data:`_INDEX_DDL` one at a time.

    Lazy ``tqdm`` import so the schema module stays cheap to load for
    callers that only need the SQL string (docs / one-off SQLite CLI).
    """
    from tqdm.auto import tqdm

    disable = None if progress is None else not progress
    bar = tqdm(_INDEX_DDL, desc="Building indexes", unit="idx", disable=disable)
    for label, sql in bar:
        bar.set_postfix_str(label, refresh=False)
        conn.execute(sql)
