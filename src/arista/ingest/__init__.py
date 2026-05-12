# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — ingest                                                 ║
# ║  « load preprocessed CSVs into SQLite »                          ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Parser per data source (Robert / Niko / Laurin) plus an         ║
# ║  orchestrator that walks /mnt/hcs, dispatches, and inserts.      ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Database ingestion — discover preprocessed CSVs, insert into SQLite."""

from __future__ import annotations

from arista.ingest.metadata import AnimalLabel, parse_animal_label
from arista.ingest.orchestrator import (
    IngestStats,
    ingest_one,
    ingest_stream,
    prepare_db,
)
from arista.ingest.parsers.alex import (
    ALEX_RESEARCHER_NAME,
    DEFAULT_STIMULUS_NAME,
    DiscoveryResult,
    IngestRecord,
    discover_alex_records,
)

__all__ = [
    # metadata
    "AnimalLabel",
    "parse_animal_label",
    # parsers
    "ALEX_RESEARCHER_NAME",
    "DEFAULT_STIMULUS_NAME",
    "DiscoveryResult",
    "IngestRecord",
    "discover_alex_records",
    # orchestrator
    "IngestStats",
    "ingest_one",
    "ingest_stream",
    "prepare_db",
]
