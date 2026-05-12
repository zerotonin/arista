# ─────────────────────────────────────────────────────────────────
#  arista.ingest.parsers.alex
#  « discover preprocessed Alex CSVs → IngestRecord stream »
# ─────────────────────────────────────────────────────────────────
"""Walk an Alex-layout tree and yield :class:`IngestRecord` instances.

The expected layout is the **flat** form produced by
``arista-preprocess`` (and committed for the in-repo subset)::

    <root>/<genotype>/<animal_label>/<fiji>.csv

where:

* ``<genotype>`` is the canonical strain (``641`` / ``605`` / ``nomp_C``)
* ``<animal_label>`` matches :func:`arista.ingest.metadata.parse_animal_label`
  (e.g. ``WT_02_m``, ``nompC_01_f``)
* ``<fiji>`` is any Fiji ROI filename accepted by
  :func:`arista.constants.parse_fiji_filename`
  (``l_CC01`` / ``r_HC02`` / ``CC_01`` / ``CC01`` / lower-case variants)

The deep HCS layout (``<genotype>/<date>/<exp>/Arista_<side>/``) is
detected and surfaced via the ``skipped`` list — the parser for it
lands in the next ingest sprint.

Stimulus protocol: Alex's 641 sessions all use ``ascAmp`` per his
records; this parser defaults to that and the CLI exposes a flag
to override per ingest run.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from arista.constants import (
    normalise_stimulus,
    normalise_strain,
    parse_fiji_filename,
)
from arista.ingest.metadata import parse_animal_label
from arista.preprocess.io import Recording, read_recording_csv

# Constant per parser-source. The orchestrator looks the researcher
# up by name; Phase 1 seeded all four canonical researchers.
ALEX_RESEARCHER_NAME = "Alexander Busch"

# Alex's per-recording default; the CLI ``--stimulus`` flag overrides.
DEFAULT_STIMULUS_NAME = "ascAmp"

# Recording rate Alex used throughout (10 fps). The schema's column
# default is also 10, but we set it explicitly so the value reflects
# the source's reality rather than a schema fallback.
DEFAULT_FPS = 10.0


@dataclass(frozen=True)
class IngestRecord:
    """One ingest-ready unit: dimension lookups + samples in one bundle.

    The orchestrator consumes a stream of these and translates each
    into one ``animals`` row (or lookup), one ``recordings`` row, and
    N ``samples`` rows.
    """

    researcher_name: str
    strain_name: str
    recording_date: str
    sex: str
    animal_number: int
    arista_suffix: str | None
    cell_type_code: str
    cell_number: int
    hemisphere: str | None
    stimulus_name: str
    fps: float
    n_samples: int
    duration_s: float
    drift_method: str
    samples_df: pd.DataFrame
    source_csv: Path
    notes: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    """Outcome of :func:`discover_alex_records` for one CSV path."""

    csv_path: Path
    record: IngestRecord | None
    reason: str | None  # None when record is populated; reason for skip otherwise


def _record_from_recording(
    *,
    recording: Recording,
    strain: str,
    animal_label_str: str,
    csv_path: Path,
    stimulus_name: str,
    notes: str | None,
) -> IngestRecord | None:
    """Combine path metadata with a loaded Recording into an IngestRecord.

    Returns ``None`` if essential metadata is missing (date / cell label /
    animal label all parsed).
    """
    if recording.recording_date is None:
        return None
    animal = parse_animal_label(animal_label_str)
    if animal is None:
        return None
    fiji = parse_fiji_filename(csv_path.name)
    if fiji is None:
        return None
    n_samples = int(recording.n_frames)
    duration_s = float(recording.time_s[-1]) if n_samples else 0.0
    return IngestRecord(
        researcher_name=ALEX_RESEARCHER_NAME,
        strain_name=normalise_strain(strain),
        recording_date=recording.recording_date,
        sex=animal.sex,
        animal_number=animal.animal_number,
        arista_suffix=animal.arista_suffix,
        cell_type_code=fiji["cell_type"],
        cell_number=int(fiji["cell_number"]),
        hemisphere=fiji["hemisphere"],
        stimulus_name=normalise_stimulus(stimulus_name),
        fps=DEFAULT_FPS,
        n_samples=n_samples,
        duration_s=duration_s,
        drift_method=recording.drift_method,
        samples_df=recording.to_dataframe(),
        source_csv=csv_path.resolve(),
        notes=notes,
    )


def discover_alex_records(
    source_root: Path,
    *,
    stimulus_name: str = DEFAULT_STIMULUS_NAME,
) -> Iterator[DiscoveryResult]:
    """Yield one :class:`DiscoveryResult` per CSV under ``source_root``.

    Walks ``<root>/<genotype>/<animal>/<fiji>.csv`` only. Paths that do
    not match the flat layout are yielded with ``record=None`` and a
    populated ``reason``; the CLI surfaces them in the startup banner.

    Args:
        source_root: Root directory (e.g. ``preprocessed_output/alex/``).
        stimulus_name: Stimulus protocol to assign to every record.
            Defaults to ``ascAmp`` per Alex's 641 sessions.

    Yields:
        :class:`DiscoveryResult` instances in deterministic alpha order.
    """
    source_root = Path(source_root).expanduser().resolve()
    if not source_root.is_dir():
        return

    for genotype_dir in sorted(source_root.iterdir()):
        if not genotype_dir.is_dir():
            continue
        strain = genotype_dir.name
        for animal_dir in sorted(genotype_dir.iterdir()):
            if not animal_dir.is_dir():
                continue
            animal_label_str = animal_dir.name
            csvs = sorted(animal_dir.glob("*.csv"))
            if not csvs:
                continue
            notes = _read_session_notes(animal_dir)
            for csv_path in csvs:
                if parse_fiji_filename(csv_path.name) is None:
                    yield DiscoveryResult(
                        csv_path=csv_path,
                        record=None,
                        reason=f"filename {csv_path.name!r} is not a Fiji ROI",
                    )
                    continue
                try:
                    recording = read_recording_csv(csv_path)
                except Exception as exc:  # noqa: BLE001
                    yield DiscoveryResult(
                        csv_path=csv_path,
                        record=None,
                        reason=f"read_recording_csv failed: {exc}",
                    )
                    continue
                record = _record_from_recording(
                    recording=recording,
                    strain=strain,
                    animal_label_str=animal_label_str,
                    csv_path=csv_path,
                    stimulus_name=stimulus_name,
                    notes=notes,
                )
                if record is None:
                    yield DiscoveryResult(
                        csv_path=csv_path,
                        record=None,
                        reason=(
                            "missing metadata (recording_date / animal / fiji)"
                        ),
                    )
                    continue
                yield DiscoveryResult(csv_path=csv_path, record=record, reason=None)


def _read_session_notes(animal_dir: Path) -> str | None:
    """Return verbatim text from ``notes.txt.txt`` / ``notes.txt`` / ``comments.txt``."""
    for name in ("notes.txt.txt", "notes.txt", "comments.txt"):
        path = animal_dir / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            return text or None
    return None
