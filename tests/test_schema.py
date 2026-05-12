# ─────────────────────────────────────────────────────────────────
#  Tests for arista.db.schema and arista.db.seeds
# ─────────────────────────────────────────────────────────────────
"""Schema round-trip + FK + CHECK constraint regression tests."""

from __future__ import annotations

import json
import sqlite3

import pytest

from arista.db.schema import build_schema
from arista.db.seeds import seed_dimensions


@pytest.fixture
def db() -> sqlite3.Connection:
    """Fresh in-memory database with schema + dimensions seeded."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    build_schema(conn)
    seed_dimensions(conn)
    yield conn
    conn.close()


# ─────────────────────────────────────────────────────────────────
#  Schema structure
# ─────────────────────────────────────────────────────────────────

def test_all_tables_created(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "researchers",
        "strains",
        "cell_types",
        "stimulus_protocols",
        "source_files",
        "animals",
        "recordings",
        "samples",
        "stimulus_responses",
    }
    assert expected.issubset(names)


def test_all_indexes_created(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "idx_rec_animal",
        "idx_rec_stim_cell",
        "idx_rec_qc",
        "idx_animal_strain",
        "idx_animal_researcher_date",
        "idx_resp_rec",
        "idx_source_kind",
    }
    assert expected.issubset(names)


def test_samples_is_without_rowid(db: sqlite3.Connection) -> None:
    """Largest table must use WITHOUT ROWID for space + lookup speed."""
    ddl = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='samples'"
    ).fetchone()[0]
    assert "WITHOUT ROWID" in ddl


def test_foreign_keys_enabled(db: sqlite3.Connection) -> None:
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# ─────────────────────────────────────────────────────────────────
#  Seed data sanity
# ─────────────────────────────────────────────────────────────────

def test_four_researchers_seeded(db: sqlite3.Connection) -> None:
    n = db.execute("SELECT COUNT(*) FROM researchers").fetchone()[0]
    assert n == 4
    names = {r[0] for r in db.execute("SELECT name FROM researchers")}
    assert "Alexander Busch" in names  # the addition that motivated the merge


def test_three_cell_types_seeded(db: sqlite3.Connection) -> None:
    codes = {r[0] for r in db.execute("SELECT code FROM cell_types")}
    assert codes == {"CC", "HC", "WC"}


def test_stimulus_protocols_seeded(db: sqlite3.Connection) -> None:
    names = {r[0] for r in db.execute("SELECT name FROM stimulus_protocols")}
    # Must contain all six canonical Robert protocols plus Bending
    for required in (
        "ascAmp", "ascAmpFlip", "descAmp", "descAmpFlip",
        "adaptation", "ColdAdapt", "HotAdapt", "Bending",
    ):
        assert required in names, f"missing {required!r}"


def test_ascamp_sequence_round_trips(db: sqlite3.Connection) -> None:
    """JSON-encoded target sequences survive a round trip."""
    blob = db.execute(
        "SELECT target_sequence_json FROM stimulus_protocols WHERE name='ascAmp'"
    ).fetchone()[0]
    sequence = json.loads(blob)
    assert sequence == [22.0, 22.5, 21.5, 23.0, 21.0, 24.0, 20.0, 26.0, 18.0]


def test_bending_has_no_sequence(db: sqlite3.Connection) -> None:
    blob = db.execute(
        "SELECT target_sequence_json FROM stimulus_protocols WHERE name='Bending'"
    ).fetchone()[0]
    assert blob is None


def test_canonical_strains_seeded(db: sqlite3.Connection) -> None:
    names = {r[0] for r in db.execute("SELECT strain_name FROM strains")}
    for required in ("CantonS", "NompC3", "white", "641"):
        assert required in names, f"missing strain {required!r}"


def test_seed_is_idempotent(db: sqlite3.Connection) -> None:
    """Re-seeding does not duplicate rows."""
    seed_dimensions(db)  # already once via fixture, now twice
    assert db.execute("SELECT COUNT(*) FROM researchers").fetchone()[0] == 4
    assert db.execute("SELECT COUNT(*) FROM cell_types").fetchone()[0] == 3


# ─────────────────────────────────────────────────────────────────
#  FK + CHECK constraints
# ─────────────────────────────────────────────────────────────────

def _strain_id(db: sqlite3.Connection, name: str) -> int:
    return db.execute(
        "SELECT strain_id FROM strains WHERE strain_name = ?", (name,)
    ).fetchone()[0]


def _researcher_id(db: sqlite3.Connection, name: str) -> int:
    return db.execute(
        "SELECT researcher_id FROM researchers WHERE name = ?", (name,)
    ).fetchone()[0]


def test_fk_violation_on_unknown_strain(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO animals "
            "(researcher_id, strain_id, recording_date, sex, animal_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (1, 99_999, "2020-01-01", "m", 1),
        )


def test_fk_violation_on_unknown_researcher(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO animals "
            "(researcher_id, strain_id, recording_date, sex, animal_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (99_999, _strain_id(db, "CantonS"), "2020-01-01", "m", 1),
        )


def test_sex_check_constraint(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO animals "
            "(researcher_id, strain_id, recording_date, sex, animal_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (_researcher_id(db, "Robert Kossen"),
             _strain_id(db, "CantonS"),
             "2020-01-01", "X", 1),
        )


def test_hemisphere_check_constraint(db: sqlite3.Connection) -> None:
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animals "
        "(researcher_id, strain_id, recording_date, sex, animal_number) "
        "VALUES (?, ?, ?, ?, ?)",
        (_researcher_id(db, "Robert Kossen"),
         _strain_id(db, "CantonS"),
         "2020-01-01", "m", 1),
    )
    animal_id = cur.lastrowid
    cell_type_id = db.execute(
        "SELECT cell_type_id FROM cell_types WHERE code='HC'"
    ).fetchone()[0]
    stimulus_id = db.execute(
        "SELECT stimulus_id FROM stimulus_protocols WHERE name='ascAmp'"
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO recordings "
            "(animal_id, cell_type_id, cell_number, stimulus_id, hemisphere) "
            "VALUES (?, ?, ?, ?, ?)",
            (animal_id, cell_type_id, 1, stimulus_id, "X"),
        )


def test_drift_correction_check_constraint(db: sqlite3.Connection) -> None:
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animals "
        "(researcher_id, strain_id, recording_date, sex, animal_number) "
        "VALUES (?, ?, ?, ?, ?)",
        (_researcher_id(db, "Robert Kossen"),
         _strain_id(db, "CantonS"),
         "2020-01-01", "m", 1),
    )
    animal_id = cur.lastrowid
    cell_type_id = db.execute(
        "SELECT cell_type_id FROM cell_types WHERE code='HC'"
    ).fetchone()[0]
    stimulus_id = db.execute(
        "SELECT stimulus_id FROM stimulus_protocols WHERE name='ascAmp'"
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO recordings "
            "(animal_id, cell_type_id, cell_number, stimulus_id, drift_correction) "
            "VALUES (?, ?, ?, ?, ?)",
            (animal_id, cell_type_id, 1, stimulus_id, "magic"),
        )


# ─────────────────────────────────────────────────────────────────
#  End-to-end happy path
# ─────────────────────────────────────────────────────────────────

def test_full_happy_path_insert(db: sqlite3.Connection) -> None:
    """Insert one source file, one animal, one recording, one sample row."""
    cur = db.cursor()

    cur.execute(
        "INSERT INTO source_files (path, kind, sha256, size_bytes) "
        "VALUES (?, ?, ?, ?)",
        ("/tmp/fake.csv", "fiji_csv", "deadbeef", 4242),
    )
    file_id = cur.lastrowid

    cur.execute(
        "INSERT INTO animals "
        "(researcher_id, strain_id, recording_date, sex, animal_number) "
        "VALUES (?, ?, ?, ?, ?)",
        (_researcher_id(db, "Alexander Busch"),
         _strain_id(db, "641"),
         "2021-12-20", "f", 2),
    )
    animal_id = cur.lastrowid

    cell_type_id = db.execute(
        "SELECT cell_type_id FROM cell_types WHERE code='CC'"
    ).fetchone()[0]
    stimulus_id = db.execute(
        "SELECT stimulus_id FROM stimulus_protocols WHERE name='ascAmp'"
    ).fetchone()[0]

    cur.execute(
        "INSERT INTO recordings "
        "(animal_id, cell_type_id, cell_number, stimulus_id, hemisphere, "
        " response_file_id, drift_correction) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (animal_id, cell_type_id, 1, stimulus_id, "l", file_id, "poly"),
    )
    recording_id = cur.lastrowid

    cur.execute(
        "INSERT INTO samples "
        "(recording_id, frame, time_s, sensor_t_c, target_t_c, dfbf) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (recording_id, 0, 0.0, 22.0, 22.0, -0.001590),
    )
    db.commit()

    # Read it back via the join we'll use in real queries
    row = db.execute(
        """
        SELECT a.recording_date, ct.code, sp.name, s.dfbf
        FROM samples s
        JOIN recordings r  ON r.recording_id = s.recording_id
        JOIN animals    a  ON a.animal_id    = r.animal_id
        JOIN cell_types ct ON ct.cell_type_id = r.cell_type_id
        JOIN stimulus_protocols sp ON sp.stimulus_id = r.stimulus_id
        WHERE s.frame = 0
        """
    ).fetchone()
    assert row == ("2021-12-20", "CC", "ascAmp", -0.001590)
