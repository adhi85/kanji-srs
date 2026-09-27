# Multi-User Support — Agent Specification

## Requirements

- Add `User` model with username (unique) and bcrypt password hash
- JWT authentication (30-day expiry, HS256, secret from `data/.jwt_secret`)
- Auth endpoints: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- Add `user_id` FK to: `SrsItem`, `UserSynonym`, `LevelEvent`, `Setting`
- All non-auth API endpoints require valid JWT via `Authorization: Bearer` header
- Per-user settings seeded at registration time
- SrsItems created lazily per-user (on lesson start)
- Frontend: auth context, login/register pages, protected routes, token in localStorage
- Migration script to backfill existing data to user `adhi` (password: `adhi1234`)

## Constraints

- SQLite: `ALTER TABLE ADD COLUMN` works, but no `ALTER COLUMN` or `DROP COLUMN`. Migration must work within these limits.
- Keep `Subject` and `SubjectDependency` tables unchanged — shared reference data.
- Python 3.12 (conda env `adhi`), FastAPI, SQLAlchemy ORM pattern.
- Must run with `PYTHONPATH=""` to avoid ros_noetic_ws contamination.

## Approach

Three layers of change: (1) new auth infrastructure, (2) schema migration + model updates, (3) route + frontend updates.

## Design

### Architecture

```
Browser → [Login/Register] → POST /api/auth/login → JWT token
       → [Protected pages] → GET /api/* (Bearer token) → Backend validates → queries with user_id filter
```

### Key Components

| Component | Responsibility | Location |
|-----------|---------------|----------|
| User model | username, password_hash, created_at | `backend/models.py` |
| Auth utilities | hash/verify password, create/decode JWT | `backend/auth.py` (new) |
| Auth routes | register, login, me | `backend/routes/auth.py` (new) |
| get_current_user | FastAPI dependency — decode JWT, return User | `backend/auth.py` |
| Migration script | Add user_id columns, backfill existing data | `backend/migrate_multiuser.py` (new) |
| AuthContext | React context for token/user state | `frontend/src/context/AuthContext.jsx` (new) |
| Login page | Username/password form | `frontend/src/pages/Login.jsx` (new) |
| Register page | Username/password/confirm form | `frontend/src/pages/Register.jsx` (new) |

### Data Model Changes

**New `User` table:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)
```

**Modified `SrsItem`:**
```python
class SrsItem(Base):
    __tablename__ = "srs_items"
    # ... existing columns ...
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Change unique constraint from (subject_id) to:
    __table_args__ = (UniqueConstraint("user_id", "subject_id"),)
    subject = relationship("Subject")
    user = relationship("User")
```

**Modified `Setting`:**
```python
class Setting(Base):
    __tablename__ = "settings"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
```

**Modified `LevelEvent`:**
```python
class LevelEvent(Base):
    __tablename__ = "level_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    level = Column(Integer, nullable=False)
    reached_at = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "level"),)
```

**Modified `UserSynonym`:**
```python
class UserSynonym(Base):
    __tablename__ = "user_synonyms"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    meaning = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "subject_id", "meaning"),)
```

### Auth Flow

**`backend/auth.py`:**
```python
from passlib.context import CryptContext
from jose import jwt, JWTError

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)

def create_access_token(user_id: int, username: str) -> str:
    payload = {"sub": str(user_id), "username": username, "exp": datetime.utcnow() + timedelta(days=30)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    # Decode JWT, lookup user, raise 401 if invalid
```

**JWT secret management:**
```python
SECRET_FILE = PROJECT_ROOT / "data" / ".jwt_secret"
if SECRET_FILE.exists():
    SECRET_KEY = SECRET_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    SECRET_FILE.write_text(SECRET_KEY)
```

### Route Changes Pattern

Every route handler that touches user-specific data gets `current_user: User = Depends(get_current_user)` added:

**Before (reviews.py:30):**
```python
@router.get("/reviews")
def get_reviews(db: Session = Depends(get_db)):
    items = db.query(SrsItem).join(Subject).filter(SrsItem.srs_stage.between(1, 8))...
```

**After:**
```python
@router.get("/reviews")
def get_reviews(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = db.query(SrsItem).join(Subject).filter(
        SrsItem.user_id == current_user.id,
        SrsItem.srs_stage.between(1, 8),
    )...
```

**Routes requiring `current_user` dependency + `user_id` filter:**
- `backend/routes/reviews.py` — `get_reviews` (line 30), `submit_review` (line 78): SrsItem queries, UserSynonym query (line 90), LevelEvent insert (line 165), `_get_intervals` helper (line 24) needs user_id for Setting query
- `backend/routes/lessons.py` — `get_lessons`, `start_lessons`: SrsItem queries + creation
- `backend/routes/settings.py` — `get_settings` (line 11), `update_settings` (line 17): Setting queries filter by user_id
- `backend/routes/stats.py` — all endpoints: SrsItem aggregates, LevelEvent queries
- `backend/routes/levels.py` — `get_levels`, `get_level_detail`: SrsItem joins
- `backend/routes/subjects.py` — `get_subject` (SrsItem join portion), synonym CRUD, reset/resurrect
- `backend/routes/extra_study.py` — summary + study queries on SrsItem

**Routes unchanged (no user-specific data):**
- `backend/routes/subjects.py` — `get_subjects` (list) — reads Subject table only

### Settings Changes

**Startup (`main.py:24`):** Remove global `seed_defaults()`. Settings are no longer seeded on app startup.

**Registration:** When a new user registers, seed their default settings:
```python
defaults = {
    "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
    "lesson_batch_size": 5,
    "jlpt_gating": True,
    "dependency_gating": True,
    "max_reviews_per_session": None,
}
for k, v in defaults.items():
    db.add(Setting(user_id=new_user.id, key=k, value=json.dumps(v)))
```

### Migration Script (`backend/migrate_multiuser.py`)

```
1. Backup data/kanji-srs.db → data/kanji-srs.db.backup
2. CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at REAL NOT NULL)
3. INSERT INTO users (username, password_hash, created_at) VALUES ('adhi', <bcrypt hash of 'adhi1234'>, <now>)
4. For each table (srs_items, settings, level_events, user_synonyms):
   a. ALTER TABLE <table> ADD COLUMN user_id INTEGER REFERENCES users(id)
   b. UPDATE <table> SET user_id = 1  (adhi's id)
5. Recreate tables with NOT NULL + new unique constraints (SQLite requires CREATE new → copy → DROP old → rename)
6. For settings: change PK from (key) to (user_id, key)
7. For srs_items: change unique from (subject_id) to (user_id, subject_id)
```

### Frontend Changes

**`frontend/src/api.js` — add auth header:**
```javascript
async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, { headers, ...options });
  if (resp.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}
```

Add auth API calls:
```javascript
export const authApi = {
  login: (username, password) => request('/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  register: (username, password) => request('/auth/register', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  me: () => request('/auth/me'),
};
```

**`frontend/src/context/AuthContext.jsx`:**
- `AuthProvider` wraps the app
- Stores `user` and `token` in state
- On mount: check localStorage for token → validate via `/api/auth/me`
- Provides: `user`, `isAuthenticated`, `isLoading`, `login()`, `register()`, `logout()`

**`frontend/src/App.jsx`:**
- Wrap `BrowserRouter` children in `AuthProvider`
- Add `/login` and `/register` as public routes
- Wrap all other routes in a `ProtectedRoute` that redirects to `/login`
- Add username + logout button to `Nav` component

**New pages:**
- `Login.jsx` — form with username, password, submit. Link to `/register`.
- `Register.jsx` — form with username, password, confirm password. Link to `/login`.

### Test Changes

**`backend/tests/conftest.py`:**
```python
@pytest.fixture
def test_user(db):
    from backend.auth import hash_password
    user = User(username="testuser", password_hash=hash_password("testpass"), created_at=time.time())
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def auth_header(test_user):
    from backend.auth import create_access_token
    token = create_access_token(test_user.id, test_user.username)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def client(auth_header):
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.headers.update(auth_header)
    return c
```

Existing tests use `client` fixture → they automatically get auth headers. Tests that create SrsItem/Setting/etc. need to set `user_id=test_user.id`.

## File References

Files the plan agent MUST read before planning:
- `backend/models.py` — current model definitions (all 6 models)
- `backend/main.py` — startup logic, router registration
- `backend/database.py` — engine, session, Base
- `backend/routes/reviews.py` — most complex route, pattern for all others
- `backend/routes/settings.py` — simplest route, shows Setting query pattern
- `backend/routes/lessons.py` — SrsItem creation on lesson start
- `backend/routes/stats.py` — aggregate queries needing user_id
- `backend/routes/levels.py` — `compute_current_level` used by reviews
- `backend/routes/subjects.py` — mixed user/global queries, synonym CRUD, reset/resurrect
- `backend/routes/extra_study.py` — extra study queries
- `backend/srs_engine.py` — pure functions, no DB access (unchanged)
- `backend/tests/conftest.py` — test fixture pattern
- `frontend/src/api.js` — fetch wrapper to modify
- `frontend/src/App.jsx` — router + nav to modify

## Success Criteria

- [ ] `POST /api/auth/register` creates user, returns JWT
- [ ] `POST /api/auth/login` verifies credentials, returns JWT
- [ ] `GET /api/auth/me` returns current user info
- [ ] All non-auth endpoints return 401 without valid token
- [ ] Two registered users see independent SRS progress, settings, synonyms, level history
- [ ] Migration script preserves existing data under `adhi` account
- [ ] All existing tests pass with auth fixture changes
- [ ] Frontend login/register pages work end-to-end
- [ ] Nav shows username and logout button
- [ ] Logout clears token and redirects to login
