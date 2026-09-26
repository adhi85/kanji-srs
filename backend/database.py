import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.environ.get("KANJI_SRS_DB", str(PROJECT_ROOT / "data" / "kanji-srs.db"))

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
