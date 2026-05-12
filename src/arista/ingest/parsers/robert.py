# ─────────────────────────────────────────────────────────────────
#  arista.ingest.parsers.robert
#  « Compiled_data_pickled TXT → IngestRecord stream »
# ─────────────────────────────────────────────────────────────────
"""Walk Robert Kossen's ``Compiled_data_pickled/<genotype>/*.txt`` tree.

Each TXT carries a five-line ``#``-prefixed provenance header followed
by a whitespace-separated 3-column body::

    #  date: 2018-02-07
    #  genotype: CantonS
    #  gender: m01
    #  stimulus: ascAmp
    #  celltype: CC
    0 21.47 -0.004010
    1 21.47 0.001740
    …

Filenames follow ``YYYY-MM-DD_<strain>_<sex><animal_num>[suffix]_<stim>_<cell>_<n>.txt``;
the per-file ``gender`` header field packs sex + animal-of-the-day +
optional ``b``-for-second-arista into one string ("m01", "f02b", …).

The dfbf column in the TXT is the **canonical post-pipeline** ΔF/F₀
(drift-corrected per the pytci massiveAligner workflow). Robert's
TXT export dropped the original choice of fit method so
``recordings.drift_correction = 'unknown'`` and the raw pre-correction
trace is not recoverable from the TXT alone. We store the TXT value
in ``samples.dfbf`` and leave ``samples.dfbf_drift_corrected`` NULL —
the column represents "raw fed in vs corrected from raw"; we lack
the raw side.

Niko's 2016 recordings were re-processed through this same pipeline
and live in ``NSybLexALexOpGCamp6/``, so they are also ingested via
this parser, attributed to the same researcher as the rest of the
compiled tree.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd

from arista.constants import normalise_stimulus, normalise_strain
from arista.ingest.parsers.alex import DiscoveryResult, IngestRecord

ROBERT_RESEARCHER_NAME = "Robert Kossen"

#: Default sample rate. Robert's pipeline assumed 10 fps throughout
#: the corpus; the TXT carries no per-file fps so we hard-code.
DEFAULT_FPS = 10.0

#: Regex matching the canonical Robert filename. Five capture groups:
#: date, strain, sex+animal+suffix, stimulus, cell type and cell number.
#: ``strain`` is greedy with ``+?`` so genotype tokens containing
#: hyphens or underscores (``NompC3``, ``NompC-HeterozControl``,
#: ``NompCGal4-Ctrl-NCBG``, …) are captured intact.
_FILENAME_PATTERN: re.Pattern[str] = re.compile(
    r"""
    ^
    (?P<date>\d{4}-\d{2}-\d{2})
    _(?P<strain>.+?)
    _(?P<sex>[mfu])(?P<animal_number>\d+)(?P<arista_suffix>[a-z])?
    _(?P<stimulus>[A-Za-z][A-Za-z0-9]*)
    _(?P<cell_type>CC|HC|WC|cc|hc|wc)
    _(?P<cell_number>\d+)
    \.txt$
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
        "date": groups["date"],
        "strain": groups["strain"],
        "sex": groups["sex"],
        "animal_number": int(groups["animal_number"]),
        "arista_suffix": groups["arista_suffix"],
        "stimulus": groups["stimulus"],
        "cell_type": groups["cell_type"].upper(),
        "cell_number": int(groups["cell_number"]),
    }


def _read_txt(path: Path) -> tuple[dict[str, str], pd.DataFrame]:
    """Parse the 5-line `#`-header + 3-col body of a Robert TXT.

    Returns:
        Pair ``(header_dict, samples_df)``. The samples_df has three
        columns: ``frame``, ``temperature_c``, ``dfbf``.

    Raises:
        ValueError: If the header is malformed or the body cannot be
            parsed as a 3-column whitespace-separated table.
    """
    header: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        # Consume the contiguous block of `#`-prefixed header lines.
        while True:
            pos = fh.tell()
            line = fh.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped.startswith("#"):
                fh.seek(pos)
                break
            body = stripped.lstrip("#").strip()
            key, _, value = body.partition(":")
            if key:
                header[key.strip()] = value.strip()
        df = pd.read_csv(
            fh,
            sep=r"\s+",
            header=None,
            names=["frame", "temperature_c", "dfbf"],
            engine="python",
        )
    if df.empty:
        raise ValueError(f"{path}: no data rows after header")
    return header, df


def _build_samples_df(body: pd.DataFrame, fps: float) -> pd.DataFrame:
    """Project Robert's 3-col TXT body into the canonical 7-col samples shape."""
    n = len(body)
    return pd.DataFrame(
        {
            "frame": body["frame"].astype(int),
            "time_s": body["frame"].astype(float) / fps,
            "sensor_t_c": body["temperature_c"].astype(float),
            "target_t_c": np.full(n, np.nan),
            "drive_t_c": np.full(n, np.nan),
            "dfbf": body["dfbf"].astype(float),
            "dfbf_drift_corrected": np.full(n, np.nan),
        }
    )


def discover_robert_records(source_root: Path) -> Iterator[DiscoveryResult]:
    """Yield one :class:`DiscoveryResult` per TXT under ``Compiled_data_pickled/``.

    The expected tree is ``<source_root>/<genotype>/*.txt`` where
    ``<genotype>`` is one of CantonS / NompC3_NSybLexALexOpGCamp6 /
    NompC-HeterozControl / NompCPbac / NompCRescue / NompCOverExpression
    / NompCGal4-Ctrl-NCBG / NompCGal4-Ctrl-WTBG / UASNompC-Ctrl-NCBG /
    NSybLexALexOpGCamp6 / ColdAdapt / HotAdapt / AristaBending.

    Files outside that pattern are yielded with ``record=None`` and a
    populated ``reason`` so the CLI surface can show them.

    Args:
        source_root: Path to ``Compiled_data_pickled/`` (or an equivalent
            tree of ``<genotype>/<txt>``).
    """
    source_root = Path(source_root).expanduser().resolve()
    if not source_root.is_dir():
        return
    for genotype_dir in sorted(source_root.iterdir()):
        if not genotype_dir.is_dir():
            continue
        for txt_path in sorted(genotype_dir.glob("*.txt")):
            meta = _parse_filename(txt_path.name)
            if meta is None:
                yield DiscoveryResult(
                    csv_path=txt_path,
                    record=None,
                    reason="filename does not match Robert pattern",
                )
                continue
            try:
                _header, body = _read_txt(txt_path)
            except Exception as exc:  # noqa: BLE001
                yield DiscoveryResult(
                    csv_path=txt_path,
                    record=None,
                    reason=f"read failed: {exc}",
                )
                continue
            samples_df = _build_samples_df(body, DEFAULT_FPS)
            n_samples = len(samples_df)
            duration_s = float(samples_df["time_s"].iloc[-1]) if n_samples else 0.0
            try:
                strain = normalise_strain(meta["strain"])
                stimulus = normalise_stimulus(meta["stimulus"])
            except ValueError as exc:
                yield DiscoveryResult(
                    csv_path=txt_path,
                    record=None,
                    reason=str(exc),
                )
                continue
            record = IngestRecord(
                researcher_name=ROBERT_RESEARCHER_NAME,
                strain_name=strain,
                recording_date=meta["date"],
                sex=meta["sex"],
                animal_number=meta["animal_number"],
                arista_suffix=meta["arista_suffix"],
                cell_type_code=meta["cell_type"],
                cell_number=meta["cell_number"],
                hemisphere=None,
                stimulus_name=stimulus,
                fps=DEFAULT_FPS,
                n_samples=n_samples,
                duration_s=duration_s,
                drift_method="unknown",
                samples_df=samples_df,
                source_csv=txt_path,
                notes=None,
            )
            yield DiscoveryResult(csv_path=txt_path, record=record, reason=None)
