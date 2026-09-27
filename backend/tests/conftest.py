import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.models import Subject, SubjectDependency, SrsItem, Setting, UserSynonym, LevelEvent, User  # noqa: F401
from backend.auth import hash_password, create_access_token
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


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_user(db):
    user = User(username="testuser", password_hash=hash_password("testpass"), created_at=time.time())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(test_user):
    from fastapi.testclient import TestClient
    token = create_access_token(test_user.id, test_user.username)
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {token}"
    return c
