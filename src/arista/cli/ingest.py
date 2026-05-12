# ─────────────────────────────────────────────────────────────────
#  arista-ingest CLI entry point  « stub, wired in pyproject »
# ─────────────────────────────────────────────────────────────────
"""``arista-ingest`` entry point. Implementation lands in sprint 6."""

from __future__ import annotations

import click

from arista import __version__


@click.command(name="arista-ingest")
@click.version_option(__version__)
@click.option("--root", type=click.Path(exists=True), help="Source data root (e.g. /mnt/hcs).")
@click.option("--db", type=click.Path(), default="arista.db", help="Target SQLite path.")
@click.option("--test-n", type=int, default=None, help="Ingest only N files per source (smoke test).")
def main(root: str | None, db: str, test_n: int | None) -> None:
    """Walk source data and insert preprocessed recordings into SQLite."""
    click.echo(
        f"arista-ingest v{__version__} — wired but not yet implemented "
        f"(root={root}, db={db}, test_n={test_n})"
    )
