import json
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
    for i in range(1, 11):
        db.add(Subject(id=i, type="kanji", characters=chr(0x5B57 + i), slug=f"char{i}", level=1,
                       jlpt_level="N5",
                       meanings=json.dumps([{"meaning": f"Char{i}", "primary": True}]),
                       readings=json.dumps([{"reading": "じ", "primary": True, "type": "onyomi"}])))
        db.add(SrsItem(subject_id=i, srs_stage=0))
    db.add(Setting(key="lesson_batch_size", value=json.dumps(5)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="dependency_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps([0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0])))
    db.commit()
    db.close()


def test_get_lessons_returns_batch():
    resp = client.get("/api/lessons")
    assert resp.status_code == 200
    assert len(resp.json()) == 5


def test_start_lessons_moves_to_stage_1():
    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    resp = client.post("/api/lessons/start", json={"subject_ids": ids})
    assert resp.status_code == 200
    assert resp.json()["started"] == 5

    resp = client.get("/api/lessons")
    new_ids = [item["id"] for item in resp.json()]
    assert not any(i in new_ids for i in ids)
