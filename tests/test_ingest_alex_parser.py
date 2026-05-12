# ─────────────────────────────────────────────────────────────────
#  Tests for arista.ingest.parsers.alex
# ─────────────────────────────────────────────────────────────────
"""Discovery + record-shaping tests for the Alex flat-layout parser."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from arista.ingest import (
    ALEX_RESEARCHER_NAME,
    discover_alex_records,
)
from arista.preprocess.io import Recording, write_recording_csv


@pytest.fixture
def alex_tree(tmp_path: Path) -> Path:
    """Build a synthetic Alex-flat tree with three preprocessed CSVs."""

    def _recording(seed: int, frames: int = 50) -> Recording:
        rng = np.random.default_rng(seed)
        return Recording(
            frame=np.arange(frames),
            time_s=np.linspace(0.0, 5.0, frames),
            sensor_t_c=22.0 + rng.normal(0, 0.05, frames),
            target_t_c=np.full(frames, 22.0),
            drive_t_c=20.0 + rng.normal(0, 0.05, frames),
            dfbf=rng.normal(0, 0.01, frames),
            dfbf_drift_corrected=rng.normal(0, 0.005, frames),
            drift_method="poly",
            recording_date="2021-12-20",
        )

    root = tmp_path / "preprocessed_output" / "alex"
    animal_dir = root / "641" / "WT_02_m"
    animal_dir.mkdir(parents=True)
    write_recording_csv(_recording(0), animal_dir / "l_CC01.csv")
    write_recording_csv(_recording(1), animal_dir / "r_HC01.csv")

    other_animal = root / "641" / "WT_01_f"
    other_animal.mkdir(parents=True)
    write_recording_csv(_recording(2), other_animal / "l_CC01.csv")

    # Note file should be hoovered up
    (animal_dir / "notes.txt.txt").write_text(
        "First 20 frames unusable. Please use frame 2-6003.\n"
    )
    return root


# ─────────────────────────────────────────────────────────────────
#  discover_alex_records
# ─────────────────────────────────────────────────────────────────

def test_discover_returns_three_records(alex_tree: Path) -> None:
    results = list(discover_alex_records(alex_tree))
    records = [r.record for r in results if r.record is not None]
    assert len(records) == 3
    by_cell = {(r.strain_name, r.animal_number, r.cell_type_code,
                r.cell_number, r.hemisphere): r for r in records}
    assert ("641", 2, "CC", 1, "l") in by_cell
    assert ("641", 2, "HC", 1, "r") in by_cell
    assert ("641", 1, "CC", 1, "l") in by_cell


def test_discover_resolves_strain_canonical(alex_tree: Path) -> None:
    results = list(discover_alex_records(alex_tree))
    for r in results:
        if r.record is not None:
            assert r.record.strain_name == "641"


def test_discover_attaches_session_notes(alex_tree: Path) -> None:
    results = [
        r.record for r in discover_alex_records(alex_tree)
        if r.record is not None and r.record.animal_number == 2
    ]
    assert all(r.notes is not None for r in results)
    assert all("frame 2-6003" in r.notes for r in results)


def test_discover_skips_non_fiji_filenames(alex_tree: Path) -> None:
    # Drop an irrelevant CSV in one of the animal directories.
    (alex_tree / "641" / "WT_02_m" / "junk.csv").write_text("foo\n1\n")
    results = list(discover_alex_records(alex_tree))
    skipped = [r for r in results if r.record is None]
    assert any("junk.csv" in str(r.csv_path) for r in skipped)
    assert any("not a Fiji ROI" in (r.reason or "") for r in skipped)


def test_discover_emits_default_stimulus_and_researcher(alex_tree: Path) -> None:
    results = [
        r.record for r in discover_alex_records(alex_tree, stimulus_name="ascAmp")
        if r.record is not None
    ]
    assert all(r.stimulus_name == "ascAmp" for r in results)
    assert all(r.researcher_name == ALEX_RESEARCHER_NAME for r in results)


def test_discover_records_per_frame_count(alex_tree: Path) -> None:
    results = [
        r.record for r in discover_alex_records(alex_tree)
        if r.record is not None
    ]
    for r in results:
        assert r.n_samples == 50
        assert pytest.approx(r.duration_s, rel=1e-6) == 5.0
        assert r.fps == 10.0


def test_discover_on_missing_root_yields_nothing(tmp_path: Path) -> None:
    results = list(discover_alex_records(tmp_path / "nope"))
    assert results == []
