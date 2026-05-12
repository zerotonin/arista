# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — db.seeds                                               ║
# ║  « dimension-table seeds: researchers, cell_types, stimulus,     ║
# ║    strains »                                                     ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Inserts every entry that's known at design time into the four   ║
# ║  controlled-vocabulary tables. Researchers and cell-types are    ║
# ║  fixed; stimulus_protocols and strains will grow as new          ║
# ║  experiments are added, but every entry shipped here is one we   ║
# ║  expect ingest to see.                                           ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Seed the controlled-vocabulary dimension tables."""

from __future__ import annotations

import json
import sqlite3

from arista.constants import (
    CANONICAL_STRAINS,
    CELL_TYPES,
    STIMULUS_PROTOCOLS,
)

# ─────────────────────────────────────────────────────────────────
#  Researcher catalogue  « four students contributing Ca²⁺ data »
# ─────────────────────────────────────────────────────────────────
# Anne Oepen contributed behaviour-only data (see [[Data Sources]] §
# Anne Oepen) and is intentionally NOT in this list — the v1.0.0 DB is
# Ca²⁺-only.
RESEARCHERS: tuple[tuple[str, str, str], ...] = (
    ("Robert Kossen",   "PhD",      "2016–2019"),
    ("Niko",            "MSc",      "2016"),
    ("Laurin Büld",     "MSc",      "2020–2021"),
    ("Alexander Busch", "post-BSc", "2021–2022"),
)


def seed_researchers(conn: sqlite3.Connection) -> None:
    """Insert the four researcher rows. Idempotent via ``INSERT OR IGNORE``."""
    conn.executemany(
        "INSERT OR IGNORE INTO researchers (name, role, period) VALUES (?, ?, ?)",
        RESEARCHERS,
    )


def seed_cell_types(conn: sqlite3.Connection) -> None:
    """Insert CC / HC / WC entries from :data:`arista.constants.CELL_TYPES`."""
    conn.executemany(
        "INSERT OR IGNORE INTO cell_types (code, name, description) VALUES (?, ?, ?)",
        [(ct.code, ct.name, ct.description) for ct in CELL_TYPES.values()],
    )


def seed_stimulus_protocols(conn: sqlite3.Connection) -> None:
    """Insert every protocol from :data:`arista.constants.STIMULUS_PROTOCOLS`.

    The ``target_sequence`` tuple is serialised as a JSON array string
    so ``json_each()`` can unroll it later inside SQL queries.
    """
    rows = [
        (
            p.name,
            p.family,
            p.description,
            json.dumps(list(p.target_sequence)) if p.target_sequence else None,
        )
        for p in STIMULUS_PROTOCOLS.values()
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stimulus_protocols "
        "(name, family, description, target_sequence_json) VALUES (?, ?, ?, ?)",
        rows,
    )


def seed_strains(conn: sqlite3.Connection) -> None:
    """Insert the canonical strain list as starter rows.

    Strains continue to grow over time; this seed only guarantees the
    documented ones exist on first DB build. The ingester inserts any
    additional strain it encounters via :func:`ensure_strain`.
    """
    conn.executemany(
        "INSERT OR IGNORE INTO strains (strain_name) VALUES (?)",
        [(s,) for s in CANONICAL_STRAINS],
    )


def seed_dimensions(conn: sqlite3.Connection) -> None:
    """Apply every dimension seed in dependency order and commit."""
    seed_researchers(conn)
    seed_cell_types(conn)
    seed_stimulus_protocols(conn)
    seed_strains(conn)
    conn.commit()
