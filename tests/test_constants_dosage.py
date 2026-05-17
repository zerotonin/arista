# ─────────────────────────────────────────────────────────────────
#  Tests for NompC dosage lookup helpers in arista.constants
# ─────────────────────────────────────────────────────────────────
"""NOMPC_DOSAGE map + nompc_dosage() helper.

The dosage map intentionally contains both canonical Kossen-era names
and cross-student aliases (``nompC_hom``, ``nompC_het``,
``UASnompC_…``) — these are stored separately from STRAIN_SYNONYMS
because the ingest layer treats Laurin's aliases as canonical of
their own and we must not rewrite that on read.
"""

from __future__ import annotations

import numpy as np
import pytest

from arista.constants import NOMPC_DOSAGE, nompc_dosage

# ─────────────────────────────────────────────────────────────────
#  Canonical strain dosage values (Bart 2026-05-14 confirmation)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("strain,expected", [
    ("NompC3",                          0.0),
    ("NompC-HeterozControl",            1.0),
    ("NompCPbac",                       1.75),
    ("CantonS",                         2.0),
    ("white",                           2.0),
    ("641",                             2.0),
    ("NompCRescue",                     2.0),
    ("NompCOverExpression",             3.0),
])
def test_canonical_strain_returns_expected_dosage(
    strain: str, expected: float,
) -> None:
    assert nompc_dosage(strain) == expected


@pytest.mark.parametrize("alias,expected", [
    ("nompC_hom",                                       0.0),
    ("nompC_het",                                       1.0),
    ("UASnompC_UASGCaMP-Gr28bd_Gal4-arista",            2.0),
])
def test_cross_student_alias_returns_same_dosage_as_canonical(
    alias: str, expected: float,
) -> None:
    """Robert/Laurin spellings must hit the same dosage as Kossen names."""
    assert nompc_dosage(alias) == expected


def test_unknown_strain_returns_none() -> None:
    assert nompc_dosage("MysteryStrain") is None


def test_none_input_returns_none() -> None:
    assert nompc_dosage(None) is None


def test_nan_input_returns_none() -> None:
    """Pandas SQL NULLs surface as float-NaN in strain_name columns."""
    assert nompc_dosage(float("nan")) is None
    assert nompc_dosage(np.nan) is None


# ─────────────────────────────────────────────────────────────────
#  Dosage-map shape
# ─────────────────────────────────────────────────────────────────


def test_dosage_ordering_makes_biological_sense() -> None:
    assert NOMPC_DOSAGE["NompC3"] < NOMPC_DOSAGE["NompC-HeterozControl"]
    assert NOMPC_DOSAGE["NompC-HeterozControl"] < NOMPC_DOSAGE["NompCPbac"]
    assert NOMPC_DOSAGE["NompCPbac"] < NOMPC_DOSAGE["CantonS"]
    assert NOMPC_DOSAGE["CantonS"] == NOMPC_DOSAGE["NompCRescue"]
    assert NOMPC_DOSAGE["NompCRescue"] < NOMPC_DOSAGE["NompCOverExpression"]


def test_cross_student_aliases_match_canonical_values() -> None:
    """The aliased entries must agree numerically with their canonicals."""
    assert NOMPC_DOSAGE["nompC_hom"] == NOMPC_DOSAGE["NompC3"]
    assert NOMPC_DOSAGE["nompC_het"] == NOMPC_DOSAGE["NompC-HeterozControl"]
    assert (
        NOMPC_DOSAGE["UASnompC_UASGCaMP-Gr28bd_Gal4-arista"]
        == NOMPC_DOSAGE["NompCRescue"]
    )
