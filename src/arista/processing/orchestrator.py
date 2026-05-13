# ─────────────────────────────────────────────────────────────────
#  arista.processing.orchestrator
#  « walk recordings, compute aggregates, upsert results »
# ─────────────────────────────────────────────────────────────────
"""Batch driver that fills ``stimulus_responses`` and ``adaptation_fits``.

Dispatches by stimulus protocol family:

* ``thermal_step``  with a target_sequence → :func:`compute_stimulus_responses`
* ``thermal_adapt`` (HotAdapt / ColdAdapt)  → :func:`fit_adaptation`
* ``mechanical``                            → no aggregates (Bending)
* ``thermal_adapt`` without target_sequence → adaptation only
* ``thermal_step``  without target_sequence → none (Laurin pilots
                                              step / step_neg / long /
                                              long_neg lack a defined
                                              sequence yet)

Idempotent: re-running over a DB that already has aggregates skips
those recordings unless ``reprocess=True`` is passed (in which case
the existing rows for the recording are deleted and recomputed).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass

import pandas as pd

from arista.processing.adaptation import AdaptationFit, fit_adaptation
from arista.processing.stimulus_response import (
    StimulusResponseRow,
    compute_stimulus_responses,
)

log = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Tally for one ``process_all`` run."""

    inserted_responses: int = 0
    inserted_adaptations: int = 0
    skipped_already_done: int = 0
    failed_adaptations: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "inserted_responses": self.inserted_responses,
            "inserted_adaptations": self.inserted_adaptations,
            "skipped_already_done": self.skipped_already_done,
            "failed_adaptations": self.failed_adaptations,
        }


# ─────────────────────────────────────────────────────────────────
#  Per-recording handlers
# ─────────────────────────────────────────────────────────────────


def _samples_df_for_recording(
    conn: sqlite3.Connection, recording_id: int
) -> pd.DataFrame:
    """Pull every sample for a recording into a DataFrame in frame order."""
    return pd.read_sql_query(
        """
        SELECT frame, time_s, sensor_t_c, target_t_c, drive_t_c,
               dfbf, dfbf_drift_corrected
        FROM samples
        WHERE recording_id = ?
        ORDER BY frame
        """,
        conn,
        params=(recording_id,),
    )


def _has_responses(cur: sqlite3.Cursor, recording_id: int) -> bool:
    row = cur.execute(
        "SELECT 1 FROM stimulus_responses WHERE recording_id = ? LIMIT 1",
        (recording_id,),
    ).fetchone()
    return row is not None


def _has_adaptation(cur: sqlite3.Cursor, recording_id: int) -> bool:
    row = cur.execute(
        "SELECT 1 FROM adaptation_fits WHERE recording_id = ?",
        (recording_id,),
    ).fetchone()
    return row is not None


def _insert_responses(
    cur: sqlite3.Cursor,
    recording_id: int,
    rows: list[StimulusResponseRow],
) -> int:
    if not rows:
        return 0
    cur.executemany(
        """
        INSERT OR REPLACE INTO stimulus_responses
            (recording_id, step_index, target_temp_c, delta_target_c,
             observed_temp_median, dfbf_response_median, n_frames_in_window)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (recording_id, r.step_index, r.target_temp_c, r.delta_target_c,
             r.observed_temp_median, r.dfbf_response_median, r.n_frames_in_window)
            for r in rows
        ],
    )
    return len(rows)


def _insert_adaptation(
    cur: sqlite3.Cursor,
    recording_id: int,
    fit: AdaptationFit,
) -> None:
    cur.execute(
        """
        INSERT OR REPLACE INTO adaptation_fits
            (recording_id, tau_s, amplitude, asymptote, r_squared,
             fit_window_start_s, fit_window_end_s, n_points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (recording_id, fit.tau_s, fit.amplitude, fit.asymptote,
         fit.r_squared, fit.fit_window_start_s, fit.fit_window_end_s,
         fit.n_points),
    )


# ─────────────────────────────────────────────────────────────────
#  Public driver
# ─────────────────────────────────────────────────────────────────


def process_all(
    conn: sqlite3.Connection,
    *,
    progress: bool | None = None,
    reprocess: bool = False,
) -> ProcessingStats:
    """Compute aggregates for every recording missing them.

    Args:
        conn: Open SQLite connection to a populated ``arista.db``.
        progress: tqdm visibility (None = auto-detect TTY, True =
            force on, False = force off).
        reprocess: If ``True`` drop existing aggregates before
            recomputing. Useful after fixing the response formula.

    Returns:
        :class:`ProcessingStats` with counts of inserted /
        already-done / failed-adaptation recordings.
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT r.recording_id, sp.name, sp.family, sp.target_sequence_json
        FROM recordings r
        JOIN stimulus_protocols sp ON sp.stimulus_id = r.stimulus_id
        ORDER BY r.recording_id
        """
    ).fetchall()

    if reprocess:
        cur.execute("DELETE FROM stimulus_responses")
        cur.execute("DELETE FROM adaptation_fits")

    stats = ProcessingStats()

    from tqdm.auto import tqdm
    disable = None if progress is None else not progress
    bar = tqdm(rows, desc="Processing recordings",
               unit="rec", disable=disable)

    for recording_id, proto_name, family, target_seq_json in bar:
        if family == "thermal_step":
            target_sequence = (
                json.loads(target_seq_json) if target_seq_json else None
            )
            if target_sequence is None:
                continue  # Laurin pilot stimuli with no defined sequence
            if not reprocess and _has_responses(cur, recording_id):
                stats.skipped_already_done += 1
                continue
            samples = _samples_df_for_recording(conn, recording_id)
            try:
                response_rows = compute_stimulus_responses(
                    samples, proto_name
                )
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "stimulus response computation failed for %d: %s",
                    recording_id, exc,
                )
                continue
            stats.inserted_responses += _insert_responses(
                cur, recording_id, response_rows
            )

        elif family == "thermal_adapt":
            if not reprocess and _has_adaptation(cur, recording_id):
                stats.skipped_already_done += 1
                continue
            samples = _samples_df_for_recording(conn, recording_id)
            try:
                fit = fit_adaptation(samples)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "adaptation fit failed for %d: %s", recording_id, exc,
                )
                stats.failed_adaptations += 1
                continue
            if fit is None:
                stats.failed_adaptations += 1
                continue
            _insert_adaptation(cur, recording_id, fit)
            stats.inserted_adaptations += 1

        # mechanical → no aggregates

    conn.commit()
    return stats
