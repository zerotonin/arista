#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  scripts/build_figures.py
#  « rebuild the publication figure set from arista.db »
# ─────────────────────────────────────────────────────────────────
"""Build the arista publication figure set against a populated database.

Currently builds:
    - response_curves: one figure per thermal-step stimulus (Kossen
      2019 Fig 19 / 22-23), saved as PNG + SVG + CSV companion.

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
from arista.viz.response_curves import (  # noqa: E402
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
) -> list[Path]:
    """One response-curve figure per thermal-step stimulus."""
    plotter = ResponseCurves(cell_types=cell_types, strains=strains)
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
        default=Path("figures"),
        help="Root output directory (default: ./figures).",
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
    args = parser.parse_args(argv)

    console = Console()
    db_path = resolve_db_path(args.db)
    console.log(f"reading [bold]{db_path}[/]")
    output_root = args.output / "response_curves"

    cell_types = tuple(args.cell_type) if args.cell_type else ("CC", "HC")
    strains = tuple(args.strain) if args.strain else None

    with open_db(db_path) as conn:
        written = build_response_curves(
            conn, output_root,
            console=console,
            cell_types=cell_types,
            strains=strains,
        )

    console.log(f"wrote {len(written)} files under [bold]{output_root}[/]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
