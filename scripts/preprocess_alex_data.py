#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════╗
# ║  scripts — preprocess_alex_data.py                               ║
# ║  « POC: run Alex Busch's legacy pipeline on the bundled corpus » ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Walks data/raw/alex/<genotype>/<animal>/ and runs the legacy    ║
# ║  aristaSingleCellData.py on every Fiji ΔF/F CSV, pairing it with ║
# ║  the per-animal temperature_data_*.mat. Headless (matplotlib Agg ║
# ║  backend) so it runs in CI and on remote shells.                 ║
# ║                                                                  ║
# ║  Outputs land under preprocessed_output/alex/<genotype>/<animal>/║
# ║  which is gitignored. Override via --output.                     ║
# ║                                                                  ║
# ║  This script is a PROOF OF CONCEPT for the preprocessing track.  ║
# ║  Phase 2 of the refactor replaces it with                        ║
# ║      arista-preprocess batch --layout alex                       ║
# ║  built from the new arista.preprocess module.                    ║
# ╚══════════════════════════════════════════════════════════════════╝
"""Run the legacy aristaSingleCellData pipeline on every bundled Alex cell.

Usage:
    python scripts/preprocess_alex_data.py
    python scripts/preprocess_alex_data.py --source /mnt/hcs/Alex/CalciumImaging
    python scripts/preprocess_alex_data.py --output /tmp/scratch -v
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

# Headless backend before any matplotlib import via aristaSingleCellData.
import matplotlib

matplotlib.use("Agg")

# The legacy script lives outside the importable package; add to path.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "_legacy"))

from aristaSingleCellData import aristaSingleCellData  # noqa: E402

from rich.console import Console  # noqa: E402
from rich.progress import (  # noqa: E402
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

log = logging.getLogger("preprocess_alex")
console = Console()


# ─────────────────────────────────────────────────────────────────
#  Discovery
# ─────────────────────────────────────────────────────────────────

def scan_animal_dirs(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Walk *root* and split candidate animal dirs into eligible + skipped.

    A directory at depth ``<genotype>/<animal>/`` qualifies if it has at
    least one ``temperature_data_*.mat`` sensor file AND at least one
    ``[lr]_*.csv`` Fiji ROI export.

    Returns:
        Tuple ``(eligible, skipped)`` where ``skipped`` is a list of
        ``(path, reason)`` pairs so callers can show the user exactly
        why each candidate was dropped.
    """
    if not root.is_dir():
        return [], []

    eligible: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    for animal_dir in sorted(root.glob("*/*")):
        if not animal_dir.is_dir():
            continue
        has_mat = any(animal_dir.glob("temperature_data_*.mat"))
        has_csv = any(animal_dir.glob("[lr]_*.csv"))
        if has_mat and has_csv:
            eligible.append(animal_dir)
        elif has_csv and not has_mat:
            skipped.append((animal_dir, "no temperature_data_*.mat"))
        elif has_mat and not has_csv:
            skipped.append((animal_dir, "no [lr]_*.csv files"))
        # purely empty candidate dirs are silently ignored
    return eligible, skipped


def find_animal_dirs(root: Path) -> list[Path]:
    """Backwards-compatible thin wrapper that returns only the eligible dirs."""
    eligible, _ = scan_animal_dirs(root)
    return eligible


def iter_cell_csvs(animal_dir: Path) -> Iterator[Path]:
    """Yield Fiji CSVs in *animal_dir*, sorted left-then-right by name."""
    yield from sorted(animal_dir.glob("[lr]_*.csv"))


# ─────────────────────────────────────────────────────────────────
#  Per-animal preprocessing
# ─────────────────────────────────────────────────────────────────

def preprocess_animal(
    animal_dir: Path,
    output_root: Path,
    source_root: Path,
) -> dict[str, int]:
    """Run the legacy pipeline on every cell in *animal_dir*.

    The per-animal output directory mirrors the input path under
    *output_root*: ``<source_root>/<genotype>/<animal>/`` →
    ``<output_root>/<genotype>/<animal>/``.

    Returns:
        Tally dict with keys ``ok``, ``errors``, ``skipped``.
    """
    counts = {"ok": 0, "errors": 0, "skipped": 0}

    mats = list(animal_dir.glob("temperature_data_*.mat"))
    if len(mats) != 1:
        log.warning(
            "Skipping %s: expected exactly one temperature_data_*.mat, found %d",
            animal_dir, len(mats),
        )
        counts["skipped"] = 1
        return counts
    mat_path = mats[0]

    rel = animal_dir.relative_to(source_root)
    target = output_root / rel
    target.mkdir(parents=True, exist_ok=True)

    for csv_path in iter_cell_csvs(animal_dir):
        try:
            ascd = aristaSingleCellData(str(csv_path), str(mat_path))
            ascd.main(str(target))
            counts["ok"] += 1
            log.debug("OK   %s", csv_path.relative_to(source_root))
        except Exception as exc:  # noqa: BLE001 — legacy code raises broadly
            log.error(
                "FAIL %s: %s",
                csv_path.relative_to(source_root),
                exc,
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            counts["errors"] += 1

    return counts


# ─────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Proof-of-concept runner: preprocess every cell in Alex Busch's "
            "bundled Drosophila arista calcium-imaging tree using the legacy "
            "aristaSingleCellData pipeline. Outputs land in a gitignored dir."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "data/raw/alex",
        help="Source root with <genotype>/<animal>/ children "
             "(default: data/raw/alex; alt: /mnt/hcs/Alex/CalciumImaging)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "preprocessed_output/alex",
        help="Output root, gitignored by default "
             "(default: preprocessed_output/alex)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show DEBUG-level logging and full tracebacks.",
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
        log.error("Source directory does not exist: %s", args.source)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)

    animal_dirs, skipped = scan_animal_dirs(args.source)
    if not animal_dirs:
        log.error(
            "No animal directories with both a temperature MAT and Fiji CSVs "
            "found under %s",
            args.source,
        )
        return 1

    n_cells_expected = sum(len(list(iter_cell_csvs(d))) for d in animal_dirs)
    console.print(
        f"[bold]Source:[/bold] {args.source}\n"
        f"[bold]Output:[/bold] {args.output}\n"
        f"[bold]Eligible animals:[/bold] {len(animal_dirs)}  "
        f"[bold]Cells:[/bold] {n_cells_expected}\n"
    )
    if skipped:
        console.print(f"[yellow]{len(skipped)} animal dir(s) skipped:[/yellow]")
        for skipped_dir, reason in skipped:
            rel = skipped_dir.relative_to(args.source)
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
        task = progress.add_task("Preprocessing animals", total=len(animal_dirs))
        for animal_dir in animal_dirs:
            counts = preprocess_animal(animal_dir, args.output, args.source)
            for key, value in counts.items():
                total[key] += value
            rel = animal_dir.relative_to(args.source)
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
