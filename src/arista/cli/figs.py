# ─────────────────────────────────────────────────────────────────
#  arista-figs CLI entry point  « stub, wired in pyproject »
# ─────────────────────────────────────────────────────────────────
"""``arista-figs`` entry point. Implementation lands in sprint 9."""

from __future__ import annotations

import click

from arista import __version__


@click.command(name="arista-figs")
@click.version_option(__version__)
@click.option("--db", type=click.Path(exists=True), help="Path to arista.db.")
@click.option("--figure", type=str, default=None, help="Specific figure (F2 / F3 / …) or omit for all.")
@click.option("--output", type=click.Path(), default="figures/", help="Output directory.")
def main(db: str | None, figure: str | None, output: str) -> None:
    """Rebuild publication figures from a populated arista.db."""
    click.echo(
        f"arista-figs v{__version__} — wired but not yet implemented "
        f"(db={db}, figure={figure}, output={output})"
    )
