import os
from contextlib import contextmanager
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import config
from app.db.models import Base

# Ensure that the database directory exists
def _ensure_db_dir(db_url: str):
    if db_url.startswith("sqlite:///"):
        # For sqlite:///./data/tasks.db, extract path
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

_ensure_db_dir(config.DATABASE_URL)
_ensure_db_dir(config.CHECKPOINTS_DATABASE_URL)

# Create engines
engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database tables."""
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
