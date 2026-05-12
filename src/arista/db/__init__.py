# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — db                                                     ║
# ║  « SQLite schema, seeds, and canonical queries »                 ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  schema.py and seeds.py build a fresh arista.db; queries.py      ║
# ║  centralises the SELECT statements consumed by viz/.             ║
# ╚══════════════════════════════════════════════════════════════════╝
"""SQLite schema, seeds, queries, and connection helpers."""

from __future__ import annotations

from arista.db.connection import open_db, resolve_db_path
from arista.db.schema import build_schema
from arista.db.seeds import seed_dimensions

__all__ = [
    "build_schema",
    "open_db",
    "resolve_db_path",
    "seed_dimensions",
]
