#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════╗
# ║  scripts — preprocess_alex_data.py                               ║
# ║  « run arista.preprocess on every Alex Busch recording »         ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Walks <source> recursively for directories that contain both a  ║
# ║  temperature_data_*.mat and one or more Fiji ΔF/F CSVs, then     ║
# ║  preprocesses each cell via the headless arista.preprocess       ║
# ║  library (read_fiji_csv → read_sensor_mat → assemble_recording   ║
# ║  → correct_drift → write_recording_csv).                         ║
# ║                                                                  ║
# ║  Handles both the in-repo flat layout                            ║
# ║      data/raw/alex/<genotype>/<animal>/                          ║
# ║  and the HCS deep layout                                         ║
# ║      <genotype>/<date>/<exp>/Arista_<side>/                      ║
# ║  by treating every directory holding the MAT+CSV pair as a       ║
# ║  recording session, regardless of nesting depth.                 ║
# ║                                                                  ║
# ║  Outputs land under <output> with the same directory structure   ║
# ║  as <source>, defaulting to preprocessed_output/alex/ which is   ║
# ║  gitignored.                                                     ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Preprocess every Alex-style Drosophila arista recording via arista.preprocess.

Usage:
    # Default: process the bundled tree, AIC-pick drift per recording
    python scripts/preprocess_alex_data.py

    # Point at the HCS archive (handles the deeper layout)
    python scripts/preprocess_alex_data.py --source /mnt/hcs/Alex/CalciumImaging

    # Force a specific drift method
    python scripts/preprocess_alex_data.py --drift-method poly

    # Skip drift correction (useful for byte-comparison with legacy)
    python scripts/preprocess_alex_data.py --drift-method none

    # Verbose: DEBUG logs + full tracebacks
    python scripts/preprocess_alex_data.py -v
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

# Headless backend; the new arista.preprocess library never imports
# pyplot itself, but be defensive against future plotting additions.
import matplotlib

matplotlib.use("Agg")

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make the package importable when running from a clean source checkout
# without a `pip install -e .` (defensive; CI installs the package).
SRC = REPO_ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rich.console import Console  # noqa: E402
from rich.progress import (  # noqa: E402
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from arista.constants import (  # noqa: E402
    is_fiji_filename,
)
from arista.preprocess import (  # noqa: E402
    Recording,
    SensorRecord,
    assemble_recording,
    correct_drift,
    read_fiji_csv,
    read_sensor_mat,
    write_recording_csv,
)
from arista.viz import SessionOverview  # noqa: E402

log = logging.getLogger("preprocess_alex")
console = Console()

DriftMethodArg = Literal["auto", "linear", "poly", "exp", "none"]

def is_fiji_csv(path: Path) -> bool:
    """Return True if *path* matches any accepted Fiji ROI filename pattern.

    Thin wrapper around :func:`arista.constants.is_fiji_filename` so
    callers (and tests) need only import from this script.
    """
    return is_fiji_filename(path.name)


# ─────────────────────────────────────────────────────────────────
#  Discovery
# ─────────────────────────────────────────────────────────────────

def discover_recording_dirs(
    root: Path,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Recursively walk *root* for any directory that holds a recording.

    A directory qualifies if it contains *exactly one*
    ``temperature_data_*.mat`` and at least one CSV that matches
    :func:`is_fiji_csv`. Returns ``(eligible, skipped)`` where
    ``skipped`` is a list of ``(path, reason)`` pairs so callers can
    surface the coverage gap to the user.
    """
    if not root.is_dir():
        return [], []

    eligible: list[Path] = []
    skipped: list[tuple[Path, str]] = []

    # Iterate every directory under root (rglob('*') yields files too;
    # filter to dirs). Sort for reproducible output.
    candidates = sorted(p for p in root.rglob("*") if p.is_dir())
    # Include root itself in case the user points at a single session.
    candidates.insert(0, root)

    for path in candidates:
        mats = sorted(path.glob("temperature_data_*.mat"))
        if not mats:
            continue  # not a recording dir; silently ignore
        csvs = [p for p in sorted(path.iterdir()) if p.is_file() and is_fiji_csv(p)]
        if not csvs:
            skipped.append((path, "has MAT but no recognised Fiji CSVs"))
            continue
        if len(mats) > 1:
            skipped.append((path, f"has {len(mats)} MAT files (expected 1)"))
            continue
        eligible.append(path)

    return eligible, skipped


def iter_cell_csvs(recording_dir: Path) -> Iterator[Path]:
    """Yield every Fiji ROI CSV in *recording_dir*, sorted by filename."""
    return iter(
        sorted(
            (p for p in recording_dir.iterdir() if p.is_file() and is_fiji_csv(p)),
            key=lambda p: p.name,
        )
    )


# ─────────────────────────────────────────────────────────────────
#  Per-recording-directory preprocessing
# ─────────────────────────────────────────────────────────────────

def _output_path_for(
    csv_path: Path,
    recording_dir: Path,
    output_root: Path,
    source_root: Path,
) -> Path:
    """Mirror the input path under the output root, swap .csv extension."""
    rel_dir = recording_dir.relative_to(source_root)
    return output_root / rel_dir / csv_path.name


def preprocess_one(
    csv_path: Path,
    sensor: SensorRecord,
    drift_method: DriftMethodArg,
) -> Recording:
    """Full pipeline on a single cell: read → align → correct drift."""
    fiji = read_fiji_csv(csv_path)
    recording = assemble_recording(fiji, sensor)
    return correct_drift(recording, method=drift_method)


def preprocess_recording_dir(
    recording_dir: Path,
    output_root: Path,
    source_root: Path,
    drift_method: DriftMethodArg,
    *,
    plotter: SessionOverview | None = None,
) -> dict[str, int]:
    """Preprocess every cell in *recording_dir*. Returns ``ok / errors / skipped`` tally.

    If a :class:`SessionOverview` is supplied, also writes a dual-y-axis
    PNG (``_overview.png``) summarising every successfully preprocessed
    cell in the session, sharing the temperature trace.
    """
    counts = {"ok": 0, "errors": 0, "skipped": 0}

    mats = list(recording_dir.glob("temperature_data_*.mat"))
    if len(mats) != 1:
        counts["skipped"] = 1
        return counts

    try:
        sensor = read_sensor_mat(mats[0])
    except Exception as exc:  # noqa: BLE001 - we want any read error logged
        log.error(
            "FAIL sensor %s: %s",
            mats[0],
            exc,
            exc_info=log.isEnabledFor(logging.DEBUG),
        )
        counts["errors"] = 1
        return counts

    # Collect successfully preprocessed cells in insertion order so the
    # session-overview legend reflects the on-disk filename order.
    session_recordings: dict[str, Recording] = {}

    for csv_path in iter_cell_csvs(recording_dir):
        try:
            recording = preprocess_one(csv_path, sensor, drift_method)
            out_path = _output_path_for(
                csv_path, recording_dir, output_root, source_root
            )
            write_recording_csv(recording, out_path)
            counts["ok"] += 1
            session_recordings[csv_path.stem] = recording
            log.debug(
                "OK   %s → %s (drift=%s)",
                csv_path.relative_to(source_root),
                out_path.relative_to(output_root),
                recording.drift_method,
            )
        except Exception as exc:  # noqa: BLE001 - log full context
            log.error(
                "FAIL %s: %s",
                csv_path.relative_to(source_root),
                exc,
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            counts["errors"] += 1

    if plotter is not None and session_recordings:
        try:
            session_dir = output_root / recording_dir.relative_to(source_root)
            title = str(recording_dir.relative_to(source_root))
            fig = plotter(session_recordings, title=title)
            plotter.save(fig, session_dir / "_overview.png")
            log.debug("PLOT %s/_overview.png", session_dir.relative_to(output_root))
        except Exception as exc:  # noqa: BLE001 - plotting is best-effort
            log.warning(
                "Overview plot failed for %s: %s",
                recording_dir.relative_to(source_root),
                exc,
                exc_info=log.isEnabledFor(logging.DEBUG),
            )

    return counts


# ─────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run arista.preprocess on every Alex-style Drosophila arista "
            "Ca²⁺ recording in <source>. Walks recursively; handles both "
            "the in-repo flat layout and the HCS deeper layout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "data" / "raw" / "alex",
        help=(
            "Source data root (default: data/raw/alex). "
            "Try /mnt/hcs/Alex/CalciumImaging for the full archive."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "preprocessed_output" / "alex",
        help="Output root, gitignored by default.",
    )
    parser.add_argument(
        "--drift-method",
        choices=["auto", "linear", "poly", "exp", "none"],
        default="auto",
        help=(
            "Drift correction method (default: auto = AIC-picked). "
            "Use 'none' to skip drift correction."
        ),
    )
    parser.add_argument(
        "--no-plot",
        dest="plot",
        action="store_false",
        default=True,
        help="Skip the per-session dual-y-axis overview PNG.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG-level logging and full tracebacks on failure.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if not args.source.is_dir():
        log.error("Source directory not found: %s", args.source)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)

    eligible, skipped = discover_recording_dirs(args.source)
    if not eligible:
        log.error(
            "No recording directories found under %s "
            "(looking for dirs with one temperature_data_*.mat plus "
            "at least one Fiji CSV)",
            args.source,
        )
        return 1

    n_cells_expected = sum(len(list(iter_cell_csvs(d))) for d in eligible)
    plotter = SessionOverview() if args.plot else None
    console.print(
        f"[bold]Source:[/bold] {args.source}\n"
        f"[bold]Output:[/bold] {args.output}\n"
        f"[bold]Drift method:[/bold] {args.drift_method}\n"
        f"[bold]Session overview PNG:[/bold] "
        f"{'enabled' if plotter else 'disabled'}\n"
        f"[bold]Eligible recording dirs:[/bold] {len(eligible)}  "
        f"[bold]Cells:[/bold] {n_cells_expected}\n"
    )
    if skipped:
        console.print(f"[yellow]{len(skipped)} candidate dir(s) skipped:[/yellow]")
        for skipped_dir, reason in skipped:
            try:
                rel = skipped_dir.relative_to(args.source)
            except ValueError:
                rel = skipped_dir
            console.print(f"  [yellow]·[/yellow] [dim]{rel}[/dim] — {reason}")
        console.print()

    total = {"ok": 0, "errors": 0, "skipped": 0}
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Preprocessing recordings", total=len(eligible))
        for recording_dir in eligible:
            counts = preprocess_recording_dir(
                recording_dir,
                args.output,
                args.source,
                args.drift_method,
                plotter=plotter,
            )
            for key, value in counts.items():
                total[key] += value
            try:
                rel = recording_dir.relative_to(args.source)
            except ValueError:
                rel = recording_dir
            progress.console.log(
                f"  [cyan]{rel}[/cyan]  "
                f"[green]{counts['ok']} ok[/green]  "
                f"[red]{counts['errors']} err[/red]"
            )
            progress.advance(task)

    console.rule()
    console.print(
        f"[bold green]✓ {total['ok']} cells preprocessed[/bold green]"
        f"   [yellow]{total['errors']} errors[/yellow]"
        f"   [dim]{total['skipped']} skipped[/dim]"
    )
    console.print(f"Outputs in [bold]{args.output}[/bold]")
    return 0 if total["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
