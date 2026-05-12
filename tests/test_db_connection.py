# ─────────────────────────────────────────────────────────────────
#  Tests for arista.db.connection
# ─────────────────────────────────────────────────────────────────
"""DB path resolution + open_db pragma tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from arista.db.connection import open_db, resolve_db_path

# ─────────────────────────────────────────────────────────────────
#  resolve_db_path
# ─────────────────────────────────────────────────────────────────


def test_resolve_db_path_explicit_wins(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARISTA_DB", str(tmp_path / "env.db"))
    monkeypatch.chdir(tmp_path)
    explicit = tmp_path / "flag.db"
    assert resolve_db_path(explicit) == explicit.resolve()


def test_resolve_db_path_env_var(tmp_path: Path, monkeypatch) -> None:
    env_target = tmp_path / "from_env.db"
    monkeypatch.setenv("ARISTA_DB", str(env_target))
    monkeypatch.chdir(tmp_path)
    assert resolve_db_path(None) == env_target.resolve()


def test_resolve_db_path_default_is_cwd_arista(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ARISTA_DB", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_db_path(None) == tmp_path.resolve() / "arista.db"


def test_resolve_db_path_expands_tilde(tmp_path: Path, monkeypatch) -> None:
    # Path.expanduser() reads $HOME on POSIX and %USERPROFILE% on
    # Windows (falling back to %HOMEDRIVE%%HOMEPATH%). Override every
    # variant so this test is cross-platform.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOMEDRIVE", "")
    monkeypatch.setenv("HOMEPATH", "")
    result = resolve_db_path("~/scratch/arista.db")
    assert result == (tmp_path / "scratch" / "arista.db").resolve()


# ─────────────────────────────────────────────────────────────────
#  open_db
# ─────────────────────────────────────────────────────────────────


def test_open_db_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "subdir" / "arista.db"
    assert not target.parent.exists()
    with open_db(target) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
    assert target.exists()
    assert target.parent.is_dir()


def test_open_db_enables_foreign_keys(tmp_path: Path) -> None:
    with open_db(tmp_path / "fk.db") as conn:
        flag = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert flag == 1


def test_open_db_uses_wal_journal(tmp_path: Path) -> None:
    with open_db(tmp_path / "wal.db") as conn:
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal.lower() == "wal"


def test_open_db_closes_on_exit(tmp_path: Path) -> None:
    target = tmp_path / "close.db"
    with open_db(target) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        captured = conn
    with pytest.raises(sqlite3.ProgrammingError):
        captured.execute("SELECT 1")
