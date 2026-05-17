# ╔══════════════════════════════════════════════════════════════════╗
# ║  arista — constants                                              ║
# ║  « single source of truth for colours, paths, figure rules »     ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Central configuration for the arista package.                   ║
# ║                                                                  ║
# ║  Holds the Wong (2011) colourblind-safe palette with semantic    ║
# ║  mappings to HC / CC / WC cell types, the canonical stimulus     ║
# ║  protocol dictionary, the canonical strain list with synonym     ║
# ║  normalisation, and the save_figure helper that produces         ║
# ║  SVG + PNG + CSV triples for every plot.                         ║
# ║                                                                  ║
# ║  Import this module instead of hardcoding any of the above.      ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Constants, palettes, stimulus + strain catalogues, and helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.figure import Figure


# ─────────────────────────────────────────────────────────────────
#  Shipped fixture paths
# ─────────────────────────────────────────────────────────────────

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PACKAGE_ROOT.parents[1]
DATA_DIR: Path = REPO_ROOT / "data"
FIJI_FIXTURE_DIR: Path = DATA_DIR / "fiji"
SENSOR_FIXTURE_DIR: Path = DATA_DIR / "sensor"
PREPROCESSED_FIXTURE_DIR: Path = DATA_DIR / "preprocessed"
RAW_ARCHIVE_DIR: Path = DATA_DIR / "raw"


# ┌────────────────────────────────────────────────────────────┐
# │ Wong (2011) palette  « colourblind-safe base colours »     │
# └────────────────────────────────────────────────────────────┘

WONG: dict[str, str] = {
    "black":          "#000000",
    "orange":         "#E69F00",
    "sky_blue":       "#56B4E9",
    "bluish_green":   "#009E73",
    "yellow":         "#F0E442",
    "blue":           "#0072B2",
    "vermilion":      "#D55E00",
    "reddish_purple": "#CC79A7",
}

# Semantic mappings used across every figure module.
CELL_TYPE_COLOURS: dict[str, str] = {
    "CC": WONG["sky_blue"],        # cold cells get a cool hue
    "HC": WONG["vermilion"],       # hot cells get a warm hue
    "WC": WONG["reddish_purple"],  # weird cells get a distinct hue
}

# ┌────────────────────────────────────────────────────────────┐
# │ Per-cell sequential gradients  « 3-4 cells per session »   │
# └────────────────────────────────────────────────────────────┘
# Within one recording session three (occasionally four) cells of the
# same type are typically imaged. The session-overview plotter assigns
# colours by cell number within type. Palettes are Wong-derived where
# possible, with darker extensions added to support four-cell sessions.
#
# Colour-blind safety verified via Brettel-projected pairwise distances
# in sRGB unit space (see tests/test_constants.py). All adjacent
# colours are separable under deuteranopia and protanopia, and luminance
# is monotonic within HC (intentionally) so even with severe colour-
# vision deficiency the cell ordering can be read from greyscale.

CC_GRADIENT: tuple[str, ...] = (
    "#003D6B",  # deep navy        — CC01
    "#0072B2",  # Wong blue        — CC02
    "#56B4E9",  # Wong sky_blue    — CC03
    "#009E73",  # Wong teal        — CC04 (rare)
)

HC_GRADIENT: tuple[str, ...] = (
    "#E69F00",  # Wong orange      — HC01
    "#D55E00",  # Wong vermilion   — HC02
    "#A0411D",  # extended rust    — HC03
    "#5C1606",  # extended dark    — HC04 (rare)
)

WC_GRADIENT: tuple[str, ...] = (
    "#CC79A7",  # Wong reddish_purple — WC01
    "#7D3C98",  # extended darker     — WC02 (rare)
)

CELL_TYPE_GRADIENTS: dict[str, tuple[str, ...]] = {
    "CC": CC_GRADIENT,
    "HC": HC_GRADIENT,
    "WC": WC_GRADIENT,
}


def colour_for_cell(cell_type: str, index: int = 0) -> str:
    """Return the palette colour for a numbered cell of the given type.

    Args:
        cell_type: ``"CC"`` / ``"HC"`` / ``"WC"`` (case-insensitive).
        index: 0-based position within the type. Clamps to the last
            palette entry once the gradient is exhausted, so a fifth
            CC cell in some hypothetical session still gets a sensible
            colour rather than raising.

    Returns:
        A hex colour string. Falls back to a neutral grey if the
        ``cell_type`` is unrecognised, so unknown labels are visible
        but don't crash plotting.
    """
    palette = CELL_TYPE_GRADIENTS.get(cell_type.upper())
    if palette is None:
        return "#666666"
    return palette[min(index, len(palette) - 1)]


# ┌────────────────────────────────────────────────────────────┐
# │ Fiji filename pattern  « used by ingest + viz + scripts »  │
# └────────────────────────────────────────────────────────────┘

#: Regex matching every Fiji ROI filename convention observed in the
#: corpus: ``l_CC01.csv`` / ``r_HC02.csv`` (flat layout); ``CC_01.csv``
#: / ``HC_02.csv`` (HCS exp01); ``CC01.csv`` / ``HC03.csv`` (HCS exp02);
#: plus lower-case variants. Three named groups: ``hemisphere`` (may
#: be ``None``), ``cell_type``, ``cell_number``.
FIJI_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"""
    ^
    (?:(?P<hemisphere>[lr])_)?              # optional hemisphere prefix
    (?P<cell_type>CC|HC|WC|cc|hc|wc)
    _?(?P<cell_number>\d+)
    \.csv$
    """,
    re.VERBOSE,
)


def is_fiji_filename(name: str) -> bool:
    """Return True if ``name`` matches any accepted Fiji ROI filename pattern."""
    return bool(FIJI_NAME_PATTERN.match(name))


def parse_fiji_filename(name: str) -> dict[str, str | None] | None:
    """Pull (hemisphere, cell_type, cell_number) out of a Fiji ROI filename.

    Returns ``None`` if the name does not match.
    """
    match = FIJI_NAME_PATTERN.match(name)
    if not match:
        return None
    groups = match.groupdict()
    return {
        "hemisphere": groups["hemisphere"],
        "cell_type": groups["cell_type"].upper(),
        "cell_number": int(groups["cell_number"]),
    }


def infer_cell_type_from_filename(name: str) -> CellTypeCode | None:
    """Convenience: return just the canonical CC/HC/WC code, or ``None``."""
    parsed = parse_fiji_filename(name)
    if parsed is None:
        return None
    return parsed["cell_type"]


# ┌────────────────────────────────────────────────────────────┐
# │ Hemisphere markers  « left / right / pooled aristas »      │
# └────────────────────────────────────────────────────────────┘
# Matplotlib marker glyphs for distinguishing arista hemisphere in
# non-time-series plots (scatter, raincloud, gain comparisons).
# Time-series plots (session overview) don't use markers because lines
# with thousands of points would become unreadable; hemisphere is
# encoded in the cell label there.

HEMISPHERE_MARKERS: dict[str | None, str] = {
    "l": "<",        # left arista — pointer left
    "r": ">",        # right arista — pointer right
    None: "o",       # pooled or unspecified — neutral circle
    "pooled": "o",   # explicit pooled label
}


def marker_for_hemisphere(hemisphere: str | None | float) -> str:
    """Return the matplotlib marker glyph for the given arista side.

    Accepts ``None``, pandas-NaN, or arbitrary non-string values and
    falls back to ``"o"`` in those cases so a real-world Series loaded
    from SQL (where NULLs surface as NaN floats) is safe to iterate
    without preprocessing.
    """
    if hemisphere is None:
        return HEMISPHERE_MARKERS[None]
    if isinstance(hemisphere, float):
        # NaN compares unequal to itself; that's how we detect it
        # without importing numpy at module level.
        if hemisphere != hemisphere:
            return HEMISPHERE_MARKERS[None]
        return "o"
    if not isinstance(hemisphere, str):
        return "o"
    return HEMISPHERE_MARKERS.get(hemisphere.lower(), "o")


# ┌────────────────────────────────────────────────────────────┐
# │ Genotype colours  « stable per-strain assignment »         │
# └────────────────────────────────────────────────────────────┘

# Distinct colour per genotype family (mutants vs controls vs rescue).
# Strain → Wong colour assignment is intentionally stable across all
# figures; viz modules look up here rather than picking ad hoc.
STRAIN_COLOURS: dict[str, str] = {
    "CantonS":             WONG["black"],
    "white":               WONG["yellow"],
    "NompC3":              WONG["vermilion"],
    "NompC-HeterozControl": WONG["orange"],
    "NompCPbac":           WONG["bluish_green"],
    "NompCRescue":         WONG["blue"],
    "NompCOverExpression": WONG["reddish_purple"],
}


# ┌────────────────────────────────────────────────────────────┐
# │ Cell-type catalogue  « CC / HC / WC semantics »            │
# └────────────────────────────────────────────────────────────┘

CellTypeCode = Literal["CC", "HC", "WC"]


@dataclass(frozen=True)
class CellTypeInfo:
    """One row in the ``cell_types`` dimension table."""

    code: CellTypeCode
    name: str
    description: str


CELL_TYPES: dict[CellTypeCode, CellTypeInfo] = {
    "CC": CellTypeInfo(
        code="CC",
        name="Cold cell",
        description="Responds to falling temperature.",
    ),
    "HC": CellTypeInfo(
        code="HC",
        name="Hot cell",
        description="Responds to rising temperature.",
    ),
    "WC": CellTypeInfo(
        code="WC",
        name="Weird cell",
        description=(
            "Apparent dual response. Working hypothesis: an HC and a CC "
            "share the same optical plane, so the ROI integrates both — "
            "artifact of plane selection, not a true cell type."
        ),
    ),
}


# ┌────────────────────────────────────────────────────────────┐
# │ Stimulus protocols  « target sequences from pytci »        │
# └────────────────────────────────────────────────────────────┘

StimulusFamily = Literal["thermal_step", "thermal_adapt", "mechanical"]


@dataclass(frozen=True)
class StimulusProtocol:
    """One row in the ``stimulus_protocols`` dimension table.

    Target sequences for the four ``*Amp*`` and ``adaptation`` protocols
    are lifted verbatim from ``_legacy/pytci/tempFileIO.py`` so the new
    pipeline and the legacy one agree on what target each step held.
    Mechanical and long-duration adaptation protocols carry no sequence.
    """

    name: str
    family: StimulusFamily
    description: str
    target_sequence: tuple[float, ...] | None
    baseline_t_c: float = 22.0
    step_duration_s: float = 60.0
    baseline_duration_s: float = 75.0


STIMULUS_PROTOCOLS: dict[str, StimulusProtocol] = {
    "ascAmp": StimulusProtocol(
        name="ascAmp",
        family="thermal_step",
        description="Ascending amplitude steps around 22 °C",
        target_sequence=(22.0, 22.5, 21.5, 23.0, 21.0, 24.0, 20.0, 26.0, 18.0),
    ),
    "ascAmpFlip": StimulusProtocol(
        name="ascAmpFlip",
        family="thermal_step",
        description="Ascending amplitude, sign-flipped order",
        target_sequence=(22.0, 21.5, 22.5, 21.0, 23.0, 20.0, 24.0, 18.0, 26.0),
    ),
    "descAmp": StimulusProtocol(
        name="descAmp",
        family="thermal_step",
        description="Descending amplitude steps around 22 °C",
        target_sequence=(22.0, 18.0, 26.0, 20.0, 24.0, 21.0, 23.0, 21.5, 22.5),
    ),
    "descAmpFlip": StimulusProtocol(
        name="descAmpFlip",
        family="thermal_step",
        description="Descending amplitude, sign-flipped order",
        target_sequence=(22.0, 26.0, 18.0, 24.0, 20.0, 23.0, 21.0, 22.5, 21.5),
    ),
    "adaptation": StimulusProtocol(
        name="adaptation",
        family="thermal_adapt",
        description="Repeated 22↔24 °C with one 20 °C trough",
        target_sequence=(22.0, 24.0, 22.0, 24.0, 20.0, 24.0, 22.0, 24.0, 22.0),
    ),
    "ColdAdapt": StimulusProtocol(
        name="ColdAdapt",
        family="thermal_adapt",
        description="Long-duration cold acclimation step (target near 18 °C)",
        target_sequence=None,
    ),
    "HotAdapt": StimulusProtocol(
        name="HotAdapt",
        family="thermal_adapt",
        description="Long-duration warm acclimation step (target near 26 °C)",
        target_sequence=None,
    ),
    "Bending": StimulusProtocol(
        name="Bending",
        family="mechanical",
        description="Piezo-driven arista bending; no thermal trace",
        target_sequence=None,
        baseline_t_c=22.0,
        step_duration_s=60.0,
        baseline_duration_s=0.0,
    ),
    "step": StimulusProtocol(
        name="step",
        family="thermal_step",
        description="Laurin pilot: short positive Peltier step",
        target_sequence=None,
    ),
    "step_neg": StimulusProtocol(
        name="step_neg",
        family="thermal_step",
        description="Laurin pilot: short negative Peltier step",
        target_sequence=None,
    ),
    "long": StimulusProtocol(
        name="long",
        family="thermal_step",
        description="Laurin pilot: long positive Peltier transient",
        target_sequence=None,
    ),
    "long_neg": StimulusProtocol(
        name="long_neg",
        family="thermal_step",
        description="Laurin pilot: long negative Peltier transient",
        target_sequence=None,
    ),
}

#: Map every observed spelling to its canonical entry in
#: :data:`STIMULUS_PROTOCOLS`. Filenames in Robert's tree mix case
#: (``coldadap`` vs ``ColdAdapt``); the ingester normalises via this
#: table and fails loudly if a string is not present.
STIMULUS_SYNONYMS: dict[str, str] = {
    # canonical → canonical (identity, for safety)
    "ascAmp":          "ascAmp",
    "ascAmpFlip":      "ascAmpFlip",
    "descAmp":         "descAmp",
    "descAmpFlip":     "descAmpFlip",
    "adaptation":      "adaptation",
    "ColdAdapt":       "ColdAdapt",
    "HotAdapt":        "HotAdapt",
    "Bending":         "Bending",
    "step":            "step",
    "step_neg":        "step_neg",
    "long":            "long",
    "long_neg":        "long_neg",
    # observed variants
    "coldadap":        "ColdAdapt",
    "cold_adap":       "ColdAdapt",
    "coldadaptation":  "ColdAdapt",
    "hotadap":         "HotAdapt",
    "hot_adap":        "HotAdapt",
    "hotadaptation":   "HotAdapt",
    "bending":         "Bending",
    "AristaBending":   "Bending",
}


def normalise_stimulus(name: str) -> str:
    """Resolve any observed spelling of a stimulus to its canonical name.

    Args:
        name: The string as it appears in a filename or file header.

    Returns:
        The canonical key in :data:`STIMULUS_PROTOCOLS`.

    Raises:
        ValueError: If ``name`` is unknown. Add it to
            :data:`STIMULUS_SYNONYMS` rather than silently mapping it.
    """
    try:
        return STIMULUS_SYNONYMS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown stimulus name {name!r}; add it to "
            f"arista.constants.STIMULUS_SYNONYMS before re-running."
        ) from exc


# ┌────────────────────────────────────────────────────────────┐
# │ Strain catalogue  « canonical names + synonyms »           │
# └────────────────────────────────────────────────────────────┘

CANONICAL_STRAINS: tuple[str, ...] = (
    # Wild-type and control stocks
    "CantonS",
    "white",
    # Kossen-era NompC lines
    "NompC3",
    "NompC-HeterozControl",
    "NompCPbac",
    "NompCRescue",
    "NompCOverExpression",
    "NompCGal4-Ctrl-NCBG",
    "NompCGal4-Ctrl-WTBG",
    "UASNompC-Ctrl-NCBG",
    "UASNompC-Ctrl-WTBG",
    "NSybLexALexOpGCamp6",
    "NompC3_NSybLexALexOpGCamp6",
    # Laurin's MSc driver
    "UASnompC_UASGCaMP-Gr28bd_Gal4-arista",
    "nompC_hom",
    "nompC_het",
    # Alex's genotypes (Bloomington stock numbers, identities to be
    # confirmed by Bart and may be renamed in a future release)
    "605",
    "641",
    "nomp_C",
)

STRAIN_SYNONYMS: dict[str, str] = {
    # canonical → canonical (identity)
    **{s: s for s in CANONICAL_STRAINS},
    # observed variants
    "WT":              "CantonS",
    "wt":              "CantonS",
    "Canton-S":        "CantonS",
    "canton-s":        "CantonS",
    "w1118":           "white",
    "w¹¹¹⁸":           "white",
    "NompCOverEx":     "NompCOverExpression",
    "nompC-overex":    "NompCOverExpression",
    "NompC_3":         "NompC3",
    "NompC3_NSybLexA-LexOpGCamp6": "NompC3_NSybLexALexOpGCamp6",
    "nompC":           "nomp_C",
    "NompC":           "nomp_C",
}


def normalise_strain(name: str) -> str:
    """Resolve any observed spelling of a strain to its canonical name.

    Args:
        name: The string as it appears in a filename or directory.

    Returns:
        The canonical entry in :data:`CANONICAL_STRAINS`.

    Raises:
        ValueError: If ``name`` is unknown.
    """
    try:
        return STRAIN_SYNONYMS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown strain name {name!r}; add it to "
            f"arista.constants.STRAIN_SYNONYMS before re-running."
        ) from exc


# ┌────────────────────────────────────────────────────────────┐
# │ NompC functional dosage  « Phase 7d headline figure x-axis »│
# └────────────────────────────────────────────────────────────┘

# Functional NompC level per strain. The axis is the *functional*
# dosage, not a literal copy count — NompCPbac is a weak hypomorph
# (homozygous → still some NompC activity) so its functional level
# sits between heterozygote and wild-type.
#
# Cross-student aliases (``nompC_hom``, ``nompC_het``,
# ``UASnompC_…``) live here at their target dosage rather than as
# entries in ``STRAIN_SYNONYMS`` because the ingest layer treats them
# as canonical strain names of their own (Laurin's filename parser
# stores ``nompC_het`` verbatim). The dosage map intentionally papers
# over the cross-student label drift at *viz* time, leaving the
# storage layer's notion of canonical untouched.
#
# Mapping confirmed by Bart on 2026-05-14:
#   - NompC3 / nompC_hom              → 0    (null; immobile)
#   - NompC-HeterozControl / nompC_het → 1   (het; one WT copy)
#   - NompCPbac                       → 1.75 (piggyBac weak hypomorph)
#   - CantonS / white / 641           → 2    (wild-type)
#   - NompCRescue / UASnompC…         → 2    (functional rescue)
#   - NompCOverExpression             → 3    (super-physiological)
NOMPC_DOSAGE: dict[str, float] = {
    # Canonical Kossen-era names
    "NompC3":               0.0,
    "NompC-HeterozControl": 1.0,
    "NompCPbac":            1.75,
    "CantonS":              2.0,
    "white":                2.0,
    "641":                  2.0,
    "NompCRescue":          2.0,
    "NompCOverExpression":  3.0,
    # Cross-student aliases (Robert/Laurin labels for the same biology)
    "nompC_hom":            0.0,
    "nompC_het":            1.0,
    "UASnompC_UASGCaMP-Gr28bd_Gal4-arista": 2.0,
}


def nompc_dosage(strain_name: str | None) -> float | None:
    """Functional NompC dosage for a strain, ``None`` when unknown.

    Accepts both canonical names and cross-student aliases. Returns
    ``None`` for unrecognised strains and for non-string / NaN input.
    """
    if not isinstance(strain_name, str):
        return None
    return NOMPC_DOSAGE.get(strain_name)


# ┌────────────────────────────────────────────────────────────┐
# │ Processing constants  « stimulus response + adaptation »   │
# └────────────────────────────────────────────────────────────┘
# Kossen 2019 §2.4.3.1: for each step's target temperature, the
# response is the median ΔF/F across all frames where the sensor
# temperature lies within ±0.5 °C of the target while the target
# column equals that step's set-point. The ±0.5 °C tolerance also
# appears verbatim in _legacy/oldScripts/tempFileIO.py (`self.offset
# = 0.5`). The "10-frame window" referenced in the methods text is
# implemented in pytci as "all frames satisfying the combined mask"
# (50-600 frames per step in practice, not 10), so we follow the
# legacy code rather than the prose.

#: Half-width of the sensor-T tolerance window around a step's target,
#: in °C. Matches Kossen 2019's ``self.offset = 0.5``.
STIMULUS_RESPONSE_WINDOW_C: float = 0.5

#: Where to start the exponential-decay fit for HotAdapt / ColdAdapt
#: recordings, in seconds. Skips the pre-stimulus baseline so the
#: fit only sees the post-onset relaxation. 75 s matches the protocol
#: design in pytci's tempFileIO (75 s baseline + step), the same on
#: Robert's and Laurin's rigs.
ADAPTATION_FIT_START_S: float = 75.0


# ┌────────────────────────────────────────────────────────────┐
# │ Figure rules  « DPI, SVG font handling, output triples »   │
# └────────────────────────────────────────────────────────────┘

FIGURE_DPI: int = 200
FIGURE_DIR_DEFAULT: Path = REPO_ROOT / "figures"

# Apply these rcParams before saving so SVG text stays editable in
# Inkscape (CLAUDE.md § 7.2).
SVG_RC_PARAMS: dict[str, str] = {
    "svg.fonttype": "none",
}


def save_figure(
    fig: Figure,
    stem: str,
    output_dir: Path,
    csv_data: pd.DataFrame | None = None,
) -> tuple[Path, Path, Path | None]:
    """Export ``fig`` as SVG + PNG with an optional CSV data companion.

    Args:
        fig: Matplotlib figure to save.
        stem: Filename stem (no extension).
        output_dir: Target directory (created if needed).
        csv_data: Optional dataframe with the numeric values behind the
            figure. Written alongside as ``<stem>.csv`` for reviewer
            verification (CLAUDE.md § 7.2).

    Returns:
        Triple of (svg_path, png_path, csv_path_or_None).
    """
    import matplotlib.pyplot as plt  # local to keep module-load fast

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(SVG_RC_PARAMS)

    svg_path = output_dir / f"{stem}.svg"
    png_path = output_dir / f"{stem}.png"
    fig.savefig(svg_path)
    fig.savefig(png_path, dpi=FIGURE_DPI)

    csv_path: Path | None = None
    if csv_data is not None:
        csv_path = output_dir / f"{stem}.csv"
        csv_data.to_csv(csv_path, index=False)

    return svg_path, png_path, csv_path
