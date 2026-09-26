import json
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.models import Subject, SrsItem, Setting, SubjectDependency  # noqa: F401
from backend.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = TestSession()
    db.add(Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(Subject(id=3, type="kanji", characters="人", slug="person", level=11, jlpt_level="N4",
                   meanings=json.dumps([{"meaning": "Person", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.add(SrsItem(subject_id=2, srs_stage=3, next_review_at=time.time() - 100))
    db.add(SrsItem(subject_id=3, srs_stage=9))
    db.commit()
    db.close()


def test_summary_counts():
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviews_available"] == 1
    assert data["lessons_available"] == 1


def test_summary_srs_stage_counts():
    resp = client.get("/api/summary")
    data = resp.json()
    counts = data["srs_stage_counts"]
    assert counts["0"] == 1
    assert counts["3"] == 1
    assert counts["9"] == 1


def test_summary_jlpt_progress():
    resp = client.get("/api/summary")
    data = resp.json()
    progress = data["jlpt_progress"]
    assert "N5" in progress
    assert progress["N5"]["total"] == 2
    assert progress["N5"]["burned"] == 0
    assert progress["N4"]["burned"] == 1
