# ─────────────────────────────────────────────────────────────────
#  Smoke tests for scripts/preprocess_alex_data.py
# ─────────────────────────────────────────────────────────────────
"""Sanity checks for the POC preprocessing runner against bundled data."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "preprocess_alex_data.py"


@pytest.fixture(scope="module")
def runner():
    """Import scripts/preprocess_alex_data.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "preprocess_alex_data", SCRIPT_PATH
    )
    assert spec and spec.loader, f"failed to load spec for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["preprocess_alex_data"] = module
    spec.loader.exec_module(module)
    return module


def test_runner_script_exists() -> None:
    assert SCRIPT_PATH.is_file()
    assert SCRIPT_PATH.stat().st_mode & 0o111, "script should be executable"


def test_runner_imports(runner) -> None:
    assert hasattr(runner, "main")
    assert hasattr(runner, "scan_animal_dirs")
    assert hasattr(runner, "find_animal_dirs")
    assert hasattr(runner, "preprocess_animal")
    assert callable(runner.main)


def test_scan_finds_two_eligible_and_four_skipped(runner) -> None:
    """The bundled data/raw/alex/641/ tree has two complete animals + four MAT-less."""
    source = REPO_ROOT / "data" / "raw" / "alex"
    eligible, skipped = runner.scan_animal_dirs(source)

    eligible_names = {p.name for p in eligible}
    assert eligible_names == {"WT_01_f", "WT_02_m"}

    skipped_names = {p.name for p, _reason in skipped}
    assert skipped_names == {"WT_03_f", "WT_04_f", "WT_05_f", "WT_06_m"}

    # Every skip reason mentions the missing MAT
    for _path, reason in skipped:
        assert "temperature_data" in reason


def test_scan_on_missing_root_returns_empty(runner, tmp_path: Path) -> None:
    nowhere = tmp_path / "does-not-exist"
    eligible, skipped = runner.scan_animal_dirs(nowhere)
    assert eligible == []
    assert skipped == []


def test_find_animal_dirs_is_alias_for_eligible(runner) -> None:
    source = REPO_ROOT / "data" / "raw" / "alex"
    legacy = runner.find_animal_dirs(source)
    eligible, _ = runner.scan_animal_dirs(source)
    assert legacy == eligible


def test_iter_cell_csvs_returns_sorted_lr_files(runner) -> None:
    source = REPO_ROOT / "data" / "raw" / "alex" / "641" / "WT_02_m"
    cells = list(runner.iter_cell_csvs(source))
    names = [c.name for c in cells]
    # Sorted: all l_* come before r_*; within each side, alphabetical.
    assert names == sorted(names)
    assert any(n.startswith("l_") for n in names)
    assert any(n.startswith("r_") for n in names)
