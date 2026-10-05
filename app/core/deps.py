from typing import Generator
from sqlmodel import Session
from app.core.database import get_session


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a managed database session."""
    with get_session() as session:
        yield session
