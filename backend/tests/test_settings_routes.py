import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.models import Setting, Subject, SubjectDependency, SrsItem  # noqa: F401
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
    defaults = {
        "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
        "lesson_batch_size": 5,
        "jlpt_gating": True,
        "dependency_gating": True,
        "max_reviews_per_session": None,
    }
    for k, v in defaults.items():
        db.add(Setting(key=k, value=json.dumps(v)))
    db.commit()
    db.close()


def test_get_settings():
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lesson_batch_size"] == 5
    assert data["jlpt_gating"] is True


def test_update_setting():
    resp = client.put("/api/settings", json={"lesson_batch_size": 10})
    assert resp.status_code == 200
    resp = client.get("/api/settings")
    assert resp.json()["lesson_batch_size"] == 10
