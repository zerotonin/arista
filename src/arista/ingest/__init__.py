# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — ingest                                                 ║
# ║  « load preprocessed CSVs into SQLite »                          ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Parser per data source (Robert / Niko / Laurin) plus an         ║
# ║  orchestrator that walks /mnt/hcs, dispatches, and inserts.      ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Database ingestion. Contents filled in sprints 5-6."""

from __future__ import annotations
