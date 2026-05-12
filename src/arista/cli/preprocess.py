# ─────────────────────────────────────────────────────────────────
#  arista-preprocess CLI entry point  « stub, wired in pyproject »
# ─────────────────────────────────────────────────────────────────
"""``arista-preprocess`` entry point. Subcommands land in sprint 3.

Planned surface:

* ``align``     — one Fiji + one MAT → aligned CSV
* ``drift``     — aligned CSV → drift-corrected CSV
* ``response``  — corrected CSV → per-step response medians
* ``batch``     — walk a directory tree, dispatch end-to-end
* ``validate``  — sanity-check a preprocessed CSV
"""

from __future__ import annotations

import click

from arista import __version__


@click.group(name="arista-preprocess")
@click.version_option(__version__)
def main() -> None:
    """Reproduce the pytci preprocessing stages headlessly."""


@main.command()
def hello() -> None:
    """Smoke-test command (delete once real subcommands land)."""
    click.echo(f"arista-preprocess v{__version__} — wired but not yet implemented")
