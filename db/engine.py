"""Database engine setup and session management."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

# Allow override via environment variable for testing
DB_PATH = os.environ.get("PLANNER_DB_PATH", "planner.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


# Enable SQLite foreign key enforcement
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce foreign key constraints in SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all database tables if they don't exist."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager providing a transactional database session.

    Automatically commits on success and rolls back on error.

    Yields:
        Session: An active SQLAlchemy session.

    Raises:
        Exception: Re-raises any exception after rolling back.
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
