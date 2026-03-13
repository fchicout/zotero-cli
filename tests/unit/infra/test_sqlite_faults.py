import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.models import Job
from zotero_cli.infra.sqlite_repo import SqliteJobRepository


@pytest.fixture
def mock_db_path(tmp_path):
    return str(tmp_path / "jobs.sqlite")


def test_init_db_failure(mock_db_path):
    """Test that initialization failures are propagated."""
    with patch("zotero_cli.infra.sqlite_repo.sqlite3.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn

        # Fail on CREATE TABLE
        mock_conn.execute.side_effect = sqlite3.OperationalError("Disk I/O error")

        with pytest.raises(sqlite3.OperationalError, match="Disk I/O error"):
            SqliteJobRepository(mock_db_path)


def test_enqueue_failure(mock_db_path):
    """Test that enqueue failures raise appropriate errors."""
    repo = SqliteJobRepository(mock_db_path)

    with patch.object(repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn

        # Fail on INSERT
        mock_conn.execute.side_effect = sqlite3.IntegrityError("Constraint failed")

        job = Job(item_key="K1", task_type="test", payload={})
        with pytest.raises(sqlite3.IntegrityError, match="Constraint failed"):
            repo.enqueue(job)


def test_enqueue_no_lastrowid(mock_db_path):
    """Test case where cursor.lastrowid is None."""
    repo = SqliteJobRepository(mock_db_path)

    with patch.object(repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.lastrowid = None

        job = Job(item_key="K1", task_type="test", payload={})
        with pytest.raises(sqlite3.Error, match="Failed to retrieve last inserted job ID"):
            repo.enqueue(job)


def test_get_next_pending_transaction_failure(mock_db_path):
    """Test that rollback occurs if transaction fails during get_next_pending."""
    repo = SqliteJobRepository(mock_db_path)

    with patch.object(repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn

        # Setup SELECT
        mock_cursor = MagicMock()
        mock_row = {
            "id": 1,
            "item_key": "K1",
            "task_type": "test",
            "status": "PENDING",
            "attempts": 0,
            "next_retry_at": None,
            "payload": "{}",
            "last_error": None,
        }
        mock_cursor.fetchone.return_value = mock_row

        # side_effect for execute calls inside get_next_pending:
        # 1. BEGIN IMMEDIATE
        # 2. SELECT
        # 3. UPDATE -> Raise Error
        mock_conn.execute.side_effect = [
            MagicMock(),  # BEGIN IMMEDIATE
            mock_cursor,  # SELECT
            sqlite3.OperationalError("Lock error"),  # UPDATE
        ]

        with pytest.raises(sqlite3.OperationalError, match="Lock error"):
            repo.get_next_pending("test")

        # mock_conn.__exit__ is called by the 'with conn' block
        # We verify it was called with an exception (the first argument to __exit__)
        assert mock_conn.__exit__.called
        args, _ = mock_conn.__exit__.call_args
        assert args[0] is sqlite3.OperationalError


def test_update_job_failure(mock_db_path):
    """Test failure during job update."""
    repo = SqliteJobRepository(mock_db_path)
    job = Job(id=1, item_key="K1", task_type="test", payload={})

    with patch.object(repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn

        mock_conn.execute.side_effect = sqlite3.OperationalError("DB Locked")

        with pytest.raises(sqlite3.OperationalError, match="DB Locked"):
            repo.update_job(job)
