"""
Database connection utilities.
Based on ygbis database patterns.
"""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from scripts.core.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling
# pool_pre_ping=True verifies connections before using them
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session factory for ORM operations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections (ygbis pattern).
    Ensures connection is closed after use.

    Example:
        from core.db import get_db_connection
        from sqlalchemy import text

        with get_db_connection() as conn:
            result = conn.execute(text("SELECT 1"))
            print(result.scalar())
    """
    conn = None
    try:
        conn = engine.connect()
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_session():
    """
    Context manager for database sessions (ORM).
    Ensures session is properly closed/committed.

    Example:
        from core.db import get_db_session
        from models.document import Document

        with get_db_session() as session:
            documents = session.query(Document).limit(10).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection() -> bool:
    """
    Test database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def execute_sql(query: str, params: dict = None) -> list:
    """
    Execute SQL query and return results.

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        List of result rows

    Example:
        results = execute_sql("SELECT * FROM documents LIMIT 10")
    """
    with get_db_connection() as conn:
        result = conn.execute(text(query), params or {})
        return result.fetchall()


def execute_sql_write(query: str, params: dict = None) -> int:
    """
    Execute SQL write operation (INSERT, UPDATE, DELETE).

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        Number of rows affected

    Example:
        rows_affected = execute_sql_write(
            "UPDATE documents SET updated_at = NOW() WHERE id = :id",
            {"id": doc_id}
        )
    """
    with get_db_connection() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result.rowcount
