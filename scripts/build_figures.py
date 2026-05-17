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
    - sigmoid_fits: per-strain × cell-type 4PL overlay per stimulus
      (Kossen 2019 Fig 24 / 25), PNG + SVG.
    - adaptation_taus: τ raincloud per adaptation stimulus
      (Kossen 2019 Fig 21), PNG + SVG + CSV companion.
    - nompc_dosage: headline gain-vs-NompC-dosage raincloud pooled
      across all four ramp protocols, PNG + SVG + CSV companion.

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
from arista.processing.sigmoid import fit_sigmoids_by_group  # noqa: E402
from arista.viz.adaptation_taus import (  # noqa: E402
    AdaptationTaus,
    discover_adaptation_stimuli,
    fetch_adaptation_taus,
)
from arista.viz.gain_comparison import (  # noqa: E402
    GainComparison,
    fetch_recording_gains,
)
from arista.viz.nompc_dosage import (  # noqa: E402
    DEFAULT_DOSAGE_STIMULI,
    NompCDosage,
    fetch_dosage_gains,
)
from arista.viz.response_curves import (  # noqa: E402
    ErrorBand,
    ResponseCurves,
    aggregate_response_data,
    fetch_response_data,
)
from arista.viz.sigmoid_fits import SigmoidFits  # noqa: E402

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


def build_sigmoid_fits(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    console: Console,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
) -> list[Path]:
    """One sigmoid-overlay figure per thermal-step stimulus."""
    plotter = SigmoidFits(cell_types=cell_types, strains=strains)
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
        fig = plotter(df, stimulus_name=stim)
        png_path = plotter.save(fig, output_dir / f"sigmoid_fits_{stim}.png")
        # Per-group fit parameters as CSV companion (reviewers want numbers,
        # not just the curve).
        fit_table = fit_sigmoids_by_group(df)
        csv_path = png_path.with_suffix(".csv")
        fit_table.to_csv(csv_path, index=False)
        n_recordings = df["recording_id"].nunique()
        n_strains = df["strain_name"].nunique()
        console.log(
            f"[green]✓[/] {stim}: {n_recordings} recordings × "
            f"{n_strains} strains → {png_path.name}"
        )
        written.extend([png_path, png_path.with_suffix(".svg"), csv_path])
    return written


def build_nompc_dosage(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    console: Console,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    stimulus_names: tuple[str, ...] = DEFAULT_DOSAGE_STIMULI,
    abs_gain: bool = True,
) -> list[Path]:
    """Single headline figure: gain vs NompC dosage pooled across stimuli."""
    plotter = NompCDosage(
        cell_types=cell_types, stimulus_names=stimulus_names,
        abs_gain=abs_gain,
    )
    df = fetch_dosage_gains(
        conn, stimulus_names=stimulus_names, cell_types=cell_types,
    )
    if df.empty:
        console.log(
            "[yellow]no recordings with known NompC dosage; "
            "skipping nompc_dosage[/]"
        )
        return []

    fig = plotter(df)
    png_path = plotter.save(fig, output_dir / "nompc_dosage.png")
    csv_path = png_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    n_recordings = df["recording_id"].nunique()
    n_strains = df["canonical_strain"].nunique()
    console.log(
        f"[green]✓[/] {n_recordings} recordings × {n_strains} canonical "
        f"strains pooled across {len(stimulus_names)} stimuli → "
        f"{png_path.name}"
    )
    return [png_path, png_path.with_suffix(".svg"), csv_path]


def build_adaptation_taus(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    console: Console,
    cell_types: tuple[str, ...] = ("CC", "HC"),
    strains: tuple[str, ...] | None = None,
    log_tau: bool = True,
    min_r_squared: float | None = None,
) -> list[Path]:
    """One τ-raincloud figure per adaptation stimulus."""
    plotter = AdaptationTaus(
        cell_types=cell_types, strains=strains,
        log_tau=log_tau, min_r_squared=min_r_squared,
    )
    stimuli = discover_adaptation_stimuli(conn)
    if not stimuli:
        console.log("[yellow]no adaptation_fits rows found; skipping[/]")
        return []

    written: list[Path] = []
    for stim in stimuli:
        taus = fetch_adaptation_taus(
            conn, stimulus_name=stim,
            cell_types=cell_types, strains=strains,
            min_r_squared=min_r_squared,
        )
        if taus.empty:
            console.log(f"[dim]skipping {stim}: no recordings after filter[/]")
            continue
        fig = plotter(taus, stimulus_name=stim)
        png_path = plotter.save(fig, output_dir / f"adaptation_taus_{stim}.png")
        csv_path = png_path.with_suffix(".csv")
        taus.to_csv(csv_path, index=False)
        n_recordings = taus["recording_id"].nunique()
        n_strains = taus["strain_name"].nunique()
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
        choices=(
            "response_curves",
            "gain_comparison",
            "sigmoid_fits",
            "adaptation_taus",
            "nompc_dosage",
            "all",
        ),
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
    parser.add_argument(
        "--linear-tau",
        action="store_true",
        help=(
            "Use a linear y-axis for adaptation_taus (default is log, "
            "since τ is positively skewed)."
        ),
    )
    parser.add_argument(
        "--min-tau-r2",
        type=float,
        default=None,
        help=(
            "Drop adaptation_taus rows below this R² threshold "
            "(default: no filter)."
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
    do_sigmoid = args.figure in ("sigmoid_fits", "all")
    do_tau = args.figure in ("adaptation_taus", "all")
    do_dosage = args.figure in ("nompc_dosage", "all")

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
        if do_sigmoid:
            console.log("[bold cyan]sigmoid_fits[/]")
            written = build_sigmoid_fits(
                conn, args.output / "sigmoid_fits",
                console=console,
                cell_types=cell_types,
                strains=strains,
            )
            total_written += len(written)
        if do_tau:
            console.log(
                f"[bold cyan]adaptation_taus[/] "
                f"(log_tau = {not args.linear_tau}, "
                f"min_r² = {args.min_tau_r2})"
            )
            written = build_adaptation_taus(
                conn, args.output / "adaptation_taus",
                console=console,
                cell_types=cell_types,
                strains=strains,
                log_tau=not args.linear_tau,
                min_r_squared=args.min_tau_r2,
            )
            total_written += len(written)
        if do_dosage:
            # The dosage headline asks "does dosage drive responsiveness",
            # so |gain| is the right default regardless of how the CLI
            # --abs-gain flag was set for gain_comparison. Use the Python
            # API directly (plot_nompc_dosage(..., abs_gain=False)) if you
            # need the signed view.
            console.log("[bold cyan]nompc_dosage[/] (abs_gain = True)")
            written = build_nompc_dosage(
                conn, args.output / "nompc_dosage",
                console=console,
                cell_types=cell_types,
                abs_gain=True,
            )
            total_written += len(written)

    console.log(f"wrote {total_written} files under [bold]{args.output}[/]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
