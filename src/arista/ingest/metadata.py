# ─────────────────────────────────────────────────────────────────
#  arista.ingest.metadata
#  « path-name parsers: animal label + cell label → structured fields »
# ─────────────────────────────────────────────────────────────────
"""Filename + directory-name parsers that recover dimension-table fields.

Two layers:

* **Animal label** (the directory name above each session's Fiji CSVs):
  ``WT_02_m`` → sex=``'m'``, animal_number=2, arista_suffix=``None``.
  The leading strain code is captured for sanity-checks but the
  canonical strain comes from the parent genotype directory
  (``641`` / ``605`` / ``nomp_C`` in Alex's tree), not from this label.

* **Cell label** (the Fiji filename stem itself): handled by
  :func:`arista.constants.parse_fiji_filename` — already covers every
  observed pattern.

The deep HCS layout (``<genotype>/<date>/<exp>/Arista_<side>/``) is
recognised but the full parser is deferred to the next ingest sprint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────
#  Dataclasses
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnimalLabel:
    """Parsed animal-directory components.

    Attributes:
        strain_prefix: The leading token (e.g. ``'WT'`` / ``'nompC'``)
            present in the directory name. Informational — the
            *canonical* strain comes from the genotype directory one
            level up.
        animal_number: The 1-based animal-of-the-day integer.
        sex: ``'m'`` / ``'f'`` / ``'u'``.
        arista_suffix: ``'b'`` for the second arista on the same fly;
            ``None`` otherwise. Robert's `f02b` convention is the
            inspiration; Alex uses this rarely.
    """

    strain_prefix: str
    animal_number: int
    sex: str
    arista_suffix: str | None


# ─────────────────────────────────────────────────────────────────
#  Regex
# ─────────────────────────────────────────────────────────────────

#: Match an animal directory name. Tolerates strain prefixes that
#: themselves contain underscores by being greedy on the prefix and
#: anchoring the trailing ``_<number>[<suffix>]_<sex>`` block.
_ANIMAL_LABEL_PATTERN: re.Pattern[str] = re.compile(
    r"""
    ^
    (?P<strain_prefix>[A-Za-z][A-Za-z0-9_-]*?)
    _
    (?P<animal_number>\d+)
    (?P<arista_suffix>[a-z])?
    _
    (?P<sex>[mfu])
    $
    """,
    re.VERBOSE,
)


def parse_animal_label(label: str) -> AnimalLabel | None:
    """Parse an animal-directory name into structured fields.

    Returns ``None`` if ``label`` does not match the expected pattern,
    so callers can ``filter()`` without try/except boilerplate.

    Args:
        label: Directory base-name, e.g. ``'WT_02_m'`` or
            ``'nompC_01_f'`` or ``'WT_02b_m'``.

    Returns:
        An :class:`AnimalLabel` if the name parses, else ``None``.
    """
    match = _ANIMAL_LABEL_PATTERN.match(label)
    if match is None:
        return None
    return AnimalLabel(
        strain_prefix=match["strain_prefix"],
        animal_number=int(match["animal_number"]),
        sex=match["sex"],
        arista_suffix=match["arista_suffix"],
    )
