# ─────────────────────────────────────────────────────────────────
#  Tests for arista.constants  « palette, stimulus, strain »
# ─────────────────────────────────────────────────────────────────
"""Tests that the controlled vocabularies and palette are well-formed."""

from __future__ import annotations

import re

import pytest

from arista import constants


# ─────────────────────────────────────────────────────────────────
#  Wong palette
# ─────────────────────────────────────────────────────────────────

def test_wong_palette_has_expected_keys() -> None:
    expected = {
        "black", "orange", "sky_blue", "bluish_green",
        "yellow", "blue", "vermilion", "reddish_purple",
    }
    assert set(constants.WONG) == expected


def test_wong_palette_values_are_valid_hex() -> None:
    pattern = re.compile(r"^#[0-9A-F]{6}$")
    for name, value in constants.WONG.items():
        assert pattern.match(value), f"{name}={value!r} is not a 6-digit hex"


def test_cell_type_colours_resolve_to_wong() -> None:
    for code in ("CC", "HC", "WC"):
        assert constants.CELL_TYPE_COLOURS[code] in constants.WONG.values()


def test_strain_colours_resolve_to_wong() -> None:
    for strain, colour in constants.STRAIN_COLOURS.items():
        assert colour in constants.WONG.values(), (
            f"{strain!r} mapped to non-Wong colour {colour!r}"
        )


# ─────────────────────────────────────────────────────────────────
#  Cell types
# ─────────────────────────────────────────────────────────────────

def test_cell_types_has_three_entries() -> None:
    assert set(constants.CELL_TYPES) == {"CC", "HC", "WC"}


def test_every_cell_type_has_description() -> None:
    for code, info in constants.CELL_TYPES.items():
        assert info.code == code
        assert info.name
        assert info.description


# ─────────────────────────────────────────────────────────────────
#  Stimulus protocols
# ─────────────────────────────────────────────────────────────────

def test_stimulus_protocols_well_formed() -> None:
    """Each protocol declares a valid family and either a sequence or a reason for None."""
    valid_families = {"thermal_step", "thermal_adapt", "mechanical"}
    for name, p in constants.STIMULUS_PROTOCOLS.items():
        assert p.name == name
        assert p.family in valid_families
        assert p.description
        if p.target_sequence is not None:
            assert all(isinstance(t, float) for t in p.target_sequence)
            assert len(p.target_sequence) >= 2


def test_amp_protocols_have_nine_steps() -> None:
    """ascAmp / ascAmpFlip / descAmp / descAmpFlip / adaptation each step nine targets."""
    for name in ("ascAmp", "ascAmpFlip", "descAmp", "descAmpFlip", "adaptation"):
        p = constants.STIMULUS_PROTOCOLS[name]
        assert p.target_sequence is not None
        assert len(p.target_sequence) == 9
        assert p.target_sequence[0] == 22.0  # baseline


def test_bending_is_mechanical() -> None:
    p = constants.STIMULUS_PROTOCOLS["Bending"]
    assert p.family == "mechanical"
    assert p.target_sequence is None


def test_normalise_stimulus_canonical_is_identity() -> None:
    for name in constants.STIMULUS_PROTOCOLS:
        assert constants.normalise_stimulus(name) == name


def test_normalise_stimulus_variants() -> None:
    assert constants.normalise_stimulus("coldadap") == "ColdAdapt"
    assert constants.normalise_stimulus("hotadap") == "HotAdapt"
    assert constants.normalise_stimulus("bending") == "Bending"
    assert constants.normalise_stimulus("AristaBending") == "Bending"


def test_normalise_stimulus_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown stimulus name"):
        constants.normalise_stimulus("not_a_real_protocol")


# ─────────────────────────────────────────────────────────────────
#  Strains
# ─────────────────────────────────────────────────────────────────

def test_canonical_strains_are_unique() -> None:
    assert len(constants.CANONICAL_STRAINS) == len(set(constants.CANONICAL_STRAINS))


def test_strain_synonyms_resolve_to_canonical() -> None:
    canonical = set(constants.CANONICAL_STRAINS)
    for variant, target in constants.STRAIN_SYNONYMS.items():
        assert target in canonical, (
            f"synonym {variant!r} → {target!r} not in CANONICAL_STRAINS"
        )


def test_normalise_strain_wt_is_canton_s() -> None:
    """Robert and Laurin use WT for CantonS; ingester must collapse them."""
    assert constants.normalise_strain("WT") == "CantonS"
    assert constants.normalise_strain("wt") == "CantonS"
    assert constants.normalise_strain("Canton-S") == "CantonS"


def test_normalise_strain_canonical_is_identity() -> None:
    for name in constants.CANONICAL_STRAINS:
        assert constants.normalise_strain(name) == name


def test_normalise_strain_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown strain name"):
        constants.normalise_strain("not_a_real_genotype")


# ─────────────────────────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────────────────────────

def test_figure_dpi_publication_grade() -> None:
    """Figure DPI is the threshold expected for publication-quality output."""
    assert constants.FIGURE_DPI >= 200


def test_svg_fonttype_is_none() -> None:
    """SVG fonts must stay editable in Inkscape (CLAUDE.md § 7.2)."""
    assert constants.SVG_RC_PARAMS["svg.fonttype"] == "none"
