# ─────────────────────────────────────────────────────────────────
#  Smoke tests  « package imports, fixtures resolve »
# ─────────────────────────────────────────────────────────────────
"""Smoke tests that verify the Phase 0 skeleton is wired correctly."""

from __future__ import annotations

from pathlib import Path


def test_package_imports() -> None:
    """The top-level package and every subpackage import cleanly."""
    import arista
    import arista.cli
    import arista.constants
    import arista.db
    import arista.fitting
    import arista.ingest
    import arista.ingest.parsers
    import arista.preprocess
    import arista.processing
    import arista.viz

    assert hasattr(arista, "__version__")
    assert isinstance(arista.__version__, str)


def test_fixture_paths_resolve() -> None:
    """Shipped demo data is reachable from the package constants."""
    from arista import constants

    assert constants.DATA_DIR.is_dir(), f"DATA_DIR missing: {constants.DATA_DIR}"
    assert constants.FIJI_FIXTURE_DIR.is_dir()
    assert constants.SENSOR_FIXTURE_DIR.is_dir()

    # at least one Fiji ΔF/F export should ship
    fiji_csvs = list(constants.FIJI_FIXTURE_DIR.glob("*.csv"))
    assert fiji_csvs, "no Fiji fixture CSVs found in data/fiji/"

    # at least one sensor MAT should ship
    sensor_mats = list(constants.SENSOR_FIXTURE_DIR.glob("*.mat"))
    assert sensor_mats, "no sensor MAT fixtures found in data/sensor/"


def test_cli_entry_points_invokable() -> None:
    """The three CLI ``main`` callables are importable + non-empty."""
    from arista.cli import figs, ingest, preprocess

    for module in (preprocess, ingest, figs):
        assert callable(module.main), f"{module.__name__}.main is not callable"


def test_constants_paths_are_absolute() -> None:
    """Package constants resolve to absolute paths (no surprises at runtime)."""
    from arista import constants

    for name in ("PACKAGE_ROOT", "REPO_ROOT", "DATA_DIR"):
        path: Path = getattr(constants, name)
        assert path.is_absolute(), f"{name} should be absolute, got {path}"
