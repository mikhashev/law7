"""
Tests for PostgreSQL client (scripts/core/db.py)
"""

import pytest
from unittest.mock import MagicMock, patch, call, ANY
from sqlalchemy import text

from scripts.core.db import (
    get_db_connection,
    get_db_session,
    check_db_connection,
    execute_sql,
    execute_sql_write,
    engine,
    SessionLocal,
)


class TestGetDbConnection:
    """Tests for get_db_connection context manager."""

    @patch("scripts.core.db.engine")
    def test_connection_yields_connection(self, mock_engine):
        """Test that connection context manager yields a connection."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with get_db_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_called_once()

    @patch("scripts.core.db.engine")
    def test_connection_closes_on_success(self, mock_engine):
        """Test that connection is closed after successful block."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with get_db_connection() as conn:
            pass

        mock_conn.close.assert_called_once()

    @patch("scripts.core.db.engine")
    def test_connection_closes_on_exception(self, mock_engine):
        """Test that connection is closed even if exception occurs."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with pytest.raises(ValueError):
            with get_db_connection() as conn:
                raise ValueError("Test error")

        mock_conn.close.assert_called_once()

    @patch("scripts.core.db.engine")
    def test_connection_handles_none_connection(self, mock_engine):
        """Test that context manager handles None connection gracefully."""
        mock_engine.connect.return_value = None

        # Should not raise exception
        with get_db_connection() as conn:
            assert conn is None


class TestGetDbSession:
    """Tests for get_db_session context manager."""

    @patch("scripts.core.db.SessionLocal")
    def test_session_yields_session(self, mock_session_local):
        """Test that session context manager yields a session."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with get_db_session() as session:
            assert session == mock_session

        mock_session.close.assert_called_once()

    @patch("scripts.core.db.SessionLocal")
    def test_session_commits_on_success(self, mock_session_local):
        """Test that session is committed after successful block."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with get_db_session() as session:
            pass

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("scripts.core.db.SessionLocal")
    def test_session_rollbacks_on_exception(self, mock_session_local):
        """Test that session is rolled back on exception."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with pytest.raises(ValueError):
            with get_db_session() as session:
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("scripts.core.db.SessionLocal")
    def test_session_closes_after_exception(self, mock_session_local):
        """Test that session is closed even after rollback."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with pytest.raises(ValueError):
            with get_db_session() as session:
                raise ValueError("Test error")

        # Should be closed after rollback
        mock_session.close.assert_called_once()


class TestCheckDbConnection:
    """Tests for check_db_connection function."""

    @patch("scripts.core.db.get_db_connection")
    @patch("scripts.core.db.logger")
    def test_check_connection_success(self, mock_logger, mock_get_conn):
        """Test successful connection check."""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = check_db_connection()

        assert result is True
        mock_conn.execute.assert_called_once()
        mock_logger.info.assert_called_once()

    @patch("scripts.core.db.get_db_connection")
    @patch("scripts.core.db.logger")
    def test_check_connection_failure(self, mock_logger, mock_get_conn):
        """Test failed connection check."""
        mock_get_conn.side_effect = Exception("Connection failed")

        result = check_db_connection()

        assert result is False
        mock_logger.error.assert_called_once()

    @patch("scripts.core.db.get_db_connection")
    @patch("scripts.core.db.logger")
    def test_check_connection_execute_error(self, mock_logger, mock_get_conn):
        """Test connection check when execute fails."""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("Execute failed")

        result = check_db_connection()

        assert result is False
        mock_logger.error.assert_called_once()


class TestExecuteSql:
    """Tests for execute_sql function."""

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_returns_results(self, mock_get_conn):
        """Test that execute_sql returns query results."""
        # Mock result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row1",), ("row2",)]
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "SELECT * FROM documents LIMIT 2"
        results = execute_sql(query)

        assert results == [("row1",), ("row2",)]
        mock_conn.execute.assert_called_once()
        # Check that execute was called with any TextClause and empty params
        assert mock_conn.execute.call_args[0][0].text == query
        assert mock_conn.execute.call_args[0][1] == {}

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_with_params(self, mock_get_conn):
        """Test execute_sql with query parameters."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("result",)]
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "SELECT * FROM documents WHERE id = :id"
        params = {"id": "123"}
        results = execute_sql(query, params)

        assert results == [("result",)]
        mock_conn.execute.assert_called_once()
        # Check the query text and params
        assert mock_conn.execute.call_args[0][0].text == query
        assert mock_conn.execute.call_args[0][1] == params

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_returns_empty_list(self, mock_get_conn):
        """Test execute_sql returns empty list when no results."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "SELECT * FROM documents WHERE id = :id"
        results = execute_sql(query, {"id": "nonexistent"})

        assert results == []

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_default_params(self, mock_get_conn):
        """Test execute_sql uses empty dict when params not provided."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "SELECT 1"
        execute_sql(query)

        # Should call with empty dict
        mock_conn.execute.assert_called_once()
        assert mock_conn.execute.call_args[0][0].text == query
        assert mock_conn.execute.call_args[0][1] == {}


class TestExecuteSqlWrite:
    """Tests for execute_sql_write function."""

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_write_returns_rowcount(self, mock_get_conn):
        """Test that execute_sql_write returns number of affected rows."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "UPDATE documents SET updated_at = NOW()"
        rows_affected = execute_sql_write(query)

        assert rows_affected == 5
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_write_with_params(self, mock_get_conn):
        """Test execute_sql_write with query parameters."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "UPDATE documents SET title = :title WHERE id = :id"
        params = {"title": "New Title", "id": "123"}
        rows_affected = execute_sql_write(query, params)

        assert rows_affected == 1
        mock_conn.execute.assert_called_once()
        # Check the query text and params
        assert mock_conn.execute.call_args[0][0].text == query
        assert mock_conn.execute.call_args[0][1] == params
        mock_conn.commit.assert_called_once()

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_write_commits(self, mock_get_conn):
        """Test that execute_sql_write commits transaction."""
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "INSERT INTO documents (id) VALUES (:id)"
        execute_sql_write(query, {"id": "test"})

        mock_conn.commit.assert_called_once()

    @patch("scripts.core.db.get_db_connection")
    def test_execute_sql_write_delete_operation(self, mock_get_conn):
        """Test execute_sql_write with DELETE statement."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        query = "DELETE FROM documents WHERE country_id = :country_id"
        rows_affected = execute_sql_write(query, {"country_id": 999})

        assert rows_affected == 3
        mock_conn.execute.assert_called_once()
        # Check the query text and params
        assert mock_conn.execute.call_args[0][0].text == query
        assert mock_conn.execute.call_args[0][1] == {"country_id": 999}
        mock_conn.commit.assert_called_once()
