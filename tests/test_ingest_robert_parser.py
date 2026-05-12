# ─────────────────────────────────────────────────────────────────
#  Tests for arista.ingest.parsers.robert
# ─────────────────────────────────────────────────────────────────
"""Filename + TXT body parsing tests for Robert Kossen's tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from arista.ingest.parsers.robert import (
    ROBERT_RESEARCHER_NAME,
    _parse_filename,
    discover_robert_records,
)

# ─────────────────────────────────────────────────────────────────
#  Filename parser
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name, expected",
    [
        (
            "2018-02-07_CantonS_m01_ascAmp_CC_1.txt",
            {"date": "2018-02-07", "strain": "CantonS", "sex": "m",
             "animal_number": 1, "arista_suffix": None,
             "stimulus": "ascAmp", "cell_type": "CC", "cell_number": 1},
        ),
        (
            "2018-02-08_CantonS_f02b_ascAmp_HC_2.txt",
            {"date": "2018-02-08", "strain": "CantonS", "sex": "f",
             "animal_number": 2, "arista_suffix": "b",
             "stimulus": "ascAmp", "cell_type": "HC", "cell_number": 2},
        ),
        (
            "2017-04-29_NompC3_f01_descAmpFlip_CC_2.txt",
            {"date": "2017-04-29", "strain": "NompC3", "sex": "f",
             "animal_number": 1, "arista_suffix": None,
             "stimulus": "descAmpFlip", "cell_type": "CC", "cell_number": 2},
        ),
        (
            "2019-04-08_WT_m01b_ColdAdapt_HC_1.txt",
            {"date": "2019-04-08", "strain": "WT", "sex": "m",
             "animal_number": 1, "arista_suffix": "b",
             "stimulus": "ColdAdapt", "cell_type": "HC", "cell_number": 1},
        ),
        (
            "2017-02-24_NompC-HeterozControl_m04_ascAmp_CC_1.txt",
            {"date": "2017-02-24", "strain": "NompC-HeterozControl",
             "sex": "m", "animal_number": 4, "arista_suffix": None,
             "stimulus": "ascAmp", "cell_type": "CC", "cell_number": 1},
        ),
    ],
)
def test_parse_filename_accepts(name: str, expected: dict) -> None:
    assert _parse_filename(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "singleGainComp.txt",                      # stats file
        "2018-02-07_CantonS_m01_ascAmp_CC_1.csv",  # wrong extension
        "2018-02-07_CantonS_ascAmp_CC_1.txt",      # missing gender token
        "notes.txt",
    ],
)
def test_parse_filename_rejects(name: str) -> None:
    assert _parse_filename(name) is None


# ─────────────────────────────────────────────────────────────────
#  discover_robert_records
# ─────────────────────────────────────────────────────────────────

def _write_robert_txt(
    path: Path,
    *,
    date: str = "2018-02-07",
    genotype: str = "CantonS",
    gender: str = "m01",
    stimulus: str = "ascAmp",
    celltype: str = "CC",
    n_frames: int = 20,
) -> Path:
    """Write a minimal 5-header + 3-col-body Robert TXT for tests."""
    lines = [
        f"#  date: {date}",
        f"#  genotype: {genotype}",
        f"#  gender: {gender}",
        f"#  stimulus: {stimulus}",
        f"#  celltype: {celltype}",
    ]
    for i in range(n_frames):
        lines.append(f"{i} 22.{i:02d} 0.001{i:03d}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def robert_tree(tmp_path: Path) -> Path:
    root = tmp_path / "Compiled_data_pickled"
    canton_dir = root / "CantonS"
    canton_dir.mkdir(parents=True)
    _write_robert_txt(
        canton_dir / "2018-02-07_CantonS_m01_ascAmp_CC_1.txt",
        gender="m01", celltype="CC",
    )
    _write_robert_txt(
        canton_dir / "2018-02-07_CantonS_m01_ascAmp_HC_1.txt",
        gender="m01", celltype="HC",
    )
    nompc_dir = root / "NompC3_NSybLexALexOpGCamp6"
    nompc_dir.mkdir(parents=True)
    _write_robert_txt(
        nompc_dir / "2017-04-29_NompC3_f01_descAmpFlip_CC_1.txt",
        date="2017-04-29", genotype="NompC3", gender="f01",
        stimulus="descAmpFlip", celltype="CC",
    )
    # Auxiliary stats file (should be flagged as skipped, not crash)
    stats_dir = root / "stats"
    stats_dir.mkdir()
    (stats_dir / "singleGainComp.txt").write_text("dummy aggregated output\n")
    return root


def test_discover_returns_three_records(robert_tree: Path) -> None:
    results = list(discover_robert_records(robert_tree))
    records = [r.record for r in results if r.record is not None]
    skipped = [r for r in results if r.record is None]
    assert len(records) == 3
    assert any("singleGainComp.txt" in str(r.csv_path) for r in skipped)
    assert all(r.researcher_name == ROBERT_RESEARCHER_NAME for r in records)


def test_discover_resolves_strain_via_normaliser(robert_tree: Path) -> None:
    """'NompC3' filename strain stays canonical; 'CantonS' is identity."""
    records = [r.record for r in discover_robert_records(robert_tree)
               if r.record is not None]
    strains = {r.strain_name for r in records}
    assert strains == {"CantonS", "NompC3"}


def test_discover_samples_carry_canonical_columns(robert_tree: Path) -> None:
    records = [r.record for r in discover_robert_records(robert_tree)
               if r.record is not None]
    for rec in records:
        df = rec.samples_df
        assert list(df.columns) == [
            "frame", "time_s", "sensor_t_c", "target_t_c",
            "drive_t_c", "dfbf", "dfbf_drift_corrected",
        ]
        # Robert's TXT has no target / drive / pre-correction trace
        assert df["target_t_c"].isna().all()
        assert df["drive_t_c"].isna().all()
        assert df["dfbf_drift_corrected"].isna().all()
        # And the sensor + dfbf columns ARE populated
        assert not df["sensor_t_c"].isna().any()
        assert not df["dfbf"].isna().any()


def test_discover_marks_drift_method_unknown(robert_tree: Path) -> None:
    records = [r.record for r in discover_robert_records(robert_tree)
               if r.record is not None]
    assert all(r.drift_method == "unknown" for r in records)


def test_discover_missing_root_yields_nothing(tmp_path: Path) -> None:
    assert list(discover_robert_records(tmp_path / "nope")) == []
