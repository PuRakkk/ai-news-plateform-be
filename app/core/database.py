from contextlib import contextmanager
from typing import Generator
import os

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.core.config import settings

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}",
)

engine_kwargs = {"echo": False}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 50,
            "max_overflow": 20,
        }
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session: Session = SessionLocal()
    try:
        yield session
        if session.is_active:
            session.commit()
    except Exception:
        if session.is_active:
            session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize database connection.
    Schema migrations are managed by Alembic; do not call SQLModel.metadata.create_all().
    """
    pass
