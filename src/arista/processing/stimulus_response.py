# ─────────────────────────────────────────────────────────────────
#  arista.processing.stimulus_response
#  « median ΔF/F per stimulus step (Kossen calcResponse) »
# ─────────────────────────────────────────────────────────────────
"""Compute the per-step median response for a thermal-step recording.

Reproduces ``_legacy/oldScripts/tempFileIO.py::calcResponse``:
for each step in the stimulus protocol's target sequence, take every
frame where the sensor temperature lies within ±``STIMULUS_RESPONSE_WINDOW_C``
of the step's target. The median ΔF/F across those frames is the
cell's response to that step.

Step dispatch uses the **time window** ``[baseline_duration_s +
k·step_duration_s, baseline_duration_s + (k+1)·step_duration_s)`` to
assign each frame to a step, then the sensor-T tolerance picks out
the in-target frames within that window. This matches Kossen's pytci
protocol design (75 s baseline + 8 × 60 s steps).

Kossen's calcResponse also keyed off ``targetTemp == step_target``
exact equality. We omit that constraint because our preprocess
pipeline linearly interpolates ``target_t_c`` to fill DAQ gaps,
which produces float values like ``22.0000001`` that fail exact
equality on a non-trivial fraction of frames. Pytci's
``alignTemperature2Frame`` uses per-frame medians without
interpolation so its exact equality is well-behaved; ours is not.
Time + sensor tolerance produces the same set of in-window frames
as Kossen's pipeline up to float-precision noise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from arista.constants import (
    STIMULUS_PROTOCOLS,
    STIMULUS_RESPONSE_WINDOW_C,
    StimulusProtocol,
)


@dataclass(frozen=True)
class StimulusResponseRow:
    """One row destined for the ``stimulus_responses`` table."""

    step_index: int
    target_temp_c: float
    delta_target_c: float
    observed_temp_median: float
    dfbf_response_median: float
    n_frames_in_window: int


def _select_dfbf_column(samples_df: pd.DataFrame) -> np.ndarray:
    """Prefer drift-corrected ΔF/F when present; fall back to raw.

    Robert's recordings carry the post-pipeline value in ``dfbf`` with
    no drift_corrected column (or all-NaN). Laurin's and the Alex
    pipeline both populate ``dfbf_drift_corrected`` separately; we
    use that when available.
    """
    if "dfbf_drift_corrected" in samples_df.columns:
        col = samples_df["dfbf_drift_corrected"]
        if not col.isna().all():
            return col.to_numpy()
    return samples_df["dfbf"].to_numpy()


def compute_stimulus_responses(
    samples_df: pd.DataFrame,
    stimulus_protocol_name: str,
    *,
    window_c: float = STIMULUS_RESPONSE_WINDOW_C,
) -> list[StimulusResponseRow]:
    """Median ΔF/F per step for a thermal-step recording.

    Args:
        samples_df: One recording's samples as returned by
            :func:`arista.preprocess.io.read_recording_csv` or by
            reading the ``samples`` table. Must carry ``time_s``,
            ``sensor_t_c``, ``target_t_c``, ``dfbf`` (and optionally
            ``dfbf_drift_corrected``) columns.
        stimulus_protocol_name: Canonical name from
            :data:`arista.constants.STIMULUS_PROTOCOLS`.
        window_c: Sensor-T tolerance half-width, defaults to
            :data:`arista.constants.STIMULUS_RESPONSE_WINDOW_C`.

    Returns:
        One :class:`StimulusResponseRow` per step that yielded at
        least one in-window frame. Empty list for stimuli without a
        ``target_sequence`` (mechanical Bending, the open-ended
        HotAdapt / ColdAdapt, Laurin's step / long pilots) — those
        protocols don't have a finite discrete step structure to
        median over.
    """
    proto: StimulusProtocol | None = STIMULUS_PROTOCOLS.get(stimulus_protocol_name)
    if proto is None or proto.target_sequence is None:
        return []

    time_s = samples_df["time_s"].to_numpy()
    sensor_t = samples_df["sensor_t_c"].to_numpy()
    dfbf = _select_dfbf_column(samples_df)

    rows: list[StimulusResponseRow] = []
    for step_index, target in enumerate(proto.target_sequence):
        # Combined mask: in-step time slice, in-tolerance sensor
        # temperature, finite ΔF/F. See module docstring for why we
        # do not also require target_t_c equality.
        step_start = proto.baseline_duration_s + step_index * proto.step_duration_s
        step_end = step_start + proto.step_duration_s
        mask = (
            (time_s >= step_start)
            & (time_s < step_end)
            & (sensor_t > target - window_c)
            & (sensor_t < target + window_c)
            & ~np.isnan(dfbf)
        )

        n = int(mask.sum())
        if n == 0:
            continue
        rows.append(
            StimulusResponseRow(
                step_index=step_index,
                target_temp_c=float(target),
                delta_target_c=float(target - proto.baseline_t_c),
                observed_temp_median=float(np.median(sensor_t[mask])),
                dfbf_response_median=float(np.median(dfbf[mask])),
                n_frames_in_window=n,
            )
        )
    return rows
