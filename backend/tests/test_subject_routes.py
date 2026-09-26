import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.models import Subject, SubjectDependency, SrsItem, Setting  # noqa: F401
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
    subjects = [
        Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "One", "primary": True}])),
        Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}])),
        Subject(id=3, type="kanji", characters="人", slug="person", level=2, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Person", "primary": True}]),
                readings=json.dumps([{"reading": "じん", "primary": True, "type": "onyomi"}])),
        Subject(id=4, type="vocabulary", characters="大人", slug="adult", level=3, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Adult", "primary": True}]),
                readings=json.dumps([{"reading": "おとな", "primary": True, "type": "kunyomi"}])),
    ]
    db.add_all(subjects)
    db.add(SubjectDependency(subject_id=2, component_id=1))
    for s in subjects:
        db.add(SrsItem(subject_id=s.id))
    db.commit()
    db.close()


def test_list_subjects():
    resp = client.get("/api/subjects")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 4


def test_filter_by_jlpt():
    resp = client.get("/api/subjects?jlpt=N5")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 4


def test_filter_by_type():
    resp = client.get("/api/subjects?type=kanji")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_search_by_query():
    resp = client.get("/api/subjects?q=big")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["characters"] == "大" for i in items)


def test_get_subject_detail():
    resp = client.get("/api/subjects/2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["characters"] == "大"
    assert len(data["components"]) == 1
    assert data["components"][0]["characters"] == "一"
