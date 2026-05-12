# ─────────────────────────────────────────────────────────────────
#  Tests for arista.ingest.parsers.laurin
# ─────────────────────────────────────────────────────────────────
"""Filename + CSV body parsing tests for Laurin Büld's tree."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from arista.ingest.parsers.laurin import (
    LAURIN_RESEARCHER_NAME,
    _parse_filename,
    discover_laurin_records,
)

# ─────────────────────────────────────────────────────────────────
#  Filename parser
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name, expected",
    [
        (
            "nompC_het_cc_f_a1_e3_adaptation_driftCorr-linear_2020-02-13.csv",
            {"strain": "nompC_het", "cell_type": "CC", "sex": "f",
             "cell_number": 1, "animal_number": 3,
             "stimulus": "adaptation", "drift": "linear",
             "date": "2020-02-13"},
        ),
        (
            "nompC_hom_cc_m_a1_e11_adaptation_driftCorr-None_2021-03-08.csv",
            {"strain": "nompC_hom", "cell_type": "CC", "sex": "m",
             "cell_number": 1, "animal_number": 11,
             "stimulus": "adaptation", "drift": "none",
             "date": "2021-03-08"},
        ),
        (
            "wt_hc_f_a2_e5_adaptation_driftCorr-poly_2020-05-01.csv",
            {"strain": "wt", "cell_type": "HC", "sex": "f",
             "cell_number": 2, "animal_number": 5,
             "stimulus": "adaptation", "drift": "poly",
             "date": "2020-05-01"},
        ),
    ],
)
def test_parse_filename_accepts(name: str, expected: dict) -> None:
    assert _parse_filename(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "nompC_het_cc_f_e3_adaptation_driftCorr-linear_2020-02-13.csv",     # missing a<n>
        "nompC_het_cc_f_a1_e3_adaptation_2020-02-13.csv",                    # missing driftCorr
        "nompC_het_cc_f_a1_e3_adaptation_driftCorr-magic_2020-02-13.csv",    # bad drift method
        "notes.txt",
    ],
)
def test_parse_filename_rejects(name: str) -> None:
    assert _parse_filename(name) is None


# ─────────────────────────────────────────────────────────────────
#  discover_laurin_records
# ─────────────────────────────────────────────────────────────────

def _write_laurin_csv(
    path: Path,
    *,
    n_frames: int = 20,
    sensor_starts_nan: bool = True,
) -> Path:
    """Write a synthetic 7-col Laurin CSV with the expected header."""
    rows = []
    for i in range(n_frames):
        sensor = "" if (sensor_starts_nan and i == 0) else f"{22.0 + i * 0.01:.3f}"
        rows.append(
            f"{i},{float(i)},{sensor},22.0,{-0.001 * i:.6f},"
            f"{i * 0.1:.4f},{-0.002 * i:.6f}"
        )
    body = (
        ",frames,temperatureDeg,targetTempDeg,deltaFbyF,time_sec,dFbF_driftCorr\n"
        + "\n".join(rows)
        + "\n"
    )
    path.write_text(body)
    return path


@pytest.fixture
def laurin_tree(tmp_path: Path) -> Path:
    root = tmp_path / "result"
    root.mkdir()
    _write_laurin_csv(
        root / "nompC_het_cc_f_a1_e3_adaptation_driftCorr-linear_2020-02-13.csv"
    )
    _write_laurin_csv(
        root / "nompC_het_hc_f_a1_e3_adaptation_driftCorr-linear_2020-02-13.csv"
    )
    _write_laurin_csv(
        root / "wt_cc_m_a2_e5_adaptation_driftCorr-poly_2020-05-01.csv"
    )
    # Garbage file that should be flagged as skipped
    (root / "summary.csv").write_text("foo,bar\n1,2\n")
    return root


def test_discover_returns_three_records(laurin_tree: Path) -> None:
    results = list(discover_laurin_records(laurin_tree))
    records = [r.record for r in results if r.record is not None]
    skipped = [r for r in results if r.record is None]
    assert len(records) == 3
    assert any("summary.csv" in str(r.csv_path) for r in skipped)
    assert all(r.researcher_name == LAURIN_RESEARCHER_NAME for r in records)


def test_discover_records_normalise_strain(laurin_tree: Path) -> None:
    records = [r.record for r in discover_laurin_records(laurin_tree)
               if r.record is not None]
    strains = {r.strain_name for r in records}
    # 'wt' → 'CantonS' via the synonyms table; 'nompC_het' stays canonical.
    assert "CantonS" in strains
    assert "nompC_het" in strains


def test_discover_samples_carry_both_dfbf_columns(laurin_tree: Path) -> None:
    records = [r.record for r in discover_laurin_records(laurin_tree)
               if r.record is not None]
    for rec in records:
        df = rec.samples_df
        assert list(df.columns) == [
            "frame", "time_s", "sensor_t_c", "target_t_c",
            "drive_t_c", "dfbf", "dfbf_drift_corrected",
        ]
        # Laurin's CSV has both raw and corrected ΔF/F
        assert not df["dfbf"].isna().any()
        assert not df["dfbf_drift_corrected"].isna().any()
        # target_t_c is populated; drive_t_c never recorded
        assert not df["target_t_c"].isna().any()
        assert df["drive_t_c"].isna().all()


def test_discover_drift_method_from_filename(laurin_tree: Path) -> None:
    records = [r.record for r in discover_laurin_records(laurin_tree)
               if r.record is not None]
    by_filename = {r.source_csv.name: r for r in records}
    assert by_filename[
        "nompC_het_cc_f_a1_e3_adaptation_driftCorr-linear_2020-02-13.csv"
    ].drift_method == "linear"
    assert by_filename[
        "wt_cc_m_a2_e5_adaptation_driftCorr-poly_2020-05-01.csv"
    ].drift_method == "poly"


def test_discover_sensor_t_tolerates_nan(laurin_tree: Path) -> None:
    """Laurin's CSV often has the first sensor_t_c row as NaN."""
    records = [r.record for r in discover_laurin_records(laurin_tree)
               if r.record is not None]
    for rec in records:
        assert pd.isna(rec.samples_df["sensor_t_c"].iloc[0])


def test_discover_missing_root_yields_nothing(tmp_path: Path) -> None:
    assert list(discover_laurin_records(tmp_path / "nope")) == []
