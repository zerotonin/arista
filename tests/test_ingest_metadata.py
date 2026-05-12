# ─────────────────────────────────────────────────────────────────
#  Tests for arista.ingest.metadata
# ─────────────────────────────────────────────────────────────────
"""Animal-label parser coverage."""

from __future__ import annotations

import pytest

from arista.ingest.metadata import AnimalLabel, parse_animal_label


@pytest.mark.parametrize(
    "label, expected",
    [
        ("WT_01_f", AnimalLabel("WT", 1, "f", None)),
        ("WT_02_m", AnimalLabel("WT", 2, "m", None)),
        ("WT_02b_m", AnimalLabel("WT", 2, "m", "b")),
        ("nompC_01_f", AnimalLabel("nompC", 1, "f", None)),
        ("nompC_HeterozControl_07_m", AnimalLabel(
            "nompC_HeterozControl", 7, "m", None
        )),
        ("WT_99_u", AnimalLabel("WT", 99, "u", None)),
    ],
)
def test_parse_animal_label_accepts(label: str, expected: AnimalLabel) -> None:
    assert parse_animal_label(label) == expected


@pytest.mark.parametrize(
    "label",
    [
        "",
        "WT_2m",                     # missing number/sex separators
        "WT_02_X",                   # unsupported sex code
        "01_f",                      # missing strain prefix
        "WT-02-f",                   # wrong separators
        "ColdAdapt",                 # not an animal directory
        "Arista_left",               # HCS deep-layout hemisphere dir
        "temperature_data_2021_12_20-12_40.mat",  # MAT filename
    ],
)
def test_parse_animal_label_rejects(label: str) -> None:
    assert parse_animal_label(label) is None
