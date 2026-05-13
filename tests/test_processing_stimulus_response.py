# ─────────────────────────────────────────────────────────────────
#  Tests for arista.processing.stimulus_response
# ─────────────────────────────────────────────────────────────────
"""Per-step median ΔF/F computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from arista.constants import STIMULUS_PROTOCOLS, STIMULUS_RESPONSE_WINDOW_C
from arista.processing.stimulus_response import (
    StimulusResponseRow,
    compute_stimulus_responses,
)


def _synthetic_ascamp_samples(
    *,
    fps: float = 10.0,
    response_per_step: dict[int, float] | None = None,
) -> pd.DataFrame:
    """Build a synthetic ascAmp recording: 75 s baseline + 9 × 60 s steps.

    Sensor T sits within ±0.1 °C of each step's target during the
    step's time window. ΔF/F is set per-step so tests can predict
    the expected median.
    """
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    response_per_step = response_per_step or {}

    total_s = (
        proto.baseline_duration_s
        + proto.step_duration_s * len(proto.target_sequence)
    )
    n = int(total_s * fps)
    time_s = np.arange(n) / fps
    sensor_t = np.full(n, proto.baseline_t_c)
    target_t = np.full(n, proto.baseline_t_c)
    dfbf = np.zeros(n)

    for step_index, target in enumerate(proto.target_sequence):
        step_start = proto.baseline_duration_s + step_index * proto.step_duration_s
        step_end = step_start + proto.step_duration_s
        mask = (time_s >= step_start) & (time_s < step_end)
        sensor_t[mask] = target  # exactly on target so the tolerance trivially passes
        target_t[mask] = target
        dfbf[mask] = response_per_step.get(step_index, 0.0)

    return pd.DataFrame({
        "frame": np.arange(n),
        "time_s": time_s,
        "sensor_t_c": sensor_t,
        "target_t_c": target_t,
        "drive_t_c": sensor_t - 4.0,
        "dfbf": dfbf,
        "dfbf_drift_corrected": dfbf,
    })


# ─────────────────────────────────────────────────────────────────
#  Happy path
# ─────────────────────────────────────────────────────────────────

def test_returns_one_row_per_step_on_a_clean_recording() -> None:
    samples = _synthetic_ascamp_samples()
    rows = compute_stimulus_responses(samples, "ascAmp")
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    assert len(rows) == len(proto.target_sequence)
    # Step indices come back in order
    assert [r.step_index for r in rows] == list(range(len(proto.target_sequence)))


def test_target_temp_and_delta_match_protocol() -> None:
    samples = _synthetic_ascamp_samples()
    rows = compute_stimulus_responses(samples, "ascAmp")
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    by_step = {r.step_index: r for r in rows}
    for i, target in enumerate(proto.target_sequence):
        assert by_step[i].target_temp_c == target
        assert by_step[i].delta_target_c == target - proto.baseline_t_c


def test_response_median_matches_seeded_per_step_value() -> None:
    seed = {0: 0.10, 1: 0.20, 4: -0.05, 7: 0.30}
    samples = _synthetic_ascamp_samples(response_per_step=seed)
    rows = compute_stimulus_responses(samples, "ascAmp")
    by_step = {r.step_index: r for r in rows}
    for step_index, expected in seed.items():
        assert by_step[step_index].dfbf_response_median == pytest.approx(expected)


def test_n_frames_in_window_is_sensible() -> None:
    """A 60 s step at 10 fps should yield ~600 in-window frames."""
    samples = _synthetic_ascamp_samples()
    rows = compute_stimulus_responses(samples, "ascAmp")
    for r in rows:
        # Allow some slop for the [start, end) boundary
        assert 590 <= r.n_frames_in_window <= 600


def test_observed_temp_median_equals_target_on_clean_data() -> None:
    samples = _synthetic_ascamp_samples()
    rows = compute_stimulus_responses(samples, "ascAmp")
    by_step = {r.step_index: r for r in rows}
    for i, target in enumerate(STIMULUS_PROTOCOLS["ascAmp"].target_sequence):
        assert by_step[i].observed_temp_median == pytest.approx(target)


# ─────────────────────────────────────────────────────────────────
#  Edge cases
# ─────────────────────────────────────────────────────────────────

def test_returns_empty_for_unknown_stimulus() -> None:
    samples = _synthetic_ascamp_samples()
    assert compute_stimulus_responses(samples, "no_such_stimulus") == []


def test_returns_empty_for_mechanical_stimulus() -> None:
    samples = _synthetic_ascamp_samples()
    assert compute_stimulus_responses(samples, "Bending") == []


def test_returns_empty_when_protocol_has_no_target_sequence() -> None:
    samples = _synthetic_ascamp_samples()
    assert compute_stimulus_responses(samples, "ColdAdapt") == []


def test_step_outside_recording_window_is_skipped() -> None:
    """Truncating before step 7's window cuts off steps 7 and 8."""
    samples = _synthetic_ascamp_samples()
    # ascAmp step 7 starts at 495 s; truncating at 490 leaves no frames
    # in steps 7 (495-555) or 8 (555-615).
    samples = samples.loc[samples["time_s"] < 490].copy()
    rows = compute_stimulus_responses(samples, "ascAmp")
    step_indices = {r.step_index for r in rows}
    assert 7 not in step_indices
    assert 8 not in step_indices
    assert 0 in step_indices  # earlier steps still match


def test_sensor_outside_tolerance_excludes_frames() -> None:
    """Bumping sensor 1 °C off target for one step drops that step entirely."""
    samples = _synthetic_ascamp_samples()
    proto = STIMULUS_PROTOCOLS["ascAmp"]
    step_start = proto.baseline_duration_s + 2 * proto.step_duration_s
    step_end = step_start + proto.step_duration_s
    mask = (samples["time_s"] >= step_start) & (samples["time_s"] < step_end)
    samples.loc[mask, "sensor_t_c"] += 5.0  # way out of ±0.5 °C tolerance
    rows = compute_stimulus_responses(samples, "ascAmp")
    step_indices = {r.step_index for r in rows}
    assert 2 not in step_indices


def test_falls_back_to_dfbf_when_drift_corrected_all_nan() -> None:
    """Robert's data has no dfbf_drift_corrected; we use plain dfbf."""
    samples = _synthetic_ascamp_samples(response_per_step={0: 0.42})
    samples["dfbf_drift_corrected"] = np.nan
    rows = compute_stimulus_responses(samples, "ascAmp")
    by_step = {r.step_index: r for r in rows}
    assert by_step[0].dfbf_response_median == pytest.approx(0.42)


def test_window_c_parameter_controls_tolerance() -> None:
    """Tightening the tolerance to 0.05 °C with sensor offset 0.2 °C drops the step."""
    samples = _synthetic_ascamp_samples()
    # Offset all sensor readings by +0.2 °C — still inside default 0.5
    # tolerance but outside a tightened 0.05 tolerance.
    samples["sensor_t_c"] += 0.2
    rows_loose = compute_stimulus_responses(samples, "ascAmp",
                                            window_c=STIMULUS_RESPONSE_WINDOW_C)
    rows_tight = compute_stimulus_responses(samples, "ascAmp", window_c=0.05)
    assert len(rows_loose) > len(rows_tight)
    assert len(rows_tight) == 0


def test_works_without_target_t_column_filled() -> None:
    """Robert's data leaves target_t_c all NaN; time + sensor must still work."""
    samples = _synthetic_ascamp_samples()
    samples["target_t_c"] = np.nan
    rows = compute_stimulus_responses(samples, "ascAmp")
    assert len(rows) == len(STIMULUS_PROTOCOLS["ascAmp"].target_sequence)


# ─────────────────────────────────────────────────────────────────
#  Dataclass shape
# ─────────────────────────────────────────────────────────────────

def test_stimulus_response_row_is_frozen() -> None:
    import dataclasses
    samples = _synthetic_ascamp_samples()
    rows = compute_stimulus_responses(samples, "ascAmp")
    assert isinstance(rows[0], StimulusResponseRow)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rows[0].step_index = 99  # type: ignore[misc]
