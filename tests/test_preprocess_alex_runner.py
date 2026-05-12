# ─────────────────────────────────────────────────────────────────
#  Tests for scripts/preprocess_alex_data.py
# ─────────────────────────────────────────────────────────────────
"""Discovery + per-recording-dir tests for the POC runner."""

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
    """All public callables on the new arista.preprocess-backed runner exist."""
    for name in (
        "main",
        "discover_recording_dirs",
        "iter_cell_csvs",
        "is_fiji_csv",
        "preprocess_one",
        "preprocess_recording_dir",
    ):
        assert hasattr(runner, name), f"missing {name!r}"
        assert callable(getattr(runner, name)), f"{name!r} is not callable"


# ─────────────────────────────────────────────────────────────────
#  is_fiji_csv pattern coverage
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name",
    [
        "l_CC01.csv", "r_HC02.csv", "l_HC10.csv",   # flat layout
        "CC_01.csv", "HC_02.csv", "WC_03.csv",      # HCS exp01 style
        "CC01.csv", "HC03.csv", "WC02.csv",         # HCS exp02 style
        "cc_01.csv", "hc01.csv",                    # lower-case variants
    ],
)
def test_is_fiji_csv_accepts(runner, name: str) -> None:
    assert runner.is_fiji_csv(Path(name)), f"{name!r} should be accepted"


@pytest.mark.parametrize(
    "name",
    [
        "temperature_data_2021_12_20-12_40.mat",
        "notes.txt.txt",
        "DisplaySettings.json",
        "comments.txt",
        "Arista_left_MMStack_Default.ome.tif",
        "stack.tif",
        "df_d0.tif",
        "X.csv",       # ambiguous; not a recognised Fiji name
        "data.csv",
    ],
)
def test_is_fiji_csv_rejects(runner, name: str) -> None:
    assert not runner.is_fiji_csv(Path(name)), f"{name!r} should be rejected"


# ─────────────────────────────────────────────────────────────────
#  discover_recording_dirs against the bundled tree
# ─────────────────────────────────────────────────────────────────

def test_discover_in_bundled_tree(runner) -> None:
    """The bundled data/raw/alex/641/ tree has two complete + four MAT-less animals."""
    source = REPO_ROOT / "data" / "raw" / "alex"
    eligible, skipped = runner.discover_recording_dirs(source)
    eligible_names = {p.name for p in eligible}
    assert eligible_names == {"WT_01_f", "WT_02_m"}
    # The four MAT-less animals are NOT reported as skipped — they have
    # no MAT at all, so discovery silently ignores them (matches the
    # 'not a recording dir' heuristic). We assert that explicitly so
    # this behaviour stays intentional rather than accidental.
    skipped_names = {p.name for p, _reason in skipped}
    assert skipped_names == set()


def test_discover_handles_missing_root(runner, tmp_path: Path) -> None:
    eligible, skipped = runner.discover_recording_dirs(tmp_path / "nope")
    assert eligible == []
    assert skipped == []


def test_discover_flags_unrecognised_csvs(runner, tmp_path: Path) -> None:
    """A dir with a MAT but only non-Fiji CSVs goes to ``skipped`` with a reason."""
    import numpy as np
    import scipy.io as sio

    rec_dir = tmp_path / "session"
    rec_dir.mkdir()
    sio.savemat(str(rec_dir / "temperature_data_2025_01_01-00_00.mat"),
                {"data": np.zeros((10, 5))})
    (rec_dir / "notes.csv").write_text("foo,bar\n1,2\n")

    eligible, skipped = runner.discover_recording_dirs(tmp_path)
    assert eligible == []
    assert len(skipped) == 1
    skipped_path, reason = skipped[0]
    assert skipped_path == rec_dir
    assert "no recognised Fiji CSVs" in reason


def test_discover_flags_multiple_mats(runner, tmp_path: Path) -> None:
    """Two MATs in one dir → skipped (we can't tell which sensor pairs with which CSV)."""
    import numpy as np
    import scipy.io as sio

    rec_dir = tmp_path / "session"
    rec_dir.mkdir()
    for tstamp in ("2025_01_01-00_00", "2025_01_01-00_01"):
        sio.savemat(str(rec_dir / f"temperature_data_{tstamp}.mat"),
                    {"data": np.zeros((10, 5))})
    (rec_dir / "l_CC01.csv").write_text("X,Y\n0,0.1\n")

    eligible, skipped = runner.discover_recording_dirs(tmp_path)
    assert eligible == []
    assert len(skipped) == 1
    assert "2 MAT files" in skipped[0][1]


# ─────────────────────────────────────────────────────────────────
#  iter_cell_csvs
# ─────────────────────────────────────────────────────────────────

def test_iter_cell_csvs_sorts_left_then_right(runner) -> None:
    source = REPO_ROOT / "data" / "raw" / "alex" / "641" / "WT_02_m"
    cells = list(runner.iter_cell_csvs(source))
    names = [c.name for c in cells]
    assert names == sorted(names)
    assert any(n.startswith("l_") for n in names)
    assert any(n.startswith("r_") for n in names)


# ─────────────────────────────────────────────────────────────────
#  Integration: preprocess one full animal dir end-to-end
# ─────────────────────────────────────────────────────────────────

def test_preprocess_recording_dir_end_to_end(runner, tmp_path: Path) -> None:
    source = REPO_ROOT / "data" / "raw" / "alex"
    output = tmp_path / "out"
    animal = source / "641" / "WT_01_f"
    counts = runner.preprocess_recording_dir(
        animal,
        output_root=output,
        source_root=source,
        drift_method="auto",
    )
    assert counts["ok"] == 4
    assert counts["errors"] == 0
    # Outputs mirror the input layout under output_root.
    written = sorted((output / "641" / "WT_01_f").glob("*.csv"))
    assert len(written) == 4
    # The CSV header carries the drift method.
    first_line = written[0].read_text().splitlines()[0]
    assert first_line.startswith("# drift_method:")
