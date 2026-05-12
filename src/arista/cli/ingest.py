# ─────────────────────────────────────────────────────────────────
#  arista-ingest CLI entry point
# ─────────────────────────────────────────────────────────────────
"""``arista-ingest`` — load preprocessed CSVs into the SQLite database.

Phase-4 scope: Alex flat layout only. Robert / Niko / Laurin parsers
land in a follow-up sprint once the schema is locked against real
ingested data.

Path resolution:

* ``--db PATH``  explicit override
* ``$ARISTA_DB`` environment variable
* ``./arista.db`` in the current working directory (fallback)
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from arista import __version__
from arista.db.connection import open_db, resolve_db_path
from arista.ingest.orchestrator import IngestStats, ingest_one, prepare_db
from arista.ingest.parsers.alex import (
    DEFAULT_STIMULUS_NAME,
    DiscoveryResult,
    discover_alex_records,
)
from arista.ingest.parsers.laurin import discover_laurin_records
from arista.ingest.parsers.robert import discover_robert_records

console = Console()

_DEFAULT_SOURCE = Path.cwd() / "preprocessed_output" / "alex"

# Each layout maps to a discovery function. The Alex discoverer is the
# only one that takes a stimulus keyword (its source paths don't encode
# the protocol); Robert + Laurin extract stimulus from the filename.
_LAYOUT_DISPATCH: dict[str, object] = {
    "alex":   discover_alex_records,
    "laurin": discover_laurin_records,
    "robert": discover_robert_records,
}


@click.command(name="arista-ingest")
@click.version_option(__version__)
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "SQLite database path. Falls back to $ARISTA_DB, then ./arista.db. "
        "Parent directories are created on first connect."
    ),
)
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=str(_DEFAULT_SOURCE),
    show_default=True,
    help="Root containing <genotype>/<animal>/*.csv preprocessed files.",
)
@click.option(
    "--layout",
    type=click.Choice(sorted(_LAYOUT_DISPATCH)),
    default="alex",
    show_default=True,
    help=(
        "Source-tree layout. 'alex' walks <genotype>/<animal>/*.csv "
        "preprocessed by arista-preprocess; 'robert' walks "
        "Compiled_data_pickled/<genotype>/*.txt; 'laurin' walks "
        "ms-thesis/result/*.csv."
    ),
)
@click.option(
    "--stimulus",
    type=str,
    default=DEFAULT_STIMULUS_NAME,
    show_default=True,
    help=(
        "Stimulus protocol name to assign to every ingested recording. "
        "Used only by --layout alex; robert/laurin extract the stimulus "
        "from the filename."
    ),
)
@click.option(
    "--test-n",
    type=int,
    default=None,
    help="Smoke-test: ingest only the first N discovered recordings.",
)
def main(
    db: Path | None,
    source: Path,
    layout: str,
    stimulus: str,
    test_n: int | None,
) -> None:
    """Ingest preprocessed Ca²⁺ CSVs into the arista SQLite database."""
    db_path = resolve_db_path(db)
    source = Path(source).resolve()

    console.print(
        f"[bold]Source:[/bold] {source}\n"
        f"[bold]DB:[/bold]     {db_path}\n"
        f"[bold]Layout:[/bold] {layout}  "
        f"[bold]Stimulus:[/bold] {stimulus}\n"
    )

    discoverer = _LAYOUT_DISPATCH[layout]
    # The Alex discoverer takes a stimulus kwarg (its paths don't carry it).
    # Other layouts encode stimulus in the filename and accept no extra args.
    if layout == "alex":
        discoveries: list[DiscoveryResult] = list(
            discoverer(source, stimulus_name=stimulus)  # type: ignore[call-arg]
        )
    else:
        discoveries = list(discoverer(source))  # type: ignore[call-arg]
    eligible = [d for d in discoveries if d.record is not None]
    skipped = [d for d in discoveries if d.record is None]

    if not eligible:
        console.print(
            f"[red]No ingestable recordings found under {source}.[/red]"
        )
        if skipped:
            console.print(f"[yellow]{len(skipped)} candidate(s) skipped:[/yellow]")
            for d in skipped:
                console.print(f"  · {d.csv_path}  — {d.reason}")
        raise SystemExit(1)

    if test_n is not None:
        eligible = eligible[:test_n]

    console.print(
        f"[bold]Eligible recordings:[/bold] {len(eligible)}  "
        f"[bold]skipped:[/bold] {len(skipped)}\n"
    )
    if skipped:
        for d in skipped[:5]:
            try:
                rel = d.csv_path.relative_to(source)
            except ValueError:
                rel = d.csv_path
            console.print(f"  [yellow]·[/yellow] [dim]{rel}[/dim] — {d.reason}")
        if len(skipped) > 5:
            console.print(f"  [dim]… {len(skipped) - 5} more[/dim]")
        console.print()

    stats = IngestStats()
    with open_db(db_path) as conn:
        prepare_db(conn)
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting", total=len(eligible))
            for d in eligible:
                assert d.record is not None  # for type-checkers
                try:
                    _, was_new, n_samples = ingest_one(conn, d.record)
                    if was_new:
                        stats.inserted_recordings += 1
                        stats.inserted_samples += n_samples
                    else:
                        stats.skipped_duplicates += 1
                except Exception as exc:  # noqa: BLE001
                    progress.console.log(
                        f"[red]FAIL {d.csv_path.name}[/red]: {exc}"
                    )
                    stats.errors += 1
                progress.advance(task)

    console.rule()
    console.print(
        f"[bold green]✓ {stats.inserted_recordings} new recordings[/bold green]"
        f"  [dim]{stats.skipped_duplicates} duplicates skipped[/dim]"
        f"  [yellow]{stats.errors} errors[/yellow]\n"
        f"[bold]{stats.inserted_samples}[/bold] sample rows inserted"
    )
    if stats.errors:
        raise SystemExit(1)
