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


# ─────────────────────────────────────────────────────────────────
#  Per-cell colour gradients
# ─────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _deutan(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Brettel-style projection collapsing the red-green axis."""
    r, g, b = rgb
    return (0.625 * r + 0.375 * g, 0.700 * r + 0.300 * g, b)


def _euclid(c1, c2) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2, strict=True)) ** 0.5


@pytest.mark.parametrize(
    "palette_name",
    ["CC_GRADIENT", "HC_GRADIENT", "WC_GRADIENT"],
)
def test_palette_entries_are_valid_hex(palette_name: str) -> None:
    palette = getattr(constants, palette_name)
    pattern = re.compile(r"^#[0-9A-F]{6}$")
    for c in palette:
        assert pattern.match(c), f"{c!r} in {palette_name} is not valid 6-digit hex"


def test_cc_gradient_has_four_entries() -> None:
    """Four entries support the common 3-cell case plus the rare fourth."""
    assert len(constants.CC_GRADIENT) == 4


def test_hc_gradient_has_four_entries() -> None:
    assert len(constants.HC_GRADIENT) == 4


def test_wc_gradient_has_at_least_two_entries() -> None:
    assert len(constants.WC_GRADIENT) >= 2


@pytest.mark.parametrize(
    "palette_name", ["CC_GRADIENT", "HC_GRADIENT", "WC_GRADIENT"]
)
def test_palette_pairwise_separable_under_deuteranopia(palette_name: str) -> None:
    """Every pair of palette colours must be distinguishable to a CB viewer."""
    palette = getattr(constants, palette_name)
    threshold = 0.10  # sRGB unit distance
    for i in range(len(palette)):
        for j in range(i + 1, len(palette)):
            d = _euclid(_deutan(_hex_to_rgb(palette[i])), _deutan(_hex_to_rgb(palette[j])))
            assert d > threshold, (
                f"{palette_name}[{i}]={palette[i]} and "
                f"{palette_name}[{j}]={palette[j]} collapse under "
                f"deuteranopia (d={d:.3f} ≤ {threshold})"
            )


def test_colour_for_cell_returns_palette_entry() -> None:
    assert constants.colour_for_cell("CC", 0) == constants.CC_GRADIENT[0]
    assert constants.colour_for_cell("HC", 1) == constants.HC_GRADIENT[1]
    assert constants.colour_for_cell("WC", 0) == constants.WC_GRADIENT[0]


def test_colour_for_cell_clamps_out_of_range_index() -> None:
    """Beyond the palette length, return the last entry rather than IndexError."""
    assert constants.colour_for_cell("CC", 99) == constants.CC_GRADIENT[-1]


def test_colour_for_cell_handles_lowercase() -> None:
    assert constants.colour_for_cell("cc", 0) == constants.CC_GRADIENT[0]


def test_colour_for_cell_unknown_returns_neutral_grey() -> None:
    """Unknown labels should still plot, just in neutral grey."""
    assert constants.colour_for_cell("??", 0) == "#666666"


# ─────────────────────────────────────────────────────────────────
#  Fiji filename helpers
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name,expected",
    [
        ("l_CC01.csv", {"hemisphere": "l", "cell_type": "CC", "cell_number": 1}),
        ("r_HC02.csv", {"hemisphere": "r", "cell_type": "HC", "cell_number": 2}),
        ("CC_03.csv", {"hemisphere": None, "cell_type": "CC", "cell_number": 3}),
        ("HC04.csv",   {"hemisphere": None, "cell_type": "HC", "cell_number": 4}),
        ("wc_05.csv",  {"hemisphere": None, "cell_type": "WC", "cell_number": 5}),
    ],
)
def test_parse_fiji_filename_extracts_components(name, expected) -> None:
    assert constants.parse_fiji_filename(name) == expected


def test_parse_fiji_filename_unknown_returns_none() -> None:
    assert constants.parse_fiji_filename("notes.txt") is None
    assert constants.parse_fiji_filename("data.csv") is None
    assert constants.parse_fiji_filename("temperature_data_2025.mat") is None


def test_infer_cell_type_from_filename_returns_canonical_code() -> None:
    assert constants.infer_cell_type_from_filename("l_CC01.csv") == "CC"
    assert constants.infer_cell_type_from_filename("HC02.csv") == "HC"
    assert constants.infer_cell_type_from_filename("wc_03.csv") == "WC"


def test_infer_cell_type_unknown_returns_none() -> None:
    assert constants.infer_cell_type_from_filename("notes.txt") is None


def test_is_fiji_filename_accepts_and_rejects() -> None:
    assert constants.is_fiji_filename("l_CC01.csv")
    assert constants.is_fiji_filename("HC03.csv")
    assert not constants.is_fiji_filename("notes.txt")
    assert not constants.is_fiji_filename("temperature_data_2025.mat")


# ─────────────────────────────────────────────────────────────────
#  Hemisphere markers
# ─────────────────────────────────────────────────────────────────

def test_hemisphere_markers_l_r_pooled() -> None:
    assert constants.marker_for_hemisphere("l") == "<"
    assert constants.marker_for_hemisphere("r") == ">"
    assert constants.marker_for_hemisphere(None) == "o"
    assert constants.marker_for_hemisphere("pooled") == "o"


def test_marker_for_hemisphere_handles_uppercase() -> None:
    assert constants.marker_for_hemisphere("L") == "<"
    assert constants.marker_for_hemisphere("R") == ">"


def test_marker_for_hemisphere_unknown_returns_circle() -> None:
    """Unknown labels should still plot."""
    assert constants.marker_for_hemisphere("middle") == "o"
