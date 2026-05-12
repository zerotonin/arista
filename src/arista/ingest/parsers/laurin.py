# ─────────────────────────────────────────────────────────────────
#  arista.ingest.parsers.laurin
#  « ms-thesis/result/*.csv → IngestRecord stream »
# ─────────────────────────────────────────────────────────────────
"""Walk Laurin Büld's ``ms-thesis/result/*.csv`` tree.

Each processed CSV has 7 columns: an unnamed pandas index, then
``frames, temperatureDeg, targetTempDeg, deltaFbyF, time_sec, dFbF_driftCorr``.
The header column ``temperatureDeg`` may be empty (NaN) for pre-stimulus
frames where the sensor MAT had no data; the schema's ``sensor_t_c``
column already permits NULL.

Filenames follow ``<strain>_<cell>_<sex>_a<cell_num>_e<animal_num>_<stim>_driftCorr-<method>_<date>.csv``,
where the legacy ``massiveAligner`` writes:

* ``strain`` — canonical strain name (``nompC_het`` / ``nompC_hom`` /
  ``wt`` / ``UASnompC_UASGCaMP-Gr28bd_Gal4-arista``)
* ``cell``   — cell-type code in lower case (``cc`` / ``hc``)
* ``sex``    — ``m`` / ``f``
* ``a<n>``   — cell number within type (1-based)
* ``e<n>``   — experiment / animal-of-the-day number
* ``stim``   — stimulus name (``adaptation`` for the thesis batch)
* ``driftCorr`` — ``linear`` / ``poly`` / ``exp`` / ``None``
* ``date``   — ``YYYY-MM-DD``

Laurin's filenames do not encode arista hemisphere, so every recording
gets ``hemisphere = None`` in the DB. The raw ``deltaFbyF`` column
populates ``samples.dfbf``; the drift-corrected ``dFbF_driftCorr``
column populates ``samples.dfbf_drift_corrected``. The drift method
recorded in ``recordings.drift_correction`` is read from the filename.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd

from arista.constants import normalise_stimulus, normalise_strain
from arista.ingest.parsers.alex import DiscoveryResult, IngestRecord

LAURIN_RESEARCHER_NAME = "Laurin Büld"

#: Laurin's recordings were acquired at the same 10 fps as Robert's.
DEFAULT_FPS = 10.0

#: Map filename drift tokens onto the canonical DB CHECK values.
_DRIFT_FROM_FILENAME: dict[str, str] = {
    "linear": "linear",
    "poly": "poly",
    "exp": "exp",
    "None": "none",
    "none": "none",
}


#: Regex for Laurin's result filenames. Strain is greedy ``+?`` so it
#: accepts compound names containing underscores or hyphens.
_FILENAME_PATTERN: re.Pattern[str] = re.compile(
    r"""
    ^
    (?P<strain>.+?)
    _(?P<cell_type>cc|hc|wc|CC|HC|WC)
    _(?P<sex>[mfu])
    _a(?P<cell_number>\d+)
    _e(?P<animal_number>\d+)
    _(?P<stimulus>[A-Za-z][A-Za-z0-9_]*?)
    _driftCorr-(?P<drift>linear|poly|exp|None|none)
    _(?P<date>\d{4}-\d{2}-\d{2})
    \.csv$
    """,
    re.VERBOSE,
)


def _parse_filename(name: str) -> dict | None:
    """Return parsed filename components, or ``None`` if the name does not match."""
    match = _FILENAME_PATTERN.match(name)
    if match is None:
        return None
    groups = match.groupdict()
    return {
        "strain": groups["strain"],
        "cell_type": groups["cell_type"].upper(),
        "sex": groups["sex"],
        "cell_number": int(groups["cell_number"]),
        "animal_number": int(groups["animal_number"]),
        "stimulus": groups["stimulus"],
        "drift": _DRIFT_FROM_FILENAME[groups["drift"]],
        "date": groups["date"],
    }


def _read_csv(path: Path) -> pd.DataFrame:
    """Read Laurin's 7-column processed CSV into a DataFrame."""
    df = pd.read_csv(path)
    expected = {"frames", "temperatureDeg", "targetTempDeg",
                "deltaFbyF", "time_sec", "dFbF_driftCorr"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"{path}: CSV missing columns {sorted(missing)!r}")
    return df


def _build_samples_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Project Laurin's CSV into the canonical 7-col samples shape."""
    n = len(raw)
    return pd.DataFrame(
        {
            "frame": raw["frames"].astype(float).astype(int),
            "time_s": raw["time_sec"].astype(float),
            "sensor_t_c": raw["temperatureDeg"].astype(float),
            "target_t_c": raw["targetTempDeg"].astype(float),
            "drive_t_c": np.full(n, np.nan),
            "dfbf": raw["deltaFbyF"].astype(float),
            "dfbf_drift_corrected": raw["dFbF_driftCorr"].astype(float),
        }
    )


def discover_laurin_records(source_root: Path) -> Iterator[DiscoveryResult]:
    """Yield one :class:`DiscoveryResult` per CSV under ``ms-thesis/result/``.

    The expected tree is a flat ``<source_root>/*.csv`` with no
    subdirectories — Laurin's massiveAligner writes all outputs into
    one ``result/`` folder regardless of strain or stimulus.

    Args:
        source_root: Path to ``ms-thesis/result/``.
    """
    source_root = Path(source_root).expanduser().resolve()
    if not source_root.is_dir():
        return
    for csv_path in sorted(source_root.glob("*.csv")):
        meta = _parse_filename(csv_path.name)
        if meta is None:
            yield DiscoveryResult(
                csv_path=csv_path,
                record=None,
                reason="filename does not match Laurin pattern",
            )
            continue
        try:
            raw = _read_csv(csv_path)
        except Exception as exc:  # noqa: BLE001
            yield DiscoveryResult(
                csv_path=csv_path,
                record=None,
                reason=f"read failed: {exc}",
            )
            continue
        samples_df = _build_samples_df(raw)
        n_samples = len(samples_df)
        duration_s = float(samples_df["time_s"].iloc[-1]) if n_samples else 0.0
        try:
            strain = normalise_strain(meta["strain"])
            stimulus = normalise_stimulus(meta["stimulus"])
        except ValueError as exc:
            yield DiscoveryResult(
                csv_path=csv_path,
                record=None,
                reason=str(exc),
            )
            continue
        record = IngestRecord(
            researcher_name=LAURIN_RESEARCHER_NAME,
            strain_name=strain,
            recording_date=meta["date"],
            sex=meta["sex"],
            animal_number=meta["animal_number"],
            arista_suffix=None,
            cell_type_code=meta["cell_type"],
            cell_number=meta["cell_number"],
            hemisphere=None,
            stimulus_name=stimulus,
            fps=DEFAULT_FPS,
            n_samples=n_samples,
            duration_s=duration_s,
            drift_method=meta["drift"],
            samples_df=samples_df,
            source_csv=csv_path,
            notes=None,
        )
        yield DiscoveryResult(csv_path=csv_path, record=record, reason=None)
