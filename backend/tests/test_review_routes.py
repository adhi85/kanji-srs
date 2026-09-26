import json
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.models import Subject, SrsItem, Setting, SubjectDependency  # noqa: F401
from backend.srs_engine import DEFAULT_INTERVALS
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
    s = Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}]),
                meaning_mnemonic="A person stretching wide.")
    db.add(s)
    item = SrsItem(subject_id=1, srs_stage=2, next_review_at=time.time() - 100)
    db.add(item)
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()
    db.close()


def test_get_reviews_returns_due_items():
    resp = client.get("/api/reviews")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["characters"] == "大"


def test_correct_meaning_answer():
    resp = client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "big"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_wrong_meaning_answer():
    resp = client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "small"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is False
    assert resp.json()["correct_answer"] is not None


def test_correct_reading_answer():
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_both_correct_advances_stage():
    client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "big"})
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.json()["new_stage"] == 3


def test_one_wrong_retreats_stage():
    client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "wrong"})
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.json()["new_stage"] == 1
