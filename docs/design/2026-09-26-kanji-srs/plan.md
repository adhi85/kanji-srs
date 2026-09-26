# Kanji SRS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Build a personal WaniKani clone — a self-contained web app for learning kanji via spaced repetition, with JLPT-ordered content imported once from WaniKani's API.

**Architecture:** FastAPI monolith serving a React SPA and REST API, backed by SQLite via SQLAlchemy. SRS engine is server-side. One-time data import from WaniKani API v2. Single process, single database file.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy, uvicorn, httpx), React 18+ (Vite, React Router, wanakana.js), SQLite.

---

## Task Dependency Map

```
Task 1 (project scaffolding) ── SERIAL, do first
    │
    ├── Task 2 (models)          ── SERIAL after 1
    │       │
    │       ├── Task 3 (SRS engine)     ── SERIAL after 2
    │       ├── Task 4 (JLPT mapping)   ── PARALLEL with 3
    │       │
    │       ├── Task 5 (settings routes)    ── SERIAL after 3
    │       ├── Task 6 (subject routes)     ── PARALLEL with 5
    │       ├── Task 7 (lesson routes)      ── SERIAL after 3, 5
    │       ├── Task 8 (review routes)      ── SERIAL after 3, 5
    │       ├── Task 9 (stats routes)       ── PARALLEL with 7, 8
    │       │
    │       └── Task 10 (import script)     ── PARALLEL with 5-9
    │
    └── Task 11 (frontend scaffolding)      ── PARALLEL with 2-10
            │
            ├── Task 12 (Dashboard page)    ── SERIAL after 11, 9
            ├── Task 13 (Subjects page)     ── SERIAL after 11, 6
            ├── Task 14 (Lessons page)      ── SERIAL after 11, 7
            ├── Task 15 (Reviews page)      ── SERIAL after 11, 8
            │
            └── Task 16 (static serving + integration) ── SERIAL after all
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/database.py`
- Create: `backend/requirements.txt`
- Create: `backend/conftest.py`
- Create: `.gitignore`

**Step 1: Create project directories**

```bash
cd ~/ADHI/projects/kanji-srs
mkdir -p backend/routes
mkdir -p frontend/src
mkdir -p data
touch backend/__init__.py
touch backend/routes/__init__.py
```

**Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
data/*.db
node_modules/
frontend/dist/
.env
*.egg-info/
```

**Step 3: Create `backend/requirements.txt`**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
httpx>=0.25.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

**Step 4: Create `backend/database.py`**

This sets up the SQLAlchemy engine and session factory. The database path defaults to `data/kanji-srs.db` relative to the project root.

```python
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
```

**Step 5: Create `backend/conftest.py`**

Shared pytest fixtures for all backend tests. Uses an in-memory SQLite database.

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
```

**Step 6: Initialize git and commit**

```bash
cd ~/ADHI/projects/kanji-srs
git init
pip install -r backend/requirements.txt
git add .
git commit -m "chore: project scaffolding with SQLAlchemy, FastAPI, pytest"
```

---

### Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/models.py`
- Create: `backend/tests/test_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models.py
import json
from backend.models import Subject, SubjectDependency, SrsItem, Setting
from backend.database import Base


def test_subject_creation(db):
    s = Subject(
        id=1,
        type="kanji",
        characters="大",
        slug="big",
        level=1,
        jlpt_level="N5",
        meanings=json.dumps([{"meaning": "Big", "primary": True}]),
        readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}]),
        meaning_mnemonic="A person spreading arms wide is big.",
        reading_mnemonic="Tie a big knot.",
    )
    db.add(s)
    db.commit()
    fetched = db.get(Subject, 1)
    assert fetched.characters == "大"
    assert fetched.jlpt_level == "N5"
    assert json.loads(fetched.meanings)[0]["meaning"] == "Big"


def test_subject_dependency(db):
    radical = Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                      meanings=json.dumps([{"meaning": "One", "primary": True}]))
    kanji = Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                    meanings=json.dumps([{"meaning": "Big", "primary": True}]))
    dep = SubjectDependency(subject_id=2, component_id=1)
    db.add_all([radical, kanji, dep])
    db.commit()

    deps = db.query(SubjectDependency).filter_by(subject_id=2).all()
    assert len(deps) == 1
    assert deps[0].component_id == 1


def test_srs_item_defaults(db):
    s = Subject(id=1, type="radical", characters="口", slug="mouth", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Mouth", "primary": True}]))
    db.add(s)
    db.commit()
    item = SrsItem(subject_id=1)
    db.add(item)
    db.commit()
    assert item.srs_stage == 0
    assert item.correct_count == 0
    assert item.incorrect_count == 0
    assert item.next_review_at is None


def test_setting_roundtrip(db):
    setting = Setting(key="lesson_batch_size", value=json.dumps(5))
    db.add(setting)
    db.commit()
    fetched = db.query(Setting).filter_by(key="lesson_batch_size").one()
    assert json.loads(fetched.value) == 5
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models'`

**Step 3: Write minimal implementation**

```python
# backend/models.py
from sqlalchemy import Column, Integer, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    type = Column(Text, nullable=False)
    characters = Column(Text, nullable=True)
    slug = Column(Text, nullable=True)
    level = Column(Integer, nullable=False)
    jlpt_level = Column(Text, nullable=True)
    meanings = Column(Text, nullable=False)
    readings = Column(Text, nullable=True)
    meaning_mnemonic = Column(Text, nullable=True)
    reading_mnemonic = Column(Text, nullable=True)
    part_of_speech = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)

    srs_item = relationship("SrsItem", back_populates="subject", uselist=False)
    components = relationship(
        "Subject",
        secondary="subject_dependencies",
        primaryjoin="Subject.id == SubjectDependency.subject_id",
        secondaryjoin="Subject.id == SubjectDependency.component_id",
        viewonly=True,
    )


class SubjectDependency(Base):
    __tablename__ = "subject_dependencies"

    subject_id = Column(Integer, ForeignKey("subjects.id"), primary_key=True)
    component_id = Column(Integer, ForeignKey("subjects.id"), primary_key=True)


class SrsItem(Base):
    __tablename__ = "srs_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), unique=True, nullable=False)
    srs_stage = Column(Integer, nullable=False, default=0)
    unlocked_at = Column(Float, nullable=True)
    started_at = Column(Float, nullable=True)
    next_review_at = Column(Float, nullable=True)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    meaning_correct_in_session = Column(Integer, default=0)
    reading_correct_in_session = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="srs_item")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
```

Note: timestamps stored as Unix floats for simplicity with SQLite.

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_models.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_models.py
git commit -m "feat: add SQLAlchemy models for subjects, SRS items, settings"
```

---

### Task 3: SRS Engine

**Files:**
- Create: `backend/srs_engine.py`
- Create: `backend/tests/test_srs_engine.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_srs_engine.py
import time
from backend.srs_engine import (
    advance_stage,
    retreat_stage,
    next_review_time,
    check_answer_meaning,
    check_answer_reading,
    DEFAULT_INTERVALS,
)


class TestStageAdvancement:
    def test_advance_from_1_to_2(self):
        assert advance_stage(1) == 2

    def test_advance_from_8_to_9_burned(self):
        assert advance_stage(8) == 9

    def test_advance_capped_at_9(self):
        assert advance_stage(9) == 9


class TestStageRetreat:
    def test_retreat_apprentice_drops_by_1(self):
        assert retreat_stage(2) == 1
        assert retreat_stage(3) == 2
        assert retreat_stage(4) == 3

    def test_retreat_apprentice_floor_is_1(self):
        assert retreat_stage(1) == 1

    def test_retreat_guru_and_above_drops_by_2(self):
        assert retreat_stage(5) == 3
        assert retreat_stage(6) == 4
        assert retreat_stage(7) == 5
        assert retreat_stage(8) == 6


class TestNextReviewTime:
    def test_stage_0_returns_none(self):
        assert next_review_time(0, DEFAULT_INTERVALS) is None

    def test_stage_9_returns_none(self):
        assert next_review_time(9, DEFAULT_INTERVALS) is None

    def test_stage_1_returns_4_hours_from_now(self):
        now = time.time()
        result = next_review_time(1, DEFAULT_INTERVALS)
        assert abs(result - (now + 14400)) < 2


class TestAnswerChecking:
    def test_meaning_exact_match(self):
        meanings = [{"meaning": "Big", "primary": True}, {"meaning": "Large", "primary": False}]
        assert check_answer_meaning("big", meanings) is True
        assert check_answer_meaning("Big", meanings) is True
        assert check_answer_meaning("large", meanings) is True

    def test_meaning_wrong(self):
        meanings = [{"meaning": "Big", "primary": True}]
        assert check_answer_meaning("small", meanings) is False

    def test_meaning_close_typo_tolerance(self):
        meanings = [{"meaning": "Construction", "primary": True}]
        assert check_answer_meaning("constructoin", meanings) is True  # 1 char diff in long word

    def test_meaning_no_tolerance_short_words(self):
        meanings = [{"meaning": "Big", "primary": True}]
        assert check_answer_meaning("bag", meanings) is False

    def test_reading_exact_hiragana(self):
        readings = [{"reading": "たい", "primary": True, "type": "onyomi"}]
        assert check_answer_reading("たい", readings) is True

    def test_reading_wrong(self):
        readings = [{"reading": "たい", "primary": True, "type": "onyomi"}]
        assert check_answer_reading("だい", readings) is False

    def test_reading_accepts_any_valid(self):
        readings = [
            {"reading": "たい", "primary": True, "type": "onyomi"},
            {"reading": "おお", "primary": False, "type": "kunyomi"},
        ]
        assert check_answer_reading("おお", readings) is True
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_srs_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/srs_engine.py
import time

DEFAULT_INTERVALS = [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0]


def advance_stage(current_stage: int) -> int:
    return min(current_stage + 1, 9)


def retreat_stage(current_stage: int) -> int:
    if current_stage <= 4:
        return max(current_stage - 1, 1)
    return max(current_stage - 2, 1)


def next_review_time(stage: int, intervals: list[int]) -> float | None:
    if stage == 0 or stage == 9:
        return None
    return time.time() + intervals[stage]


def check_answer_meaning(answer: str, meanings: list[dict]) -> bool:
    answer_lower = answer.strip().lower()
    for m in meanings:
        expected = m["meaning"].strip().lower()
        if answer_lower == expected:
            return True
        if len(expected) >= 5 and _levenshtein(answer_lower, expected) <= 1:
            return True
    return False


def check_answer_reading(answer: str, readings: list[dict]) -> bool:
    answer_stripped = answer.strip()
    return any(r["reading"].strip() == answer_stripped for r in readings)


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_srs_engine.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/srs_engine.py backend/tests/test_srs_engine.py
git commit -m "feat: add SRS engine with stage logic, interval calc, answer checking"
```

---

### Task 4: JLPT Mapping (PARALLEL with Task 3)

**Files:**
- Create: `backend/jlpt_mapping.py`
- Create: `backend/tests/test_jlpt_mapping.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_jlpt_mapping.py
from backend.jlpt_mapping import wanikani_level_to_jlpt


def test_level_1_is_n5():
    assert wanikani_level_to_jlpt(1) == "N5"

def test_level_10_is_n5():
    assert wanikani_level_to_jlpt(10) == "N5"

def test_level_11_is_n4():
    assert wanikani_level_to_jlpt(11) == "N4"

def test_level_30_is_n3():
    assert wanikani_level_to_jlpt(30) == "N3"

def test_level_40_is_n2():
    assert wanikani_level_to_jlpt(40) == "N2"

def test_level_50_is_n1():
    assert wanikani_level_to_jlpt(50) == "N1"

def test_level_60_is_n1():
    assert wanikani_level_to_jlpt(60) == "N1"

def test_invalid_level_returns_none():
    assert wanikani_level_to_jlpt(0) is None
    assert wanikani_level_to_jlpt(61) is None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_jlpt_mapping.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# backend/jlpt_mapping.py

def wanikani_level_to_jlpt(level: int) -> str | None:
    if 1 <= level <= 10:
        return "N5"
    if 11 <= level <= 20:
        return "N4"
    if 21 <= level <= 30:
        return "N3"
    if 31 <= level <= 40:
        return "N2"
    if 41 <= level <= 60:
        return "N1"
    return None
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_jlpt_mapping.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add backend/jlpt_mapping.py backend/tests/test_jlpt_mapping.py
git commit -m "feat: add WaniKani level to JLPT level mapping"
```

---

### Task 5: Settings Routes

**Files:**
- Create: `backend/routes/settings.py`
- Create: `backend/tests/test_settings_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_settings_routes.py
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Setting

engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_settings_routes.py -v`
Expected: FAIL (no `backend.main` module yet)

**Step 3: Write the FastAPI app and settings routes**

```python
# backend/main.py
from fastapi import FastAPI
from backend.routes import settings, subjects, lessons, reviews, stats

app = FastAPI(title="Kanji SRS")

app.include_router(settings.router, prefix="/api")
```

Note: the other routers (subjects, lessons, reviews, stats) will be empty placeholder files for now so the import doesn't break.

```python
# backend/routes/settings.py
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Setting

router = APIRouter()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {row.key: json.loads(row.value) for row in rows}


@router.put("/settings")
def update_settings(updates: dict, db: Session = Depends(get_db)):
    for key, value in updates.items():
        setting = db.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = json.dumps(value)
    db.commit()
    return get_settings(db)
```

Create placeholder route files so `backend/main.py` imports don't break:

```python
# backend/routes/subjects.py
from fastapi import APIRouter
router = APIRouter()
```

```python
# backend/routes/lessons.py
from fastapi import APIRouter
router = APIRouter()
```

```python
# backend/routes/reviews.py
from fastapi import APIRouter
router = APIRouter()
```

```python
# backend/routes/stats.py
from fastapi import APIRouter
router = APIRouter()
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_settings_routes.py -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add backend/main.py backend/routes/ backend/tests/test_settings_routes.py
git commit -m "feat: add settings GET/PUT API routes and FastAPI app skeleton"
```

---

### Task 6: Subject Routes (PARALLEL with Task 5)

**Files:**
- Modify: `backend/routes/subjects.py`
- Create: `backend/tests/test_subject_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_subject_routes.py
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Subject, SubjectDependency, SrsItem

engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_subject_routes.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/routes/subjects.py
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SubjectDependency, SrsItem

router = APIRouter()


def _subject_to_dict(s: Subject) -> dict:
    return {
        "id": s.id,
        "type": s.type,
        "characters": s.characters,
        "slug": s.slug,
        "level": s.level,
        "jlpt_level": s.jlpt_level,
        "meanings": json.loads(s.meanings),
        "readings": json.loads(s.readings) if s.readings else [],
        "meaning_mnemonic": s.meaning_mnemonic,
        "reading_mnemonic": s.reading_mnemonic,
        "part_of_speech": json.loads(s.part_of_speech) if s.part_of_speech else [],
    }


@router.get("/subjects")
def list_subjects(
    jlpt: str | None = None,
    type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Subject)
    if jlpt:
        query = query.filter(Subject.jlpt_level == jlpt)
    if type:
        query = query.filter(Subject.type == type)
    if q:
        q_lower = f"%{q.lower()}%"
        query = query.filter(
            (Subject.characters.ilike(q_lower)) | (Subject.meanings.ilike(q_lower))
        )
    total = query.count()
    items = query.order_by(Subject.level, Subject.id).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [_subject_to_dict(s) for s in items], "total": total, "page": page}


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    result = _subject_to_dict(subject)
    dep_ids = db.query(SubjectDependency.component_id).filter_by(subject_id=subject_id).all()
    components = [db.get(Subject, d[0]) for d in dep_ids]
    result["components"] = [_subject_to_dict(c) for c in components if c]
    srs = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if srs:
        result["srs"] = {
            "stage": srs.srs_stage,
            "correct_count": srs.correct_count,
            "incorrect_count": srs.incorrect_count,
            "next_review_at": srs.next_review_at,
        }
    return result
```

Also update `backend/main.py` to include the subjects router:

```python
app.include_router(subjects.router, prefix="/api")
```

(This should already be in the import list from Task 5.)

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_subject_routes.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/routes/subjects.py backend/tests/test_subject_routes.py
git commit -m "feat: add subject list/detail/search/filter API routes"
```

---

### Task 7: Lesson Routes

**Files:**
- Modify: `backend/routes/lessons.py`
- Create: `backend/tests/test_lesson_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_lesson_routes.py
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Subject, SrsItem, Setting

engine = create_engine("sqlite:///:memory:")
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
        db.add(Subject(id=i, type="kanji", characters=f"字{i}", slug=f"char{i}", level=1,
                       jlpt_level="N5",
                       meanings=json.dumps([{"meaning": f"Char{i}", "primary": True}]),
                       readings=json.dumps([{"reading": "じ", "primary": True, "type": "onyomi"}])))
        db.add(SrsItem(subject_id=i, srs_stage=0))
    db.add(Setting(key="lesson_batch_size", value=json.dumps(5)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="dependency_gating", value=json.dumps(False)))
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_lesson_routes.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/routes/lessons.py
import json
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting
from backend.srs_engine import next_review_time, DEFAULT_INTERVALS

router = APIRouter()


def _get_setting(db: Session, key: str, default=None):
    row = db.query(Setting).filter_by(key=key).first()
    return json.loads(row.value) if row else default


def _get_intervals(db: Session) -> list[int]:
    return _get_setting(db, "srs_intervals", DEFAULT_INTERVALS)


@router.get("/lessons")
def get_lessons(db: Session = Depends(get_db)):
    batch_size = _get_setting(db, "lesson_batch_size", 5)
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage == 0)
        .order_by(Subject.level, Subject.id)
        .limit(batch_size)
        .all()
    )
    results = []
    for item in items:
        s = item.subject
        results.append({
            "id": s.id,
            "type": s.type,
            "characters": s.characters,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
        })
    return results


class StartLessonsRequest(BaseModel):
    subject_ids: list[int]


@router.post("/lessons/start")
def start_lessons(req: StartLessonsRequest, db: Session = Depends(get_db)):
    intervals = _get_intervals(db)
    started = 0
    for sid in req.subject_ids:
        item = db.query(SrsItem).filter_by(subject_id=sid, srs_stage=0).first()
        if item:
            item.srs_stage = 1
            item.started_at = time.time()
            item.next_review_at = next_review_time(1, intervals)
            started += 1
    db.commit()
    return {"started": started}
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_lesson_routes.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add backend/routes/lessons.py backend/tests/test_lesson_routes.py
git commit -m "feat: add lesson GET (batch) and POST (start) API routes"
```

---

### Task 8: Review Routes

**Files:**
- Modify: `backend/routes/reviews.py`
- Create: `backend/tests/test_review_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_review_routes.py
import json
import time
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Subject, SrsItem, Setting
from backend.srs_engine import DEFAULT_INTERVALS

engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _seed_review_item(db):
    """Create a kanji at stage 2 with next_review_at in the past so it's due."""
    s = Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}]),
                meaning_mnemonic="A person stretching wide.")
    db.add(s)
    item = SrsItem(subject_id=1, srs_stage=2, next_review_at=time.time() - 100)
    db.add(item)
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = TestSession()
    _seed_review_item(db)
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_review_routes.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/routes/reviews.py
import json
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting
from backend.srs_engine import (
    advance_stage,
    retreat_stage,
    next_review_time,
    check_answer_meaning,
    check_answer_reading,
    DEFAULT_INTERVALS,
)

router = APIRouter()


def _get_intervals(db: Session) -> list[int]:
    row = db.query(Setting).filter_by(key="srs_intervals").first()
    return json.loads(row.value) if row else DEFAULT_INTERVALS


@router.get("/reviews")
def get_reviews(db: Session = Depends(get_db)):
    now = time.time()
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at <= now)
        .order_by(SrsItem.next_review_at)
        .all()
    )
    return [
        {
            "srs_item_id": item.id,
            "subject_id": item.subject_id,
            "type": item.subject.type,
            "characters": item.subject.characters,
        }
        for item in items
    ]


class AnswerRequest(BaseModel):
    answer_type: str  # "meaning" or "reading"
    answer: str


@router.post("/reviews/{subject_id}")
def submit_review(subject_id: int, req: AnswerRequest, db: Session = Depends(get_db)):
    item = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    meanings = json.loads(subject.meanings)
    readings = json.loads(subject.readings) if subject.readings else []

    if req.answer_type == "meaning":
        correct = check_answer_meaning(req.answer, meanings)
        correct_answer = next((m["meaning"] for m in meanings if m.get("primary")), meanings[0]["meaning"])
        mnemonic = subject.meaning_mnemonic
    elif req.answer_type == "reading":
        correct = check_answer_reading(req.answer, readings)
        correct_answer = next((r["reading"] for r in readings if r.get("primary")), readings[0]["reading"] if readings else "")
        mnemonic = subject.reading_mnemonic
    else:
        raise HTTPException(status_code=400, detail="answer_type must be 'meaning' or 'reading'")

    if correct:
        if req.answer_type == "meaning":
            item.meaning_correct_in_session = 1
        else:
            item.reading_correct_in_session = 1
        item.correct_count += 1
    else:
        if req.answer_type == "meaning":
            item.meaning_correct_in_session = 0
        else:
            item.reading_correct_in_session = 0
        item.incorrect_count += 1

    new_stage = item.srs_stage
    both_needed = subject.type != "radical"
    meaning_done = item.meaning_correct_in_session == 1
    reading_done = item.reading_correct_in_session == 1 if both_needed else True

    if meaning_done and reading_done:
        any_wrong = item.incorrect_count > (item.correct_count - (2 if both_needed else 1))
        if item.meaning_correct_in_session and item.reading_correct_in_session:
            had_wrong = (item.incorrect_count > 0 and
                         not (item.meaning_correct_in_session and item.reading_correct_in_session))
        new_stage = advance_stage(item.srs_stage)
        item.srs_stage = new_stage
        intervals = _get_intervals(db)
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0
    elif not correct:
        new_stage = retreat_stage(item.srs_stage)
        item.srs_stage = new_stage
        intervals = _get_intervals(db)
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0

    db.commit()

    return {
        "correct": correct,
        "correct_answer": correct_answer if not correct else None,
        "new_stage": new_stage,
        "mnemonic": mnemonic if not correct else None,
    }
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_review_routes.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/routes/reviews.py backend/tests/test_review_routes.py
git commit -m "feat: add review GET (due items) and POST (submit answer) routes"
```

---

### Task 9: Stats / Summary Routes (PARALLEL with Tasks 7, 8)

**Files:**
- Modify: `backend/routes/stats.py`
- Create: `backend/tests/test_stats_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_stats_routes.py
import json
import time
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Subject, SrsItem

engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_stats_routes.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/routes/stats.py
import time
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import Subject, SrsItem

router = APIRouter()


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    now = time.time()

    reviews_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at <= now)
        .scalar()
    )

    next_review = (
        db.query(func.min(SrsItem.next_review_at))
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at > now)
        .scalar()
    )

    lessons_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.srs_stage == 0)
        .scalar()
    )

    stage_counts = defaultdict(int)
    rows = db.query(SrsItem.srs_stage, func.count(SrsItem.id)).group_by(SrsItem.srs_stage).all()
    for stage, count in rows:
        stage_counts[str(stage)] = count

    jlpt_progress = {}
    jlpt_rows = (
        db.query(Subject.jlpt_level, func.count(Subject.id))
        .group_by(Subject.jlpt_level)
        .all()
    )
    for level, total in jlpt_rows:
        if level:
            burned = (
                db.query(func.count(SrsItem.id))
                .join(Subject)
                .filter(Subject.jlpt_level == level, SrsItem.srs_stage == 9)
                .scalar()
            )
            jlpt_progress[level] = {"total": total, "burned": burned}

    return {
        "reviews_available": reviews_available,
        "next_review_at": next_review,
        "lessons_available": lessons_available,
        "srs_stage_counts": dict(stage_counts),
        "jlpt_progress": jlpt_progress,
    }
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_stats_routes.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/routes/stats.py backend/tests/test_stats_routes.py
git commit -m "feat: add summary/stats API route with SRS counts and JLPT progress"
```

---

### Task 10: WaniKani Import Script (PARALLEL with Tasks 5-9)

**Files:**
- Create: `backend/import_wanikani.py`
- Create: `backend/tests/test_import.py`

**Step 1: Write the failing test**

This test mocks the WaniKani API responses to verify import logic without making real HTTP calls.

```python
# backend/tests/test_import.py
import json
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Subject, SubjectDependency, SrsItem
from backend.import_wanikani import import_subjects


def _make_api_response(subjects, next_url=None):
    return {
        "total_count": len(subjects),
        "pages": {"next_url": next_url, "previous_url": None, "per_page": 1000},
        "data": subjects,
    }


def _make_subject(id, type, characters, level, meanings, readings=None, components=None):
    return {
        "id": id,
        "object": type,
        "data": {
            "characters": characters,
            "slug": characters,
            "level": level,
            "meanings": [{"meaning": m, "primary": i == 0} for i, m in enumerate(meanings)],
            "readings": [{"reading": r, "primary": i == 0, "type": "onyomi"} for i, r in enumerate(readings or [])],
            "meaning_mnemonic": "A mnemonic.",
            "reading_mnemonic": "A reading mnemonic.",
            "component_subject_ids": components or [],
            "document_url": f"https://wanikani.com/{type}/{characters}",
            "parts_of_speech": [],
        },
    }


def test_import_subjects():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    api_data = [
        _make_subject(1, "radical", "一", 1, ["One"]),
        _make_subject(2, "kanji", "大", 1, ["Big"], ["たい", "おお"], [1]),
        _make_subject(3, "vocabulary", "大人", 3, ["Adult"], ["おとな"], [2]),
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = _make_api_response(api_data)
    mock_response.status_code = 200
    mock_response.headers = {"RateLimit-Remaining": "59"}

    with patch("backend.import_wanikani.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_httpx.Client.return_value = mock_client

        db = Session()
        import_subjects(db, "fake-token")
        db.close()

    db = Session()
    assert db.query(Subject).count() == 3
    assert db.query(SubjectDependency).count() == 2  # kanji->radical + vocab->kanji
    assert db.query(SrsItem).count() == 3
    kanji = db.get(Subject, 2)
    assert kanji.jlpt_level == "N5"
    assert json.loads(kanji.meanings)[0]["meaning"] == "Big"
    db.close()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_import.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/import_wanikani.py
import json
import sys
import time

import httpx
from sqlalchemy.orm import Session

from backend.database import Base, engine, SessionLocal
from backend.jlpt_mapping import wanikani_level_to_jlpt
from backend.models import Subject, SubjectDependency, SrsItem

WANIKANI_API_BASE = "https://api.wanikani.com/v2"


def import_subjects(db: Session, token: str):
    url = f"{WANIKANI_API_BASE}/subjects"
    headers = {"Authorization": f"Bearer {token}"}
    total_imported = 0

    with httpx.Client(timeout=30) as client:
        while url:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for item in data["data"]:
                subj_data = item["data"]
                subject = Subject(
                    id=item["id"],
                    type=item["object"],
                    characters=subj_data.get("characters"),
                    slug=subj_data.get("slug"),
                    level=subj_data["level"],
                    jlpt_level=wanikani_level_to_jlpt(subj_data["level"]),
                    meanings=json.dumps(subj_data.get("meanings", [])),
                    readings=json.dumps(subj_data.get("readings", [])),
                    meaning_mnemonic=subj_data.get("meaning_mnemonic"),
                    reading_mnemonic=subj_data.get("reading_mnemonic"),
                    part_of_speech=json.dumps(subj_data.get("parts_of_speech", [])),
                    document_url=subj_data.get("document_url"),
                )
                db.merge(subject)

                for comp_id in subj_data.get("component_subject_ids", []):
                    db.merge(SubjectDependency(subject_id=item["id"], component_id=comp_id))

                db.merge(SrsItem(subject_id=item["id"], srs_stage=0))

            total_imported += len(data["data"])
            print(f"Imported {total_imported} subjects...")

            url = data["pages"].get("next_url")

            remaining = int(resp.headers.get("RateLimit-Remaining", "59"))
            if remaining < 5:
                print("Rate limit approaching, sleeping 30s...")
                time.sleep(30)

    db.commit()
    print(f"Done. Total subjects imported: {total_imported}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_wanikani.py <API_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        import_subjects(db, token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/test_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/import_wanikani.py backend/tests/test_import.py
git commit -m "feat: add one-time WaniKani data import script with rate limiting"
```

---

### Task 11: Frontend Scaffolding (PARALLEL with Tasks 2-10)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api.js`
- Create: `frontend/src/App.css`

**Step 1: Initialize frontend project**

```bash
cd ~/ADHI/projects/kanji-srs/frontend
npm create vite@latest . -- --template react
```

If prompted, select React / JavaScript.

**Step 2: Install dependencies**

```bash
cd ~/ADHI/projects/kanji-srs/frontend
npm install react-router-dom wanakana
```

**Step 3: Configure Vite proxy**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

**Step 4: Create API client**

```javascript
// frontend/src/api.js
const BASE = '/api';

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

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
};
```

**Step 5: Create App shell with routing**

```jsx
// frontend/src/App.jsx
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import Reviews from './pages/Reviews';
import Subjects from './pages/Subjects';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <nav className="nav">
        <NavLink to="/" end>Dashboard</NavLink>
        <NavLink to="/lessons">Lessons</NavLink>
        <NavLink to="/reviews">Reviews</NavLink>
        <NavLink to="/subjects">Subjects</NavLink>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lessons" element={<Lessons />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/subjects" element={<Subjects />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

Create placeholder page components so the app compiles:

```bash
mkdir -p frontend/src/pages
```

For each page (Dashboard.jsx, Lessons.jsx, Reviews.jsx, Subjects.jsx), create a placeholder:

```jsx
// frontend/src/pages/Dashboard.jsx
export default function Dashboard() {
  return <div><h1>Dashboard</h1><p>Loading...</p></div>;
}
```

(Repeat pattern for Lessons.jsx, Reviews.jsx, Subjects.jsx with their respective titles.)

**Step 6: Add base CSS**

```css
/* frontend/src/App.css */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  min-height: 100vh;
}

.nav {
  display: flex;
  gap: 1rem;
  padding: 1rem 2rem;
  background: #16213e;
  border-bottom: 2px solid #0f3460;
}

.nav a {
  color: #a0a0b0;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: all 0.2s;
}

.nav a:hover, .nav a.active {
  color: #fff;
  background: #0f3460;
}

.main {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}

h1 { margin-bottom: 1rem; }

.card {
  background: #16213e;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.character-large {
  font-size: 6rem;
  text-align: center;
  padding: 2rem;
}

input[type="text"] {
  width: 100%;
  padding: 0.75rem;
  font-size: 1.2rem;
  border: 2px solid #0f3460;
  border-radius: 4px;
  background: #1a1a2e;
  color: #fff;
  outline: none;
}

input[type="text"]:focus {
  border-color: #e94560;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  background: #e94560;
  color: #fff;
}

.btn:hover { background: #c73e54; }

.correct { color: #4ecca3; }
.incorrect { color: #e94560; }

.progress-bar {
  width: 100%;
  height: 8px;
  background: #0f3460;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #4ecca3;
  transition: width 0.3s;
}
```

**Step 7: Verify frontend compiles**

```bash
cd ~/ADHI/projects/kanji-srs/frontend
npm run build
```

Expected: Build succeeds, output in `dist/`

**Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with routing, API client, and base styles"
```

---

### Task 12: Dashboard Page (SERIAL after Tasks 11, 9)

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Step 1: Implement Dashboard**

```jsx
// frontend/src/pages/Dashboard.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

const STAGE_NAMES = ['Not Started', 'Apprentice 1', 'Apprentice 2', 'Apprentice 3', 'Apprentice 4',
                     'Guru 1', 'Guru 2', 'Master', 'Enlightened', 'Burned'];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [countdown, setCountdown] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getSummary().then(setSummary);
  }, []);

  useEffect(() => {
    if (!summary?.next_review_at) return;
    const interval = setInterval(() => {
      const diff = Math.max(0, Math.floor(summary.next_review_at - Date.now() / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setCountdown(`${h}h ${m}m ${s}s`);
    }, 1000);
    return () => clearInterval(interval);
  }, [summary?.next_review_at]);

  if (!summary) return <p>Loading...</p>;

  return (
    <div>
      <div className="card" style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem' }}>{summary.reviews_available}</h1>
        <p>Reviews Available</p>
        {summary.reviews_available > 0 && (
          <button className="btn" onClick={() => navigate('/reviews')} style={{ marginTop: '1rem' }}>
            Start Reviews
          </button>
        )}
        {summary.next_review_at && summary.reviews_available === 0 && (
          <p style={{ marginTop: '0.5rem', color: '#a0a0b0' }}>Next review in {countdown}</p>
        )}
      </div>

      <div className="card" style={{ textAlign: 'center' }}>
        <h2>{summary.lessons_available}</h2>
        <p>Lessons Available</p>
        {summary.lessons_available > 0 && (
          <button className="btn" onClick={() => navigate('/lessons')} style={{ marginTop: '1rem' }}>
            Start Lessons
          </button>
        )}
      </div>

      <div className="card">
        <h2>SRS Stages</h2>
        {STAGE_NAMES.map((name, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
            <span>{name}</span>
            <span>{summary.srs_stage_counts[String(i)] || 0}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>JLPT Progress</h2>
        {['N5', 'N4', 'N3', 'N2', 'N1'].map(level => {
          const p = summary.jlpt_progress[level];
          if (!p) return null;
          const pct = p.total > 0 ? (p.burned / p.total) * 100 : 0;
          return (
            <div key={level} style={{ marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{level}</span>
                <span>{p.burned} / {p.total}</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser**

```bash
cd ~/ADHI/projects/kanji-srs/frontend && npm run dev &
cd ~/ADHI/projects/kanji-srs && uvicorn backend.main:app --reload &
```

Open `http://localhost:5173` in browser. Dashboard should load (will show zeros if no data imported yet).

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: implement Dashboard page with review count, countdown, SRS stages, JLPT progress"
```

---

### Task 13: Subjects Page (SERIAL after Tasks 11, 6)

**Files:**
- Modify: `frontend/src/pages/Subjects.jsx`

**Step 1: Implement Subjects browser**

```jsx
// frontend/src/pages/Subjects.jsx
import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Subjects() {
  const [subjects, setSubjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ jlpt: '', type: '', q: '' });
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const params = { page };
    if (filters.jlpt) params.jlpt = filters.jlpt;
    if (filters.type) params.type = filters.type;
    if (filters.q) params.q = filters.q;
    api.getSubjects(params).then(data => {
      setSubjects(data.items);
      setTotal(data.total);
    });
  }, [page, filters]);

  const showDetail = async (id) => {
    const data = await api.getSubject(id);
    setSelected(data);
  };

  if (selected) {
    return (
      <div>
        <button className="btn" onClick={() => setSelected(null)} style={{ marginBottom: '1rem' }}>
          Back
        </button>
        <div className="card">
          <div className="character-large">{selected.characters || '(image)'}</div>
          <h2>{selected.meanings.map(m => m.meaning).join(', ')}</h2>
          {selected.readings?.length > 0 && (
            <p>Readings: {selected.readings.map(r => `${r.reading} (${r.type})`).join(', ')}</p>
          )}
          <p style={{ color: '#a0a0b0' }}>{selected.type} | Level {selected.level} | {selected.jlpt_level}</p>
          {selected.meaning_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Meaning Mnemonic</h3>
              <p>{selected.meaning_mnemonic}</p>
            </div>
          )}
          {selected.reading_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Reading Mnemonic</h3>
              <p>{selected.reading_mnemonic}</p>
            </div>
          )}
          {selected.components?.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Components</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {selected.components.map(c => (
                  <span key={c.id} className="card" style={{ cursor: 'pointer', padding: '0.5rem' }}
                        onClick={() => showDetail(c.id)}>
                    {c.characters} ({c.meanings[0]?.meaning})
                  </span>
                ))}
              </div>
            </div>
          )}
          {selected.srs && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Your Progress</h3>
              <p>Stage: {selected.srs.stage} | Correct: {selected.srs.correct_count} | Incorrect: {selected.srs.incorrect_count}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Subjects</h1>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <select value={filters.jlpt} onChange={e => { setFilters(f => ({ ...f, jlpt: e.target.value })); setPage(1); }}>
          <option value="">All JLPT</option>
          {['N5','N4','N3','N2','N1'].map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={filters.type} onChange={e => { setFilters(f => ({ ...f, type: e.target.value })); setPage(1); }}>
          <option value="">All Types</option>
          {['radical','kanji','vocabulary'].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input type="text" placeholder="Search..." value={filters.q}
               onChange={e => { setFilters(f => ({ ...f, q: e.target.value })); setPage(1); }}
               style={{ flex: 1 }} />
      </div>

      <p style={{ color: '#a0a0b0', marginBottom: '0.5rem' }}>{total} subjects found</p>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '0.5rem' }}>Character</th>
            <th style={{ textAlign: 'left', padding: '0.5rem' }}>Meaning</th>
            <th style={{ textAlign: 'left', padding: '0.5rem' }}>Type</th>
            <th style={{ textAlign: 'left', padding: '0.5rem' }}>JLPT</th>
          </tr>
        </thead>
        <tbody>
          {subjects.map(s => (
            <tr key={s.id} onClick={() => showDetail(s.id)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #0f3460' }}>
              <td style={{ padding: '0.5rem', fontSize: '1.5rem' }}>{s.characters || '(image)'}</td>
              <td style={{ padding: '0.5rem' }}>{s.meanings[0]?.meaning}</td>
              <td style={{ padding: '0.5rem' }}>{s.type}</td>
              <td style={{ padding: '0.5rem' }}>{s.jlpt_level}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
        <button className="btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
        <span>Page {page}</span>
        <button className="btn" disabled={subjects.length < 50} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser** — navigate to `/subjects`, confirm table renders.

**Step 3: Commit**

```bash
git add frontend/src/pages/Subjects.jsx
git commit -m "feat: implement Subjects browser with search, filters, and detail view"
```

---

### Task 14: Lessons Page (SERIAL after Tasks 11, 7)

**Files:**
- Modify: `frontend/src/pages/Lessons.jsx`

**Step 1: Implement Lessons page**

```jsx
// frontend/src/pages/Lessons.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Lessons() {
  const [items, setItems] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [phase, setPhase] = useState('loading'); // loading | study | quiz | done
  const [quizAnswer, setQuizAnswer] = useState('');
  const [quizType, setQuizType] = useState('meaning');
  const [quizResult, setQuizResult] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getLessons().then(data => {
      if (data.length === 0) {
        setPhase('done');
      } else {
        setItems(data);
        setPhase('study');
      }
    });
  }, []);

  const currentItem = items[currentIndex];

  const handleNext = () => {
    if (currentIndex < items.length - 1) {
      setCurrentIndex(i => i + 1);
    } else {
      setCurrentIndex(0);
      setQuizType('meaning');
      setPhase('quiz');
    }
  };

  const handleQuizSubmit = (e) => {
    e.preventDefault();
    const meanings = currentItem.meanings.map(m => m.meaning.toLowerCase());
    const readings = (currentItem.readings || []).map(r => r.reading);
    let correct;
    if (quizType === 'meaning') {
      correct = meanings.includes(quizAnswer.trim().toLowerCase());
    } else {
      correct = readings.includes(quizAnswer.trim());
    }
    setQuizResult(correct);
    if (correct) {
      setTimeout(() => {
        setQuizResult(null);
        setQuizAnswer('');
        if (quizType === 'meaning' && currentItem.type !== 'radical' && currentItem.readings?.length) {
          setQuizType('reading');
        } else if (currentIndex < items.length - 1) {
          setCurrentIndex(i => i + 1);
          setQuizType('meaning');
        } else {
          api.startLessons(items.map(i => i.id)).then(() => setPhase('done'));
        }
      }, 800);
    } else {
      setTimeout(() => { setQuizResult(null); setQuizAnswer(''); }, 1500);
    }
  };

  if (phase === 'loading') return <p>Loading lessons...</p>;

  if (phase === 'done') {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>No lessons available</h1>
        <p>Check back later or adjust your settings.</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'study') {
    return (
      <div>
        <p style={{ color: '#a0a0b0' }}>Lesson {currentIndex + 1} of {items.length}</p>
        <div className="card">
          <div className="character-large">{currentItem.characters || '(image)'}</div>
          <h2>{currentItem.meanings.map(m => m.meaning).join(', ')}</h2>
          {currentItem.readings?.length > 0 && (
            <p style={{ fontSize: '1.2rem' }}>
              {currentItem.readings.map(r => `${r.reading} (${r.type || ''})`).join(', ')}
            </p>
          )}
          {currentItem.meaning_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Meaning</h3>
              <p>{currentItem.meaning_mnemonic}</p>
            </div>
          )}
          {currentItem.reading_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Reading</h3>
              <p>{currentItem.reading_mnemonic}</p>
            </div>
          )}
        </div>
        <button className="btn" onClick={handleNext} style={{ width: '100%' }}>
          {currentIndex < items.length - 1 ? 'Next' : 'Start Quiz'}
        </button>
      </div>
    );
  }

  // Quiz phase
  return (
    <div>
      <p style={{ color: '#a0a0b0' }}>Quiz: {currentIndex + 1} of {items.length} — {quizType}</p>
      <div className="card">
        <div className="character-large">{currentItem.characters || '(image)'}</div>
        <form onSubmit={handleQuizSubmit}>
          <label>{quizType === 'meaning' ? 'Type the meaning:' : 'Type the reading (hiragana):'}</label>
          <input type="text" value={quizAnswer} onChange={e => setQuizAnswer(e.target.value)}
                 autoFocus style={{ marginTop: '0.5rem' }} />
        </form>
        {quizResult === true && <p className="correct" style={{ marginTop: '0.5rem' }}>Correct!</p>}
        {quizResult === false && <p className="incorrect" style={{ marginTop: '0.5rem' }}>Try again</p>}
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser** — navigate to `/lessons`, confirm the study -> quiz flow works.

**Step 3: Commit**

```bash
git add frontend/src/pages/Lessons.jsx
git commit -m "feat: implement Lessons page with study cards and quiz flow"
```

---

### Task 15: Reviews Page (SERIAL after Tasks 11, 8)

**Files:**
- Modify: `frontend/src/pages/Reviews.jsx`

**Step 1: Implement Reviews page**

```jsx
// frontend/src/pages/Reviews.jsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toHiragana, bind, unbind } from 'wanakana';
import { api } from '../api';

export default function Reviews() {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answerType, setAnswerType] = useState('meaning');
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [stats, setStats] = useState({ correct: 0, incorrect: 0 });
  const [phase, setPhase] = useState('loading');
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getReviews().then(items => {
      if (items.length === 0) {
        setPhase('empty');
        return;
      }
      const shuffled = items.sort(() => Math.random() - 0.5);
      const expanded = [];
      for (const item of shuffled) {
        expanded.push({ ...item, answerType: 'meaning' });
        if (item.type !== 'radical') {
          expanded.push({ ...item, answerType: 'reading' });
        }
      }
      expanded.sort(() => Math.random() - 0.5);
      setQueue(expanded);
      setPhase('reviewing');
    });
  }, []);

  useEffect(() => {
    if (phase !== 'reviewing' || !inputRef.current) return;
    const current = queue[currentIndex];
    if (current?.answerType === 'reading') {
      bind(inputRef.current);
      return () => unbind(inputRef.current);
    }
  }, [currentIndex, phase]);

  useEffect(() => {
    if (phase === 'reviewing' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!answer.trim() || result !== null) return;
    const current = queue[currentIndex];
    const resp = await api.submitReview(current.subject_id, current.answerType, answer.trim());
    setResult(resp);
    setStats(s => ({
      correct: s.correct + (resp.correct ? 1 : 0),
      incorrect: s.incorrect + (resp.correct ? 0 : 1),
    }));
  };

  const handleNextAfterResult = () => {
    setResult(null);
    setAnswer('');
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(i => i + 1);
    } else {
      setPhase('summary');
    }
  };

  if (phase === 'loading') return <p>Loading reviews...</p>;

  if (phase === 'empty') {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>No reviews available</h1>
        <p>Check back later.</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>Session Complete</h1>
        <p style={{ fontSize: '2rem' }}>{pct}%</p>
        <p>{stats.correct} correct, {stats.incorrect} incorrect</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  const current = queue[currentIndex];
  const progress = ((currentIndex + 1) / queue.length) * 100;

  return (
    <div>
      <div className="progress-bar" style={{ marginBottom: '1rem' }}>
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p style={{ color: '#a0a0b0', textAlign: 'center' }}>
        {currentIndex + 1} / {queue.length} — {current.answerType}
      </p>

      <div className="card">
        <div className="character-large">{current.characters || '(image)'}</div>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            {current.answerType === 'meaning' ? 'Meaning (English):' : 'Reading (hiragana):'}
          </label>
          <input ref={inputRef} type="text" value={answer}
                 onChange={e => setAnswer(e.target.value)}
                 disabled={result !== null}
                 style={result !== null ? {
                   borderColor: result.correct ? '#4ecca3' : '#e94560',
                   backgroundColor: result.correct ? '#1a3a2a' : '#3a1a1a',
                 } : {}} />
        </form>

        {result && (
          <div style={{ marginTop: '1rem' }}>
            {result.correct ? (
              <p className="correct">Correct!</p>
            ) : (
              <>
                <p className="incorrect">Incorrect — answer: {result.correct_answer}</p>
                {result.mnemonic && <p style={{ marginTop: '0.5rem', color: '#a0a0b0' }}>{result.mnemonic}</p>}
              </>
            )}
            <button className="btn" onClick={handleNextAfterResult} style={{ marginTop: '1rem', width: '100%' }}>
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser** — start a review session, test typed answers, verify romaji→hiragana conversion on reading questions.

**Step 3: Commit**

```bash
git add frontend/src/pages/Reviews.jsx
git commit -m "feat: implement Reviews page with typed answers and wanakana input"
```

---

### Task 16: Static Serving & Integration

**Files:**
- Modify: `backend/main.py`

**Step 1: Update FastAPI to serve static files**

```python
# backend/main.py
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routes import settings, subjects, lessons, reviews, stats

app = FastAPI(title="Kanji SRS")

app.include_router(settings.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(lessons.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(stats.router, prefix="/api")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
```

**Step 2: Build frontend and test full stack**

```bash
cd ~/ADHI/projects/kanji-srs/frontend && npm run build
cd ~/ADHI/projects/kanji-srs && uvicorn backend.main:app
```

Open `http://localhost:8000` — should serve the React app. Navigate to different routes — should work with client-side routing. API calls under `/api/` should hit the backend.

**Step 3: Seed default settings on startup**

Add to `backend/main.py`, after the app is created:

```python
from backend.database import Base, engine, SessionLocal
from backend.models import Setting
import json

@app.on_event("startup")
def seed_defaults():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    defaults = {
        "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
        "lesson_batch_size": 5,
        "jlpt_gating": True,
        "dependency_gating": True,
        "max_reviews_per_session": None,
    }
    for k, v in defaults.items():
        if not db.query(Setting).filter_by(key=k).first():
            db.add(Setting(key=k, value=json.dumps(v)))
    db.commit()
    db.close()
```

**Step 4: Run all backend tests**

```bash
cd ~/ADHI/projects/kanji-srs && python -m pytest backend/tests/ -v
```

Expected: All tests PASS

**Step 5: End-to-end smoke test**

1. `python -m backend.import_wanikani YOUR_TOKEN` — imports data
2. `cd frontend && npm run build && cd ..`
3. `uvicorn backend.main:app`
4. Open `http://localhost:8000`
5. Dashboard shows lesson count > 0
6. Start a lesson batch, complete quiz
7. Wait for review to become due (or manually set `next_review_at` to past in DB)
8. Complete a review session with typed answers

**Step 6: Commit**

```bash
git add backend/main.py
git commit -m "feat: serve React SPA from FastAPI, seed default settings on startup"
```

---

## Final State

After all 16 tasks, the project at `~/ADHI/projects/kanji-srs/` is a fully functional WaniKani clone with:

- One-time WaniKani data import into SQLite
- JLPT-ordered content (N5 → N1)
- Configurable 9-stage SRS engine
- Typed-answer reviews with romaji→hiragana conversion
- Lesson system with study cards and quiz
- Dashboard with review count, countdown, progress
- Subject browser with search and filters
- Single-command deployment: `uvicorn backend.main:app`

**Total tasks: 16** | **PARALLEL groups: {3,4}, {5,6,9,10,11}, {12,13,14,15}** | **SERIAL chains: 1→2→3→7→14, 1→2→3→8→15**
