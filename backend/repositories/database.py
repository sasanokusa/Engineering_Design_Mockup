from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings
from backend.models.db import Base


@lru_cache
def get_engine():
    settings = get_settings()
    settings.ensure_storage_directories()
    connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
    return create_engine(settings.resolved_database_url, connect_args=connect_args)


@lru_cache
def get_sessionmaker():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            _ensure_sqlite_column(
                connection,
                table_name="documents",
                column_name="session_id",
                definition="INTEGER",
            )
            _ensure_sqlite_column(
                connection,
                table_name="documents",
                column_name="external_session_id",
                definition="VARCHAR(255)",
            )
            _ensure_sqlite_column(
                connection,
                table_name="document_comparisons",
                column_name="granularity",
                definition="VARCHAR(30) DEFAULT 'chunk'",
            )
            connection.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
                    USING fts5(
                        chunk_id UNINDEXED,
                        document_id UNINDEXED,
                        collection_id UNINDEXED,
                        text,
                        tokenize='unicode61'
                    )
                    """
                )
            )


def get_db():
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    return get_sessionmaker()()


def reset_database_caches() -> None:
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()


def _ensure_sqlite_column(connection, *, table_name: str, column_name: str, definition: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    }
    if column_name in columns:
        return
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
