# ─────────────────────────────────────────────────────────────────
#  arista.db.connection  « open SQLite with the right pragmas »
# ─────────────────────────────────────────────────────────────────
"""Open a SQLite connection with the project conventions enabled.

The pragmas applied here are:

* ``foreign_keys = ON`` — schema enforces FK constraints; without this
  every CHECK / FK in :mod:`arista.db.schema` becomes silent metadata.
* ``journal_mode = WAL`` — write-ahead logging, gives concurrent reads
  during bulk insert and is cheap to enable per-connection.

The context manager closes the connection deterministically so the
caller doesn't have to remember.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Default DB path resolution order:
#   1. explicit ``db_path`` argument
#   2. ``$ARISTA_DB`` environment variable
#   3. ``./arista.db`` in the current working directory
_ENV_VAR_NAME = "ARISTA_DB"
_DEFAULT_DB_BASENAME = "arista.db"


def resolve_db_path(explicit: str | Path | None = None) -> Path:
    """Return the canonical DB path per the documented resolution order.

    Args:
        explicit: A user-supplied path (e.g. from ``--db`` on the CLI).
            ``None`` means defer to the environment / default.

    Returns:
        Absolute :class:`Path` to the target database file. The file
        itself need not exist yet — callers may open or build it.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env_value = os.environ.get(_ENV_VAR_NAME)
    if env_value:
        return Path(env_value).expanduser().resolve()
    return Path.cwd() / _DEFAULT_DB_BASENAME


@contextmanager
def open_db(
    path: str | Path,
    *,
    create_parents: bool = True,
    timeout: float = 30.0,
) -> Iterator[sqlite3.Connection]:
    """Context manager around :func:`sqlite3.connect` with FK pragma.

    Args:
        path: Database file path. Created on first connect if absent.
        create_parents: ``True`` (default) creates the parent directory
            tree if it does not exist — convenient for the
            ``/mnt/data/arista/arista.db`` case where the lab datadrive
            mount-point exists but the project subdirectory may not.
        timeout: SQLite lock-wait timeout in seconds.

    Yields:
        An open :class:`sqlite3.Connection` with foreign-key enforcement
        on and the WAL journal mode active.
    """
    path = Path(path).expanduser()
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()
