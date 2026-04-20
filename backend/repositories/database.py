from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings
from backend.models.db import Base


@lru_cache
def get_engine():
    settings = get_settings()
    settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
    return create_engine(settings.resolved_database_url, connect_args=connect_args)


@lru_cache
def get_sessionmaker():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


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

