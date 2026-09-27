# Multi-User Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Add user accounts with JWT authentication so multiple users can maintain independent SRS progress on the same instance.

**Architecture:** New `User` model + `backend/auth.py` for JWT auth. Add `user_id` FK to `SrsItem`, `Setting`, `LevelEvent`, `UserSynonym`. All non-auth routes get a `get_current_user` dependency that decodes the JWT and filters queries by user. Frontend gets auth context, login/register pages, and protected routes.

**Tech Stack:** `python-jose[cryptography]` + `passlib[bcrypt]` for JWT/hashing, FastAPI `OAuth2PasswordBearer`, React context for auth state, localStorage for token.

---

### Task 1: Install backend dependencies (SERIAL — everything depends on this)

**Files:**
- Modify: `backend/` (pip install)

**Step 1: Install packages**

```bash
pip install "python-jose[cryptography]" "passlib[bcrypt]"
```

**Step 2: Verify imports work**

```bash
PYTHONPATH="" python -c "from jose import jwt; from passlib.context import CryptContext; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: add python-jose and passlib dependencies for JWT auth"
```

---

### Task 2: Add User model to models.py (SERIAL — Tasks 3-7 depend on this)

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_user_model(db):
    from backend.models import User
    user = User(username="alice", password_hash="fakehash", created_at=1000000.0)
    db.add(user)
    db.commit()
    row = db.query(User).filter_by(username="alice").first()
    assert row is not None
    assert row.username == "alice"
    assert row.password_hash == "fakehash"
    assert row.created_at == 1000000.0


def test_user_username_unique(db):
    from backend.models import User
    from sqlalchemy.exc import IntegrityError
    import pytest
    db.add(User(username="bob", password_hash="h1", created_at=1.0))
    db.commit()
    db.add(User(username="bob", password_hash="h2", created_at=2.0))
    with pytest.raises(IntegrityError):
        db.commit()
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_models.py::test_user_model -v
```

Expected: FAIL — `ImportError: cannot import name 'User'`

**Step 3: Write the User model**

Add to `backend/models.py` (after existing imports, before `Subject`):

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)
```

**Step 4: Run tests to verify they pass**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_models.py::test_user_model backend/tests/test_models.py::test_user_username_unique -v
```

Expected: 2 PASS

**Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_models.py
git commit -m "feat: add User model with username and password_hash"
```

---

### Task 3: Create auth.py — password hashing, JWT, get_current_user (SERIAL — Task 4 depends on this)

**Files:**
- Create: `backend/auth.py`
- Create: `backend/tests/test_auth.py`

**Step 1: Write failing tests**

Create `backend/tests/test_auth.py`:

```python
import time
import pytest
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.models import User
from fastapi import HTTPException


def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_decode_token(db):
    user = User(username="testuser", password_hash=hash_password("pw"), created_at=time.time())
    db.add(user)
    db.commit()

    token = create_access_token(user.id, user.username)
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3  # JWT has 3 parts


def test_get_current_user_valid_token(db):
    user = User(username="testuser", password_hash=hash_password("pw"), created_at=time.time())
    db.add(user)
    db.commit()

    token = create_access_token(user.id, user.username)
    result = get_current_user(token=token, db=db)
    assert result.id == user.id
    assert result.username == "testuser"


def test_get_current_user_invalid_token(db):
    with pytest.raises(HTTPException) as exc:
        get_current_user(token="invalid.token.here", db=db)
    assert exc.value.status_code == 401


def test_get_current_user_nonexistent_user(db):
    token = create_access_token(9999, "ghost")
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=db)
    assert exc.value.status_code == 401
```

**Step 2: Run to verify failure**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_auth.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.auth'`

**Step 3: Create `backend/auth.py`**

```python
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.database import get_db, PROJECT_ROOT
from backend.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SECRET_FILE = PROJECT_ROOT / "data" / ".jwt_secret"
if SECRET_FILE.exists():
    SECRET_KEY = SECRET_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(SECRET_KEY)

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

**Step 4: Run tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_auth.py -v
```

Expected: 5 PASS

**Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat: add auth module with password hashing, JWT creation, and get_current_user"
```

---

### Task 4: Create auth routes — register, login, me (SERIAL — needed before route updates)

**Files:**
- Create: `backend/routes/auth.py`
- Modify: `backend/main.py` (register router)
- Create: `backend/tests/test_auth_routes.py`

**Step 1: Write failing tests**

Create `backend/tests/test_auth_routes.py`:

```python
import time
from backend.models import User
from backend.auth import hash_password


def test_register_creates_user(client, db):
    resp = client.post("/api/auth/register", json={"username": "newuser", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["username"] == "newuser"
    user = db.query(User).filter_by(username="newuser").first()
    assert user is not None


def test_register_duplicate_username(client, db):
    client.post("/api/auth/register", json={"username": "dup", "password": "pass123"})
    resp = client.post("/api/auth/register", json={"username": "dup", "password": "other"})
    assert resp.status_code == 409


def test_login_valid_credentials(client, db):
    user = User(username="loginuser", password_hash=hash_password("mypass"), created_at=time.time())
    db.add(user)
    db.commit()
    resp = client.post("/api/auth/login", json={"username": "loginuser", "password": "mypass"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password(client, db):
    user = User(username="loginuser2", password_hash=hash_password("correct"), created_at=time.time())
    db.add(user)
    db.commit()
    resp = client.post("/api/auth/login", json={"username": "loginuser2", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


def test_me_returns_current_user(client, db):
    resp = client.post("/api/auth/register", json={"username": "meuser", "password": "pass"})
    token = resp.json()["token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "meuser"


def test_me_without_token(db):
    from fastapi.testclient import TestClient
    from backend.main import app
    raw_client = TestClient(app)
    resp = raw_client.get("/api/auth/me")
    assert resp.status_code == 401
```

**Step 2: Run to verify failure**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_auth_routes.py -v
```

Expected: FAIL

**Step 3: Create `backend/routes/auth.py`**

```python
import json
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Setting
from backend.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth")

SETTING_DEFAULTS = {
    "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
    "lesson_batch_size": 5,
    "jlpt_gating": True,
    "dependency_gating": True,
    "max_reviews_per_session": None,
}


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(req: AuthRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(username=req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        created_at=time.time(),
    )
    db.add(user)
    db.flush()
    for k, v in SETTING_DEFAULTS.items():
        db.add(Setting(user_id=user.id, key=k, value=json.dumps(v)))
    db.commit()
    token = create_access_token(user.id, user.username)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.username)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}
```

**Step 4: Register the auth router in `backend/main.py`**

Add import at line 8:
```python
from backend.routes import settings, subjects, lessons, reviews, stats, levels, extra_study, auth
```

Add router registration after line 11 (before other routers):
```python
app.include_router(auth.router, prefix="/api")
```

**Step 5: Run tests**

Note: The auth route tests will initially fail because `Setting` now needs `user_id` but the model hasn't been updated yet. The register endpoint creates Settings with `user_id=user.id`, but the model still has `key` as sole PK. We need to update models first. **However**, the tests for login/me/duplicate should pass. The register test and any test that creates Settings will fail until Task 5.

For now, skip the register test and verify the route structure:

```bash
PYTHONPATH="" python -m pytest backend/tests/test_auth_routes.py::test_login_nonexistent_user backend/tests/test_auth_routes.py::test_me_without_token -v
```

Expected: 2 PASS

**Step 6: Commit (partial — auth routes scaffolded)**

```bash
git add backend/routes/auth.py backend/main.py backend/tests/test_auth_routes.py
git commit -m "feat: add auth routes for register, login, and me"
```

---

### Task 5: Update models — add user_id to SrsItem, Setting, LevelEvent, UserSynonym (SERIAL — all route changes depend on this)

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_models.py`

**Step 1: Update models.py**

The `Subject` and `SubjectDependency` models stay unchanged.

Update `SrsItem`:
```python
class SrsItem(Base):
    __tablename__ = "srs_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    srs_stage = Column(Integer, nullable=False, default=0)
    unlocked_at = Column(Float, nullable=True)
    started_at = Column(Float, nullable=True)
    next_review_at = Column(Float, nullable=True)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    meaning_correct_in_session = Column(Integer, default=0)
    reading_correct_in_session = Column(Integer, default=0)
    last_incorrect_at = Column(Float, nullable=True)
    incorrect_in_session = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="srs_item")
    user = relationship("User")

    __table_args__ = (UniqueConstraint("user_id", "subject_id"),)
```

Remove `unique=True` from the old `subject_id` column (the UniqueConstraint now handles it as a composite).

Update `Setting`:
```python
class Setting(Base):
    __tablename__ = "settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
```

Update `LevelEvent`:
```python
class LevelEvent(Base):
    __tablename__ = "level_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    level = Column(Integer, nullable=False)
    reached_at = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "level"),)
```

Remove the old `unique=True` from `level` column.

Update `UserSynonym`:
```python
class UserSynonym(Base):
    __tablename__ = "user_synonyms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    meaning = Column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "subject_id", "meaning"),)
```

Add the `UniqueConstraint` import at the top of `models.py`:
```python
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, UniqueConstraint
```

**Important:** The `Subject.srs_item` back_populates relationship needs updating — with multi-user, a Subject can have multiple SrsItems (one per user). Change the `Subject` model's relationship:
```python
srs_item = relationship("SrsItem", back_populates="subject", uselist=False, viewonly=True)
```

Note: `uselist=False` still works for the relationship definition, but queries that use `Subject.srs_item` via join will need to be aware they might get any user's item. The routes will query SrsItem directly with `user_id` filter instead of relying on this relationship. The `viewonly=True` prevents accidental writes via the relationship.

**Step 2: Update test conftest.py to provide a test_user fixture and update client**

Replace `backend/tests/conftest.py`:

```python
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
```

Key change: `client` now depends on `test_user` and automatically includes an auth header. All existing tests that use `client` will get an authenticated client.

**Step 3: Update test_models.py**

Every `SrsItem(...)`, `Setting(...)`, `LevelEvent(...)`, and `UserSynonym(...)` creation needs `user_id`. Update test_models.py to use the `test_user` fixture:

In each test function that creates these models, add `test_user` as a parameter and pass `user_id=test_user.id`.

Example — change `test_srs_item_creation(db)` to `test_srs_item_creation(db, test_user)` and add `user_id=test_user.id` to the SrsItem constructor. Do the same for Setting, LevelEvent, UserSynonym tests.

**Step 4: Run model tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_models.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add backend/models.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat: add user_id FK to SrsItem, Setting, LevelEvent, UserSynonym"
```

---

### Task 6: Update all test files to pass user_id (SERIAL — must pass before route changes)

**Files:**
- Modify: all 16 test files in `backend/tests/`

Every test that creates `SrsItem`, `Setting`, `LevelEvent`, or `UserSynonym` needs `user_id=test_user.id`. This is mechanical — add `test_user` to the fixture parameters and add the `user_id` field.

**Pattern for each test file:**

1. Any test function using `db` that creates SrsItem/Setting/LevelEvent/UserSynonym → add `test_user` parameter
2. Any `_seed(db)` helper → change to `_seed(db, test_user)` and propagate `user_id=test_user.id`
3. Any test function calling `_seed(db)` → change to `_seed(db, test_user)` and add `test_user` param

**Files and specific changes:**

| File | What to change |
|------|----------------|
| `test_review_routes.py` | `_seed(db)` → `_seed(db, user)`: add `user_id=user.id` to SrsItem + Setting. `_seed_with_kunyomi` same. Tests add `test_user` param, pass to `_seed`. |
| `test_lesson_routes.py` | `_seed(db)` → `_seed(db, user)`: add `user_id=user.id` to all SrsItem + Setting. All 5 test functions get `test_user`. |
| `test_settings_routes.py` | Setting creation needs `user_id=test_user.id`. |
| `test_stats_routes.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_level_routes.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_level_history.py` | SrsItem + LevelEvent creation needs `user_id=test_user.id`. |
| `test_subject_routes.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_synonym_routes.py` | SrsItem + UserSynonym creation needs `user_id=test_user.id`. |
| `test_critical_items.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_extra_study_routes.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_forecast.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_reset_resurrect.py` | SrsItem creation needs `user_id=test_user.id`. |
| `test_import.py` | Only tests import logic, may not need changes. Check. |
| `test_srs_engine.py` | Pure functions, no DB models. No changes. |
| `test_jlpt_mapping.py` | Pure functions. No changes. |
| `test_auth.py` | Already uses User. No changes needed. |
| `test_auth_routes.py` | Already correct. No changes. |

**Step 1: Update all test files**

For each file, apply the mechanical changes described above.

**Step 2: Run all tests (they will fail — routes not yet updated)**

The tests will fail at this point because the routes don't pass `user_id` in queries yet. That's expected. Verify the test files at least load:

```bash
PYTHONPATH="" python -m pytest backend/tests/test_models.py backend/tests/test_auth.py -v
```

Expected: PASS (these don't hit routes)

**Step 3: Commit test changes**

```bash
git add backend/tests/
git commit -m "test: add user_id to all test model creation for multi-user"
```

---

### Task 7: Update main.py — remove global seed_defaults (SERIAL)

**Files:**
- Modify: `backend/main.py`

**Step 1: Update seed_defaults**

Replace the `seed_defaults` function. It should only call `create_all` now — setting defaults are seeded per-user at registration (already done in `backend/routes/auth.py`):

```python
@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
```

Remove the `import json` at the top if no longer needed, and remove the `Setting` import from `backend.models` if unused.

**Step 2: Verify the app starts**

```bash
PYTHONPATH="" uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/api/auth/login | head -5
kill %1
```

Expected: some JSON response (error is fine — just checking it starts)

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "refactor: remove global seed_defaults, settings now seeded per-user at registration"
```

---

### Task 8: Update settings routes (PARALLEL with Tasks 9-13)

**Files:**
- Modify: `backend/routes/settings.py`

**Step 1: Update routes**

```python
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Setting, User
from backend.auth import get_current_user

router = APIRouter()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Setting).filter_by(user_id=current_user.id).all()
    return {row.key: json.loads(row.value) for row in rows}


@router.put("/settings")
def update_settings(updates: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    for key, value in updates.items():
        setting = db.query(Setting).filter_by(user_id=current_user.id, key=key).first()
        if setting:
            setting.value = json.dumps(value)
    db.commit()
    return get_settings(db=db, current_user=current_user)
```

**Step 2: Run settings tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_settings_routes.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add backend/routes/settings.py
git commit -m "feat: scope settings routes to current user"
```

---

### Task 9: Update reviews routes (PARALLEL with Tasks 8, 10-13)

**Files:**
- Modify: `backend/routes/reviews.py`

**Step 1: Add auth imports and update `_get_intervals`**

Add imports:
```python
from backend.models import Subject, SrsItem, Setting, UserSynonym, SubjectDependency, LevelEvent, User
from backend.auth import get_current_user
```

Update `_get_intervals` to take user_id:
```python
def _get_intervals(db: Session, user_id: int) -> list:
    row = db.query(Setting).filter_by(user_id=user_id, key="srs_intervals").first()
    return json.loads(row.value) if row else DEFAULT_INTERVALS
```

**Step 2: Update `get_reviews` (line 30)**

Add `current_user: User = Depends(get_current_user)` parameter.

Add `.filter(SrsItem.user_id == current_user.id)` to the main query.

Update the UserSynonym query to also filter by `user_id`:
```python
synonyms = [{"id": syn.id, "meaning": syn.meaning}
             for syn in db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=s.id).all()]
```

**Step 3: Update `submit_review` (line 78)**

Add `current_user: User = Depends(get_current_user)` parameter.

Change SrsItem lookup:
```python
item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
```

Change UserSynonym lookup:
```python
user_syns = [s.meaning for s in db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=subject_id).all()]
```

Change `_get_intervals` call:
```python
intervals = _get_intervals(db, current_user.id)
```

Change `compute_current_level` call — this function also needs user_id (see Task 11):
```python
current_level = compute_current_level(db, current_user.id)
```

Change LevelEvent queries:
```python
max_recorded = db.query(func.max(LevelEvent.level)).filter_by(user_id=current_user.id).scalar() or 0
```
```python
db.add(LevelEvent(user_id=current_user.id, level=current_level, reached_at=time.time()))
```

**Step 4: Run review tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_review_routes.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/routes/reviews.py
git commit -m "feat: scope review routes to current user"
```

---

### Task 10: Update lessons routes (PARALLEL with Tasks 8-9, 11-13)

**Files:**
- Modify: `backend/routes/lessons.py`

**Step 1: Add auth imports**

```python
from backend.models import Subject, SrsItem, Setting, SubjectDependency, User
from backend.auth import get_current_user
```

**Step 2: Update `_get_setting` to take user_id**

```python
def _get_setting(db: Session, user_id: int, key: str, default=None):
    row = db.query(Setting).filter_by(user_id=user_id, key=key).first()
    return json.loads(row.value) if row else default
```

Update `_get_intervals`:
```python
def _get_intervals(db: Session, user_id: int) -> list:
    return _get_setting(db, user_id, "srs_intervals", DEFAULT_INTERVALS)
```

**Step 3: Update `get_lessons`**

Add `current_user: User = Depends(get_current_user)` parameter.

Pass `current_user.id` to all `_get_setting` calls:
```python
batch_size = _get_setting(db, current_user.id, "lesson_batch_size", 5)
dep_gating = _get_setting(db, current_user.id, "dependency_gating", False)
jlpt_gating = _get_setting(db, current_user.id, "jlpt_gating", False)
```

Add user_id filter to main query:
```python
query = (
    db.query(SrsItem)
    .join(Subject)
    .filter(SrsItem.user_id == current_user.id)
    .filter(SrsItem.srs_stage == 0)
)
```

The dependency gating subquery also needs the user_id filter — the subquery joins SrsItem to check component stages, and those SrsItems must belong to the current user:
```python
if dep_gating:
    blocked_ids = (
        db.query(SubjectDependency.subject_id)
        .join(SrsItem, SrsItem.subject_id == SubjectDependency.component_id)
        .filter(SrsItem.user_id == current_user.id)
        .group_by(SubjectDependency.subject_id)
        .having(func.min(SrsItem.srs_stage) < 5)
        .subquery()
    )
    query = query.filter(~SrsItem.subject_id.in_(db.query(blocked_ids)))
```

The JLPT gating call to `compute_current_level` needs user_id:
```python
current_level = compute_current_level(db, current_user.id)
```

**Step 4: Update `start_lessons`**

Add `current_user: User = Depends(get_current_user)` parameter.

Update `_get_intervals` call:
```python
intervals = _get_intervals(db, current_user.id)
```

Update SrsItem lookup to filter by user:
```python
item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=sid, srs_stage=0).first()
```

**Step 5: Run tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_lesson_routes.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/routes/lessons.py
git commit -m "feat: scope lesson routes to current user"
```

---

### Task 11: Update levels routes (PARALLEL with Tasks 8-10, 12-13)

**Files:**
- Modify: `backend/routes/levels.py`

**Step 1: Add auth imports**

```python
from backend.models import Subject, SrsItem, User
from backend.auth import get_current_user
```

**Step 2: Update `compute_current_level` to accept user_id**

This function is called by `reviews.py` and `lessons.py` too, so its signature change affects those (already handled in Tasks 9-10).

```python
def compute_current_level(db: Session, user_id: int) -> int:
    rows = (
        db.query(
            Subject.level,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == user_id))
        .filter(Subject.type == "kanji")
        .group_by(Subject.level)
        .all()
    )
    level_map = {r.level: (r.total, r.passed or 0) for r in rows}
    current = 1
    for lvl in range(1, 61):
        if lvl not in level_map:
            break
        total, passed = level_map[lvl]
        if total > 0 and passed / total >= 0.9:
            current = lvl + 1
        else:
            break
    return min(current, 60)
```

Key change: `outerjoin(SrsItem)` becomes `outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == user_id))` to only join the current user's SrsItems. Without this, other users' progress would affect level computation.

**Step 3: Update `get_levels`**

```python
@router.get("/levels")
def get_levels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current = compute_current_level(db, current_user.id)
    rows = (
        db.query(
            Subject.level,
            Subject.type,
            func.count(Subject.id).label("count"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))
        .group_by(Subject.level, Subject.type)
        .all()
    )
    # ... rest unchanged ...
```

**Step 4: Update `get_level_detail`**

```python
@router.get("/levels/{level}")
def get_level_detail(level: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subjects = (
        db.query(Subject)
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))
        .filter(Subject.level == level)
        .all()
    )
```

The `s.srs_item` access at line 85 is problematic with multi-user — the relationship may return the wrong user's SrsItem. Instead, query SrsItem separately:

```python
    srs_map = {
        item.subject_id: item.srs_stage
        for item in db.query(SrsItem).filter(
            SrsItem.user_id == current_user.id,
            SrsItem.subject_id.in_([s.id for s in subjects])
        ).all()
    }
    result = {"level": level, "radicals": [], "kanji": [], "vocabulary": []}
    for s in subjects:
        item = {
            "id": s.id,
            "characters": s.characters,
            "type": s.type,
            "meanings": json.loads(s.meanings) if s.meanings else [],
            "srs_stage": srs_map.get(s.id, 0),
        }
        # ... rest unchanged (if/elif/else for type) ...
```

**Step 5: Run tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_level_routes.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/routes/levels.py
git commit -m "feat: scope level routes and compute_current_level to current user"
```

---

### Task 12: Update stats routes (PARALLEL with Tasks 8-11, 13)

**Files:**
- Modify: `backend/routes/stats.py`

**Step 1: Add auth imports**

```python
from backend.models import Subject, SrsItem, LevelEvent, User
from backend.auth import get_current_user
```

**Step 2: Update `get_summary`**

Add `current_user: User = Depends(get_current_user)` parameter.

Add `.filter(SrsItem.user_id == current_user.id)` to every SrsItem query:

- `reviews_available` count (line 18-23): add `SrsItem.user_id == current_user.id`
- `next_review` (line 25-30): add `SrsItem.user_id == current_user.id`
- `lessons_available` (line 32-36): add `SrsItem.user_id == current_user.id`
- `stage_counts` (line 38-41): add `.filter(SrsItem.user_id == current_user.id)` before `.group_by`
- JLPT burned count (line 51-56): add `SrsItem.user_id == current_user.id` to the filter
- `level_rows` (line 59-69): change `.outerjoin(SrsItem)` to `.outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))`
- `progress_rows` (line 82-92): same outerjoin change

**Step 3: Update `get_forecast`**

Add `current_user` param. Add `SrsItem.user_id == current_user.id` filter.

**Step 4: Update `get_critical_items`**

Add `current_user` param. Add `SrsItem.user_id == current_user.id` filter.

**Step 5: Update `get_recently_unlocked`**

Add `current_user` param. Add `SrsItem.user_id == current_user.id` filter.

**Step 6: Update `get_level_history`**

Add `current_user` param. Filter by `user_id`:
```python
events = db.query(LevelEvent).filter_by(user_id=current_user.id).order_by(LevelEvent.level.asc()).all()
```

**Step 7: Run tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_stats_routes.py backend/tests/test_forecast.py backend/tests/test_critical_items.py backend/tests/test_level_history.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/routes/stats.py
git commit -m "feat: scope stats routes to current user"
```

---

### Task 13: Update subjects and extra_study routes (PARALLEL with Tasks 8-12)

**Files:**
- Modify: `backend/routes/subjects.py`
- Modify: `backend/routes/extra_study.py`

#### subjects.py

**Step 1: Add auth imports**

```python
from backend.models import Subject, SubjectDependency, SrsItem, UserSynonym, User
from backend.auth import get_current_user
```

**Step 2: `list_subjects` — NO CHANGE needed**

This reads Subject table only. No user-specific data. However, it does accept an auth token (all routes should require auth). Add `current_user: User = Depends(get_current_user)` but don't use it in the query.

**Step 3: `get_subject` (line 57)**

Add `current_user` param.

Change SrsItem query (line 82):
```python
srs = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
```

Change UserSynonym query (line 90):
```python
synonyms = db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=subject_id).all()
```

**Step 4: `list_synonyms` (line 101)**

Add `current_user` param. Filter by `user_id`:
```python
db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=subject_id).all()
```

**Step 5: `add_synonym` (line 109)**

Add `current_user` param.

Filter duplicate check:
```python
existing = db.query(UserSynonym).filter_by(
    user_id=current_user.id, subject_id=subject_id, meaning=req.meaning
).first()
```

Create with user_id:
```python
syn = UserSynonym(user_id=current_user.id, subject_id=subject_id, meaning=req.meaning)
```

**Step 6: `reset_subject` (line 127)**

Add `current_user` param. Filter SrsItem by user:
```python
item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
```

**Step 7: `resurrect_subject` (line 145)**

Add `current_user` param. Same SrsItem filter.

**Step 8: `delete_synonym` (line 166)**

Add `current_user` param. Filter by user_id:
```python
syn = db.query(UserSynonym).filter_by(id=synonym_id, user_id=current_user.id, subject_id=subject_id).first()
```

#### extra_study.py

**Step 1: Add auth imports**

```python
from backend.models import Subject, SrsItem, User
from backend.auth import get_current_user
```

**Step 2: `extra_study_summary`**

Add `current_user` param. Add `SrsItem.user_id == current_user.id` to all 3 count queries.

**Step 3: `get_extra_study`**

Add `current_user` param. Add `SrsItem.user_id == current_user.id` to all 3 mode queries.

**Step 4: `submit_extra_study`**

Add `current_user` param (for auth enforcement, even though it only reads Subject data).

**Step 5: Run tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_subject_routes.py backend/tests/test_synonym_routes.py backend/tests/test_reset_resurrect.py backend/tests/test_extra_study_routes.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/routes/subjects.py backend/routes/extra_study.py
git commit -m "feat: scope subjects and extra study routes to current user"
```

---

### Task 14: Run all backend tests (SERIAL — gate before frontend)

**Step 1: Run full test suite**

```bash
PYTHONPATH="" python -m pytest backend/tests/ -v
```

Expected: ALL PASS (107+ tests)

**Step 2: Run auth route tests too**

```bash
PYTHONPATH="" python -m pytest backend/tests/test_auth_routes.py -v
```

Expected: ALL PASS

If any fail, fix before proceeding.

---

### Task 15: Create migration script (SERIAL — needed for production DB)

**Files:**
- Create: `backend/migrate_multiuser.py`

**Step 1: Write the migration script**

```python
"""Migrate existing single-user database to multi-user schema.

Usage: PYTHONPATH="" python -m backend.migrate_multiuser

Creates a backup, adds User table, inserts default user 'adhi',
adds user_id columns to srs_items/settings/level_events/user_synonyms,
and recreates tables with proper constraints.
"""

import shutil
import sqlite3
import time
from pathlib import Path

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "kanji-srs.db"
BACKUP_PATH = PROJECT_ROOT / "data" / "kanji-srs.db.backup"


def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}, nothing to migrate.")
        return

    print(f"Backing up {DB_PATH} → {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")

    # 1. Create users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # 2. Insert default user
    password_hash = pwd_context.hash("adhi1234")
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        ("adhi", password_hash, time.time()),
    )
    adhi_id = conn.execute("SELECT id FROM users WHERE username = 'adhi'").fetchone()[0]
    print(f"Created user 'adhi' with id={adhi_id}")

    # 3. Migrate srs_items
    print("Migrating srs_items...")
    conn.execute("ALTER TABLE srs_items ADD COLUMN user_id INTEGER REFERENCES users(id)")
    conn.execute(f"UPDATE srs_items SET user_id = {adhi_id}")

    conn.execute("""
        CREATE TABLE srs_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            srs_stage INTEGER NOT NULL DEFAULT 0,
            unlocked_at REAL,
            started_at REAL,
            next_review_at REAL,
            correct_count INTEGER DEFAULT 0,
            incorrect_count INTEGER DEFAULT 0,
            meaning_correct_in_session INTEGER DEFAULT 0,
            reading_correct_in_session INTEGER DEFAULT 0,
            last_incorrect_at REAL,
            incorrect_in_session INTEGER DEFAULT 0,
            UNIQUE(user_id, subject_id)
        )
    """)
    conn.execute("""
        INSERT INTO srs_items_new (id, user_id, subject_id, srs_stage, unlocked_at, started_at,
            next_review_at, correct_count, incorrect_count, meaning_correct_in_session,
            reading_correct_in_session, last_incorrect_at, incorrect_in_session)
        SELECT id, user_id, subject_id, srs_stage, unlocked_at, started_at,
            next_review_at, correct_count, incorrect_count, meaning_correct_in_session,
            reading_correct_in_session, last_incorrect_at, incorrect_in_session
        FROM srs_items
    """)
    conn.execute("DROP TABLE srs_items")
    conn.execute("ALTER TABLE srs_items_new RENAME TO srs_items")

    # 4. Migrate settings
    print("Migrating settings...")
    conn.execute("""
        CREATE TABLE settings_new (
            user_id INTEGER NOT NULL REFERENCES users(id),
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
    """)
    conn.execute(f"""
        INSERT INTO settings_new (user_id, key, value)
        SELECT {adhi_id}, key, value FROM settings
    """)
    conn.execute("DROP TABLE settings")
    conn.execute("ALTER TABLE settings_new RENAME TO settings")

    # 5. Migrate level_events
    print("Migrating level_events...")
    conn.execute("ALTER TABLE level_events ADD COLUMN user_id INTEGER REFERENCES users(id)")
    conn.execute(f"UPDATE level_events SET user_id = {adhi_id}")

    conn.execute("""
        CREATE TABLE level_events_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            level INTEGER NOT NULL,
            reached_at REAL NOT NULL,
            UNIQUE(user_id, level)
        )
    """)
    conn.execute("""
        INSERT INTO level_events_new (id, user_id, level, reached_at)
        SELECT id, user_id, level, reached_at FROM level_events
    """)
    conn.execute("DROP TABLE level_events")
    conn.execute("ALTER TABLE level_events_new RENAME TO level_events")

    # 6. Migrate user_synonyms
    print("Migrating user_synonyms...")
    conn.execute("ALTER TABLE user_synonyms ADD COLUMN user_id INTEGER REFERENCES users(id)")
    conn.execute(f"UPDATE user_synonyms SET user_id = {adhi_id}")

    conn.execute("""
        CREATE TABLE user_synonyms_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            meaning TEXT NOT NULL,
            UNIQUE(user_id, subject_id, meaning)
        )
    """)
    conn.execute("""
        INSERT INTO user_synonyms_new (id, user_id, subject_id, meaning)
        SELECT id, user_id, subject_id, meaning FROM user_synonyms
    """)
    conn.execute("DROP TABLE user_synonyms")
    conn.execute("ALTER TABLE user_synonyms_new RENAME TO user_synonyms")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
```

**Step 2: Test the migration on a copy (manual verification)**

```bash
cp data/kanji-srs.db /tmp/kanji-srs-test.db
KANJI_SRS_DB=/tmp/kanji-srs-test.db PYTHONPATH="" python -m backend.migrate_multiuser
sqlite3 /tmp/kanji-srs-test.db ".schema users"
sqlite3 /tmp/kanji-srs-test.db "SELECT count(*) FROM srs_items WHERE user_id IS NOT NULL"
sqlite3 /tmp/kanji-srs-test.db "SELECT count(*) FROM settings"
rm /tmp/kanji-srs-test.db
```

Expected: Schema shows `users` table. All srs_items have non-null user_id. Settings exist.

**Step 3: Commit**

```bash
git add backend/migrate_multiuser.py
git commit -m "feat: add migration script to convert single-user DB to multi-user"
```

---

### Task 16: Update frontend api.js — auth header and auth API calls (SERIAL — frontend Tasks 17-18 depend)

**Files:**
- Modify: `frontend/src/api.js`

**Step 1: Update the file**

```javascript
const BASE = '/api';

async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, {
    headers,
    ...options,
  });
  if (resp.status === 401) {
    localStorage.removeItem('token');
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const authApi = {
  login: (username, password) => request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  register: (username, password) => request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  me: () => request('/auth/me'),
};

export const api = {
  getSummary: () => request('/summary'),
  getLessons: () => request('/lessons'),
  startLessons: (ids) => request('/lessons/start', {
    method: 'POST',
    body: JSON.stringify({ subject_ids: ids }),
  }),
  getReviews: () => request('/reviews'),
  submitReview: (subjectId, answerType, answer) => request(`/reviews/${subjectId}`, {
    method: 'POST',
    body: JSON.stringify({ answer_type: answerType, answer }),
  }),
  getSubjects: (params) => request(`/subjects?${new URLSearchParams(params)}`),
  getSubject: (id) => request(`/subjects/${id}`),
  getSettings: () => request('/settings'),
  updateSettings: (updates) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  }),
  getLevels: () => request('/levels'),
  getLevelDetail: (level) => request(`/levels/${level}`),
  getForecast: () => request('/forecast'),
  getExtraStudySummary: () => request('/extra-study/summary'),
  getExtraStudy: (mode) => request(`/extra-study?mode=${mode}`),
  submitExtraStudy: (subjectId, answerType, answer) => request(`/extra-study/${subjectId}`, {
    method: 'POST',
    body: JSON.stringify({ answer_type: answerType, answer }),
  }),
  getCriticalItems: () => request('/critical-items'),
  getSubjectSynonyms: (id) => request(`/subjects/${id}/synonyms`),
  addSubjectSynonym: (id, meaning) => request(`/subjects/${id}/synonyms`, {
    method: 'POST',
    body: JSON.stringify({ meaning }),
  }),
  deleteSubjectSynonym: (subjectId, synonymId) => request(`/subjects/${subjectId}/synonyms/${synonymId}`, {
    method: 'DELETE',
  }),
  getRecentlyUnlocked: () => request('/recently-unlocked'),
  getLevelHistory: () => request('/level-history'),
  resetSubject: (id) => request(`/subjects/${id}/reset`, { method: 'POST' }),
  resurrectSubject: (id) => request(`/subjects/${id}/resurrect`, { method: 'POST' }),
};
```

**Step 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add auth header to API requests and auth API calls"
```

---

### Task 17: Create AuthContext, Login, and Register pages (SERIAL)

**Files:**
- Create: `frontend/src/context/AuthContext.jsx`
- Create: `frontend/src/pages/Login.jsx`
- Create: `frontend/src/pages/Register.jsx`

**Step 1: Create AuthContext**

Create `frontend/src/context/` directory, then `AuthContext.jsx`:

```jsx
import { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      authApi.me()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('token');
          setUser(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    const data = await authApi.login(username, password);
    localStorage.setItem('token', data.token);
    setUser(data.user);
    return data;
  };

  const register = async (username, password) => {
    const data = await authApi.register(username, password);
    localStorage.setItem('token', data.token);
    setUser(data.user);
    return data;
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
```

**Step 2: Create Login.jsx**

```jsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch {
      setError('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Kanji SRS</h1>
        <h2>Log in</h2>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Log in'}
          </button>
        </form>
        <p className="auth-link">
          Don't have an account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}
```

**Step 3: Create Register.jsx**

```jsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters');
      return;
    }
    setLoading(true);
    try {
      await register(username, password);
      navigate('/');
    } catch {
      setError('Username already taken');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Kanji SRS</h1>
        <h2>Create account</h2>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label>
            Confirm password
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Register'}
          </button>
        </form>
        <p className="auth-link">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/context/AuthContext.jsx frontend/src/pages/Login.jsx frontend/src/pages/Register.jsx
git commit -m "feat: add AuthContext, Login, and Register pages"
```

---

### Task 18: Update App.jsx — protected routes, auth in nav (SERIAL)

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css` (add auth page styles)

**Step 1: Update App.jsx**

Add imports:
```javascript
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import { LogOut } from 'lucide-react';
```

Add a `ProtectedRoute` component:
```jsx
function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}
```

Update `AnimatedRoutes` to include login/register as public routes and wrap existing routes:
```jsx
function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={pageTransition}
      >
        <Routes location={location}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/lessons" element={<ProtectedRoute><Lessons /></ProtectedRoute>} />
          <Route path="/reviews" element={<ProtectedRoute><Reviews /></ProtectedRoute>} />
          <Route path="/subjects" element={<ProtectedRoute><Subjects /></ProtectedRoute>} />
          <Route path="/subjects/:id" element={<ProtectedRoute><SubjectDetail /></ProtectedRoute>} />
          <Route path="/levels/:level" element={<ProtectedRoute><LevelDetail /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/extra-study/:mode" element={<ProtectedRoute><ExtraStudy /></ProtectedRoute>} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}
```

Update `Nav` to show username and logout:
```jsx
function Nav() {
  const { user, isAuthenticated, logout } = useAuth();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    api.getSummary().then(setSummary).catch(() => {});
    const interval = setInterval(() => {
      api.getSummary().then(setSummary).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  if (!isAuthenticated) return null;

  // ... rest of nav unchanged, but add logout button at the end of the nav:
```

Add to the end of the `<nav>` element, after `<ul className="nav-links">...</ul>`:
```jsx
<div className="nav-user">
  <span className="nav-username">{user?.username}</span>
  <button className="nav-logout" onClick={logout} title="Log out">
    <LogOut size={15} strokeWidth={2.2} />
  </button>
</div>
```

Wrap the `App` component's BrowserRouter children in `AuthProvider`:
```jsx
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster ... />
        <Nav />
        <main className="main">
          <AnimatedRoutes />
        </main>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

**Step 2: Add auth styles to App.css**

Append to `frontend/src/App.css`:

```css
/* Auth pages */
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
}

.auth-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 2rem;
  width: 100%;
  max-width: 360px;
}

.auth-card h1 {
  text-align: center;
  font-size: 1.4rem;
  margin-bottom: 0.25rem;
}

.auth-card h2 {
  text-align: center;
  font-size: 1rem;
  font-weight: 400;
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}

.auth-card form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.auth-card label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.auth-card input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.95rem;
  background: var(--bg);
  color: var(--text-primary);
}

.auth-card button[type="submit"] {
  padding: 0.6rem;
  border: none;
  border-radius: 6px;
  background: var(--accent);
  color: white;
  font-weight: 600;
  cursor: pointer;
  margin-top: 0.5rem;
}

.auth-card button[type="submit"]:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.auth-error {
  color: #e11;
  font-size: 0.85rem;
  margin: 0;
}

.auth-link {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: 1rem;
}

.auth-link a {
  color: var(--accent);
}

/* Nav user section */
.nav-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.nav-username {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.nav-logout {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
}

.nav-logout:hover {
  color: var(--text-primary);
}
```

**Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add protected routes, auth nav with username and logout"
```

---

### Task 19: End-to-end verification (SERIAL — final gate)

**Step 1: Run all backend tests**

```bash
PYTHONPATH="" python -m pytest backend/tests/ -v
```

Expected: ALL PASS

**Step 2: Run the migration on production DB**

```bash
PYTHONPATH="" python -m backend.migrate_multiuser
```

Expected: "Migration complete!" with backup created.

**Step 3: Build frontend and start the app**

```bash
cd frontend && npm run build && cd ..
PYTHONPATH="" uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Step 4: Manual verification checklist**

- [ ] Navigating to `/` redirects to `/login` when not logged in
- [ ] Log in as `adhi` / `adhi1234` — should see existing SRS progress
- [ ] Nav shows username "adhi" and logout button
- [ ] All pages (Dashboard, Lessons, Reviews, Subjects, Settings) work as before
- [ ] Log out — redirects to `/login`
- [ ] Register a new user — starts with empty SRS progress
- [ ] New user's settings page shows defaults
- [ ] Switch between users — each sees only their own data

**Step 5: Update CLAUDE.md**

Update the "Single user" line in Key Design Decisions to reflect multi-user, and update the Running section with migration instructions.

**Step 6: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for multi-user support"
```
