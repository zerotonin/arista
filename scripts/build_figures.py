#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  scripts/build_figures.py
#  « rebuild the publication figure set from arista.db »
# ─────────────────────────────────────────────────────────────────
"""Build the arista publication figure set against a populated database.

Currently builds:
    - response_curves: one figure per thermal-step stimulus (Kossen
      2019 Fig 19 / 22-23), saved as PNG + SVG + CSV companion.
    - gain_comparison: one raincloud figure per thermal-step stimulus
      (Kossen 2019 Fig 27), saved as PNG + SVG + CSV companion.

``--figure`` lets you build only one family; the default ``all``
builds every family.

Run with::

    python scripts/build_figures.py --db /media/geuba03p/DATADRIVE1/arista/arista.db

If ``--db`` is omitted the same resolution order as the CLIs applies
(``$ARISTA_DB`` → ``./arista.db``).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless

from rich.console import Console  # noqa: E402

from arista.db.connection import open_db, resolve_db_path  # noqa: E402
from arista.viz.gain_comparison import (  # noqa: E402
    GainComparison,
    fetch_recording_gains,
)
from arista.viz.response_curves import (  # noqa: E402
    ErrorBand,
    ResponseCurves,
    aggregate_response_data,
    fetch_response_data,
)

# ─────────────────────────────────────────────────────────────────
#  Discovery
# ─────────────────────────────────────────────────────────────────


def discover_thermal_step_stimuli(conn: sqlite3.Connection) -> list[str]:
    """Stimulus protocols that produced rows in ``stimulus_responses``."""
    cur = conn.execute(
        """
        SELECT DISTINCT v.stimulus_name
        FROM stimulus_responses sr
        JOIN v_recordings v ON v.recording_id = sr.recording_id
        ORDER BY v.stimulus_name
        """
    )
    return [row[0] for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────
#  Render
# ─────────────────────────────────────────────────────────────────


def build_response_curves(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    console: Console,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    error: ErrorBand = "ci",
) -> list[Path]:
    """One response-curve figure per thermal-step stimulus."""
    plotter = ResponseCurves(
        cell_types=cell_types, strains=strains, error=error,
    )
    stimuli = discover_thermal_step_stimuli(conn)
    if not stimuli:
        console.log("[yellow]no stimulus_responses rows found; skipping[/]")
        return []

    written: list[Path] = []
    for stim in stimuli:
        df = fetch_response_data(
            conn, stimulus_name=stim,
            cell_types=cell_types, strains=strains,
        )
        if df.empty:
            console.log(f"[dim]skipping {stim}: no rows after filter[/]")
            continue
        agg = aggregate_response_data(df)
        fig = plotter(df, stimulus_name=stim)
        png_path = plotter.save(fig, output_dir / f"response_curves_{stim}.png")
        csv_path = png_path.with_suffix(".csv")
        agg.to_csv(csv_path, index=False)
        n_recordings = df["recording_id"].nunique()
        n_strains = df["strain_name"].nunique()
        console.log(
            f"[green]✓[/] {stim}: {n_recordings} recordings × "
            f"{n_strains} strains → {png_path.name}"
        )
        written.extend([png_path, png_path.with_suffix(".svg"), csv_path])
    return written


def build_gain_comparisons(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    console: Console,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    abs_gain: bool = False,
) -> list[Path]:
    """One gain-raincloud figure per thermal-step stimulus."""
    plotter = GainComparison(
        cell_types=cell_types, strains=strains, abs_gain=abs_gain,
    )
    stimuli = discover_thermal_step_stimuli(conn)
    if not stimuli:
        console.log("[yellow]no stimulus_responses rows found; skipping[/]")
        return []

    written: list[Path] = []
    for stim in stimuli:
        gains = fetch_recording_gains(
            conn, stimulus_name=stim,
            cell_types=cell_types, strains=strains,
        )
        if gains.empty:
            console.log(f"[dim]skipping {stim}: no recordings after filter[/]")
            continue
        fig = plotter(gains, stimulus_name=stim)
        png_path = plotter.save(fig, output_dir / f"gain_comparison_{stim}.png")
        csv_path = png_path.with_suffix(".csv")
        gains.to_csv(csv_path, index=False)
        n_recordings = gains["recording_id"].nunique()
        n_strains = gains["strain_name"].nunique()
        console.log(
            f"[green]✓[/] {stim}: {n_recordings} recordings × "
            f"{n_strains} strains → {png_path.name}"
        )
        written.extend([png_path, png_path.with_suffix(".svg"), csv_path])
    return written


# ─────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to arista.db (defaults to $ARISTA_DB or ./arista.db).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figure_output"),
        help=(
            "Root output directory (default: ./figure_output). "
            "Regenerable from the DB, gitignored."
        ),
    )
    parser.add_argument(
        "--cell-type",
        action="append",
        default=None,
        help="Cell types to plot (repeatable; default CC + HC).",
    )
    parser.add_argument(
        "--strain",
        action="append",
        default=None,
        help="Restrict to these strains (repeatable; default all).",
    )
    parser.add_argument(
        "--error",
        choices=("ci", "iqr", "sem", "none"),
        default="ci",
        help=(
            "Error band mode for response_curves (default: ci). "
            "ci = median ± 95%% bootstrap CI; "
            "iqr = median ± IQR; "
            "sem = mean ± SEM (Shapiro-Wilk gated, falls back to ci); "
            "none = centre line only."
        ),
    )
    parser.add_argument(
        "--figure",
        choices=("response_curves", "gain_comparison", "all"),
        default="all",
        help="Which figure family to build (default: all).",
    )
    parser.add_argument(
        "--abs-gain",
        action="store_true",
        help=(
            "Plot |gain| (absolute slope magnitude) instead of signed "
            "slope on gain_comparison."
        ),
    )
    args = parser.parse_args(argv)

    console = Console()
    db_path = resolve_db_path(args.db)
    console.log(f"reading [bold]{db_path}[/]")

    cell_types = tuple(args.cell_type) if args.cell_type else ("CC", "HC")
    strains = tuple(args.strain) if args.strain else None
    do_response = args.figure in ("response_curves", "all")
    do_gain = args.figure in ("gain_comparison", "all")

    total_written = 0
    with open_db(db_path) as conn:
        if do_response:
            console.log(f"[bold cyan]response_curves[/] (error band = {args.error})")
            written = build_response_curves(
                conn, args.output / "response_curves",
                console=console,
                cell_types=cell_types,
                strains=strains,
                error=args.error,
            )
            total_written += len(written)
        if do_gain:
            console.log(
                f"[bold cyan]gain_comparison[/] "
                f"(abs_gain = {args.abs_gain})"
            )
            written = build_gain_comparisons(
                conn, args.output / "gain_comparison",
                console=console,
                cell_types=cell_types,
                strains=strains,
                abs_gain=args.abs_gain,
            )
            total_written += len(written)

    console.log(f"wrote {total_written} files under [bold]{args.output}[/]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
