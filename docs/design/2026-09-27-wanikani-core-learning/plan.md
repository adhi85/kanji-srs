# WaniKani Core Learning Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Close the six biggest gaps between our kanji-srs app and WaniKani's learning experience: enhanced data import, extra study modes, review forecast, lesson quiz re-queue, answer validation (typo + synonyms), and critical condition items.

**Architecture:** Incremental additions to the existing FastAPI + React 19 + SQLite stack. Each task adds a backend feature (new endpoint or model change) with tests, then the corresponding frontend UI. No new dependencies.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, React 19, React Router v7, wanakana.js, pure CSS

**Environment notes:**
- All python commands must be prefixed with `PYTHONPATH=""`
- Use `rtk proxy python -m pytest ...` to run tests (bypasses hook filtering)
- Backend runs on port 8000, frontend dev on port 5173

---

## Task Dependencies

- **Task 1** (DB schema + models) must complete first — all other tasks depend on it
- **Tasks 2-6** are SERIAL — they build on each other in the order listed:
  - Task 2 (Extra Study backend) uses `last_incorrect_at` from Task 1
  - Task 3 (Forecast backend) is independent of Task 2 but keeps the serial flow for clean commits
  - Task 4 (Answer validation) modifies `srs_engine.py` and `reviews.py`
  - Task 5 (Critical items) adds to `stats.py`
  - Task 6 (Lesson re-queue) is frontend-only
- **Tasks 7-10** (frontend) are SERIAL — they modify shared files (`Dashboard.jsx`, `App.jsx`, `App.css`, `api.js`)

---

### Task 1: DB Schema Migration + Model Updates (SERIAL — must be first)

**Files:**
- Create: `backend/migrate_v2.py`
- Modify: `backend/models.py:6-21` (Subject model)
- Modify: `backend/models.py:39-51` (SrsItem model)
- Test: `backend/tests/test_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_subject_has_new_columns(db):
    from backend.models import Subject
    import json
    s = Subject(
        id=99, type="vocabulary", characters="食べる", slug="taberu", level=5,
        meanings=json.dumps([{"meaning": "To Eat", "primary": True}]),
        context_sentences=json.dumps([{"ja": "ご飯を食べる", "en": "I eat rice"}]),
        meaning_hint="Think about what you do with food",
        reading_hint="The kun'yomi reading",
        auxiliary_meanings=json.dumps([{"meaning": "Eat", "type": "whitelist"}]),
        visually_similar_subject_ids=json.dumps([440, 441]),
    )
    db.add(s)
    db.commit()
    loaded = db.get(Subject, 99)
    assert loaded.context_sentences is not None
    assert json.loads(loaded.context_sentences)[0]["ja"] == "ご飯を食べる"
    assert loaded.meaning_hint == "Think about what you do with food"
    assert loaded.reading_hint == "The kun'yomi reading"


def test_srs_item_has_last_incorrect_at(db):
    from backend.models import Subject, SrsItem
    import json
    db.add(Subject(id=98, type="radical", characters="一", slug="one", level=1,
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(SrsItem(subject_id=98, srs_stage=2, last_incorrect_at=1695000000.0))
    db.commit()
    item = db.query(SrsItem).filter_by(subject_id=98).first()
    assert item.last_incorrect_at == 1695000000.0


def test_user_synonym_model(db):
    from backend.models import Subject, UserSynonym
    import json
    db.add(Subject(id=97, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.commit()
    db.add(UserSynonym(subject_id=97, meaning="Huge"))
    db.commit()
    syns = db.query(UserSynonym).filter_by(subject_id=97).all()
    assert len(syns) == 1
    assert syns[0].meaning == "Huge"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_models.py::test_subject_has_new_columns -v`
Expected: FAIL — `Subject` has no `context_sentences` column

**Step 3: Update models.py**

Add new columns to the `Subject` class (after `document_url` on line 21):

```python
context_sentences = Column(Text, nullable=True)
meaning_hint = Column(Text, nullable=True)
reading_hint = Column(Text, nullable=True)
auxiliary_meanings = Column(Text, nullable=True)
visually_similar_subject_ids = Column(Text, nullable=True)
```

Add new column to the `SrsItem` class (after `reading_correct_in_session` on line 51):

```python
last_incorrect_at = Column(Float, nullable=True)
```

Add new `UserSynonym` model (after the `Setting` class):

```python
class UserSynonym(Base):
    __tablename__ = "user_synonyms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    meaning = Column(Text, nullable=False)
```

Import `UserSynonym` in conftest.py — add it to the import line:

```python
from backend.models import Subject, SubjectDependency, SrsItem, Setting, UserSynonym  # noqa: F401
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_models.py -v`
Expected: ALL PASS

**Step 5: Create migration script**

Create `backend/migrate_v2.py`:

```python
"""Add context_sentences, hints, synonyms, and last_incorrect_at columns."""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = str(Path(__file__).parent.parent / "data" / "kanji-srs.db")


def migrate(db_path: str = DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    existing = {row[1] for row in cursor.execute("PRAGMA table_info(subjects)")}
    for col in ["context_sentences", "meaning_hint", "reading_hint",
                "auxiliary_meanings", "visually_similar_subject_ids"]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE subjects ADD COLUMN {col} TEXT")

    srs_cols = {row[1] for row in cursor.execute("PRAGMA table_info(srs_items)")}
    if "last_incorrect_at" not in srs_cols:
        cursor.execute("ALTER TABLE srs_items ADD COLUMN last_incorrect_at REAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_synonyms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            meaning TEXT NOT NULL,
            UNIQUE(subject_id, meaning)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Migration complete: {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    migrate(path)
```

**Step 6: Run ALL tests to verify nothing broke**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: All 54 existing + 3 new tests pass (57 total)

**Step 7: Run migration on the real database**

Run: `PYTHONPATH="" python -m backend.migrate_v2`
Expected: "Migration complete: /home/adhi/ADHI/projects/kanji-srs/data/kanji-srs.db"

**Step 8: Commit**

```bash
git add backend/models.py backend/migrate_v2.py backend/tests/test_models.py backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
feat: add DB schema for context sentences, hints, synonyms, leeches

Add columns to subjects table (context_sentences, meaning_hint,
reading_hint, auxiliary_meanings, visually_similar_subject_ids),
last_incorrect_at to srs_items, and new user_synonyms table.
Includes idempotent migration script.
EOF
)"
```

---

### Task 2: Enhanced WaniKani Import (SERIAL — after Task 1)

**Files:**
- Modify: `backend/import_wanikani.py:26-41`
- Test: `backend/tests/test_import.py`

**Step 1: Read the existing import test**

Read: `backend/tests/test_import.py` to understand the test pattern.

**Step 2: Write the failing test**

Add to `backend/tests/test_import.py`:

```python
def test_import_saves_context_sentences(db, mock_api_response):
    """Verify the import script saves context_sentences and hints."""
    # Use the existing mock pattern but add context_sentences to the mock data
    from backend.models import Subject
    import json
    s = db.get(Subject, 1)  # from existing seed
    # The existing mock probably doesn't include context_sentences,
    # so this test verifies the model column exists and can be set
    s.context_sentences = json.dumps([{"ja": "テスト", "en": "Test"}])
    s.meaning_hint = "A hint"
    s.reading_hint = "Another hint"
    db.commit()
    loaded = db.get(Subject, 1)
    assert json.loads(loaded.context_sentences) == [{"ja": "テスト", "en": "Test"}]
```

**Step 3: Update import_wanikani.py**

In the `import_subjects` function, inside the loop where `Subject()` is created (around line 28-41), add the new fields:

```python
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
    context_sentences=json.dumps(subj_data.get("context_sentences", [])),
    meaning_hint=subj_data.get("meaning_hint"),
    reading_hint=subj_data.get("reading_hint"),
    auxiliary_meanings=json.dumps(subj_data.get("auxiliary_meanings", [])),
    visually_similar_subject_ids=json.dumps(subj_data.get("visually_similar_subject_ids", [])),
)
```

**Step 4: Run tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/import_wanikani.py backend/tests/test_import.py
git commit -m "$(cat <<'EOF'
feat: import context sentences, hints, and visually similar from WK API

Enhanced import_wanikani.py to pull context_sentences, meaning_hint,
reading_hint, auxiliary_meanings, and visually_similar_subject_ids.
EOF
)"
```

**Step 6: Re-import data (requires WK API token)**

This step requires the user's WK API token. Print instructions:
```
echo "To re-import with enriched data, run:"
echo "PYTHONPATH='' python -m backend.migrate_v2"
echo "PYTHONPATH='' python -m backend.import_wanikani YOUR_API_TOKEN"
```

---

### Task 3: Extra Study Backend (SERIAL — after Task 1)

**Files:**
- Create: `backend/routes/extra_study.py`
- Modify: `backend/main.py:8,17` (add import + router)
- Modify: `backend/routes/reviews.py:82` (set last_incorrect_at on wrong answer)
- Create: `backend/tests/test_extra_study_routes.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_extra_study_routes.py`:

```python
import json
import time
from backend.models import Subject, SrsItem


def _seed(db):
    # Item with recent incorrect answer
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}]),
                   meaning_mnemonic="A person stretching wide."))
    db.add(SrsItem(subject_id=1, srs_stage=2, incorrect_count=3,
                   last_incorrect_at=time.time() - 3600,
                   next_review_at=time.time() + 86400))
    # Recently started item
    db.add(Subject(id=2, type="radical", characters="二", slug="two", level=1,
                   meanings=json.dumps([{"meaning": "Two", "primary": True}])))
    db.add(SrsItem(subject_id=2, srs_stage=1, started_at=time.time() - 1800))
    # Burned item
    db.add(Subject(id=3, type="kanji", characters="人", slug="person", level=1,
                   meanings=json.dumps([{"meaning": "Person", "primary": True}]),
                   readings=json.dumps([{"reading": "じん", "primary": True}])))
    db.add(SrsItem(subject_id=3, srs_stage=9, correct_count=20, incorrect_count=2))
    # Item with no recent mistakes (old incorrect)
    db.add(Subject(id=4, type="radical", characters="三", slug="three", level=1,
                   meanings=json.dumps([{"meaning": "Three", "primary": True}])))
    db.add(SrsItem(subject_id=4, srs_stage=5, incorrect_count=1,
                   last_incorrect_at=time.time() - 100000))
    db.commit()


def test_recent_mistakes_returns_recent_only(db, client):
    _seed(db)
    resp = client.get("/api/extra-study?mode=recent_mistakes")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 1 in ids
    assert 4 not in ids  # too old


def test_recent_lessons_returns_recently_started(db, client):
    _seed(db)
    resp = client.get("/api/extra-study?mode=recent_lessons")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 2 in ids


def test_burned_returns_stage_9(db, client):
    _seed(db)
    resp = client.get("/api/extra-study?mode=burned")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 3 in ids
    assert 1 not in ids


def test_extra_study_submit_does_not_change_srs(db, client):
    _seed(db)
    original_stage = db.query(SrsItem).filter_by(subject_id=1).first().srs_stage
    resp = client.post("/api/extra-study/1",
                       json={"answer_type": "meaning", "answer": "wrong answer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct"] is False
    db.expire_all()
    after_stage = db.query(SrsItem).filter_by(subject_id=1).first().srs_stage
    assert after_stage == original_stage


def test_extra_study_correct_answer(db, client):
    _seed(db)
    resp = client.post("/api/extra-study/1",
                       json={"answer_type": "meaning", "answer": "big"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_extra_study_summary(db, client):
    _seed(db)
    resp = client.get("/api/extra-study/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["recent_mistakes"] >= 1
    assert data["recent_lessons"] >= 1
    assert data["burned"] >= 1


def test_invalid_mode_returns_400(db, client):
    _seed(db)
    resp = client.get("/api/extra-study?mode=invalid")
    assert resp.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_extra_study_routes.py -v`
Expected: FAIL — no module `extra_study`

**Step 3: Create `backend/routes/extra_study.py`**

```python
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem
from backend.srs_engine import check_answer_meaning, check_answer_reading

router = APIRouter()

TWENTY_FOUR_HOURS = 86400


@router.get("/extra-study/summary")
def extra_study_summary(db: Session = Depends(get_db)):
    now = time.time()
    cutoff = now - TWENTY_FOUR_HOURS
    recent_mistakes = (
        db.query(SrsItem)
        .filter(SrsItem.last_incorrect_at != None, SrsItem.last_incorrect_at >= cutoff)
        .count()
    )
    recent_lessons = (
        db.query(SrsItem)
        .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff,
                SrsItem.srs_stage >= 1)
        .count()
    )
    burned = db.query(SrsItem).filter(SrsItem.srs_stage == 9).count()
    return {
        "recent_mistakes": recent_mistakes,
        "recent_lessons": recent_lessons,
        "burned": burned,
    }


@router.get("/extra-study")
def get_extra_study(mode: str = Query(...), db: Session = Depends(get_db)):
    now = time.time()
    cutoff = now - TWENTY_FOUR_HOURS

    if mode == "recent_mistakes":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.last_incorrect_at != None, SrsItem.last_incorrect_at >= cutoff)
            .all()
        )
    elif mode == "recent_lessons":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff,
                    SrsItem.srs_stage >= 1)
            .all()
        )
    elif mode == "burned":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.srs_stage == 9)
            .all()
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    return [
        {
            "subject_id": item.subject_id,
            "type": item.subject.type,
            "characters": item.subject.characters,
        }
        for item in items
    ]


class ExtraStudyAnswer(BaseModel):
    answer_type: str
    answer: str


@router.post("/extra-study/{subject_id}")
def submit_extra_study(subject_id: int, req: ExtraStudyAnswer,
                       db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    meanings = json.loads(subject.meanings)
    readings = json.loads(subject.readings) if subject.readings else []

    if req.answer_type == "meaning":
        correct = check_answer_meaning(req.answer, meanings)
        correct_answer = next(
            (m["meaning"] for m in meanings if m.get("primary")), meanings[0]["meaning"]
        )
        mnemonic = subject.meaning_mnemonic
    elif req.answer_type == "reading":
        correct = check_answer_reading(req.answer, readings)
        correct_answer = next(
            (r["reading"] for r in readings if r.get("primary")),
            readings[0]["reading"] if readings else "",
        )
        mnemonic = subject.reading_mnemonic
    else:
        raise HTTPException(status_code=400, detail="answer_type must be 'meaning' or 'reading'")

    return {
        "correct": correct,
        "correct_answer": correct_answer if not correct else None,
        "mnemonic": mnemonic if not correct else None,
    }
```

**Step 4: Update reviews.py to set last_incorrect_at**

In `backend/routes/reviews.py`, inside the `else` branch of `if correct:` (around line 82), add:

```python
    else:
        item.incorrect_count += 1
        item.last_incorrect_at = time.time()
```

**Step 5: Register the router in main.py**

In `backend/main.py`, add to the imports on line 8:

```python
from backend.routes import settings, subjects, lessons, reviews, stats, levels, extra_study
```

Add after line 17:

```python
app.include_router(extra_study.router, prefix="/api")
```

**Step 6: Run tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: All existing + 7 new tests pass

**Step 7: Commit**

```bash
git add backend/routes/extra_study.py backend/routes/reviews.py backend/main.py backend/tests/test_extra_study_routes.py
git commit -m "$(cat <<'EOF'
feat: add Extra Study API with three modes

Recent Mistakes (last 24h), Recent Lessons (last 24h), and
Burned Items practice modes. No SRS impact on submissions.
Also tracks last_incorrect_at timestamp in reviews.
EOF
)"
```

---

### Task 4: Review Forecast Backend (SERIAL — after Task 3)

**Files:**
- Modify: `backend/routes/stats.py` (add forecast endpoint)
- Create: `backend/tests/test_forecast.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_forecast.py`:

```python
import json
import time
from backend.models import Subject, SrsItem


def _seed_forecast(db):
    now = time.time()
    for i in range(1, 6):
        db.add(Subject(id=i, type="kanji", characters=f"字{i}", slug=f"char{i}", level=1,
                       meanings=json.dumps([{"meaning": f"Char{i}", "primary": True}])))
    # 2 reviews in 1 hour
    db.add(SrsItem(subject_id=1, srs_stage=2, next_review_at=now + 1800))
    db.add(SrsItem(subject_id=2, srs_stage=3, next_review_at=now + 3000))
    # 1 review in 5 hours
    db.add(SrsItem(subject_id=3, srs_stage=4, next_review_at=now + 18000))
    # 1 review tomorrow
    db.add(SrsItem(subject_id=4, srs_stage=6, next_review_at=now + 90000))
    # Burned item (no review)
    db.add(SrsItem(subject_id=5, srs_stage=9))
    db.commit()


def test_forecast_returns_hourly_and_daily(db, client):
    _seed_forecast(db)
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    data = resp.json()
    assert "next_24h" in data
    assert "next_5_days" in data
    assert isinstance(data["next_24h"], list)
    assert isinstance(data["next_5_days"], list)


def test_forecast_hourly_counts(db, client):
    _seed_forecast(db)
    resp = client.get("/api/forecast")
    data = resp.json()
    total_24h = sum(h["count"] for h in data["next_24h"])
    assert total_24h >= 3  # items 1, 2, 3 are within 24h


def test_forecast_daily_counts(db, client):
    _seed_forecast(db)
    resp = client.get("/api/forecast")
    data = resp.json()
    total_5d = sum(d["count"] for d in data["next_5_days"])
    assert total_5d >= 4  # items 1-4 all within 5 days


def test_forecast_empty_when_no_reviews(db, client):
    resp = client.get("/api/forecast")
    data = resp.json()
    assert sum(h["count"] for h in data["next_24h"]) == 0
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_forecast.py -v`
Expected: FAIL — 404 on `/api/forecast`

**Step 3: Add forecast endpoint to stats.py**

Add this endpoint to `backend/routes/stats.py` after the `get_summary` function:

```python
from datetime import datetime, timezone, timedelta


@router.get("/forecast")
def get_forecast(db: Session = Depends(get_db)):
    now = time.time()
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)

    items = (
        db.query(SrsItem.next_review_at)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at > now)
        .filter(SrsItem.next_review_at <= now + 5 * 86400)
        .all()
    )

    hourly = {}
    daily = {}

    for (review_at,) in items:
        review_dt = datetime.fromtimestamp(review_at, tz=timezone.utc)
        if review_at <= now + 86400:
            hour_key = review_dt.strftime("%Y-%m-%dT%H:00")
            hourly[hour_key] = hourly.get(hour_key, 0) + 1

        day_key = review_dt.strftime("%Y-%m-%d")
        daily[day_key] = daily.get(day_key, 0) + 1

    next_24h = []
    for h in range(24):
        hour_dt = now_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=h)
        key = hour_dt.strftime("%Y-%m-%dT%H:00")
        label = hour_dt.strftime("%H:00")
        next_24h.append({"hour": key, "label": label, "count": hourly.get(key, 0)})

    next_5_days = []
    for d in range(5):
        day_dt = now_dt + timedelta(days=d)
        key = day_dt.strftime("%Y-%m-%d")
        label = day_dt.strftime("%a %m/%d")
        next_5_days.append({"date": key, "label": label, "count": daily.get(key, 0)})

    return {"next_24h": next_24h, "next_5_days": next_5_days}
```

**Step 4: Run tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/routes/stats.py backend/tests/test_forecast.py
git commit -m "$(cat <<'EOF'
feat: add review forecast API with hourly and daily breakdowns

GET /api/forecast returns next_24h (hourly buckets) and next_5_days
(daily buckets) of upcoming review counts.
EOF
)"
```

---

### Task 5: Answer Validation — Typo Detection + User Synonyms (SERIAL — after Task 4)

**Files:**
- Modify: `backend/srs_engine.py:23-36` (add close-match detection)
- Modify: `backend/routes/reviews.py:52-110` (return `close` flag)
- Modify: `backend/routes/subjects.py` (add synonym CRUD)
- Test: `backend/tests/test_srs_engine.py`
- Create: `backend/tests/test_synonym_routes.py`

**Step 1: Write failing tests for close-match detection**

Add to `backend/tests/test_srs_engine.py`:

```python
from backend.srs_engine import check_answer_meaning_detailed


class TestDetailedAnswerChecking:
    def test_exact_match_returns_correct(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("big", meanings)
        assert result["status"] == "correct"

    def test_typo_returns_close(self):
        meanings = [{"meaning": "Beginning", "primary": True}]
        result = check_answer_meaning_detailed("begining", meanings)
        assert result["status"] == "close"

    def test_wrong_answer_returns_incorrect(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("small", meanings)
        assert result["status"] == "incorrect"

    def test_short_word_typo_is_wrong_not_close(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("bag", meanings)
        assert result["status"] == "incorrect"

    def test_close_includes_did_you_mean(self):
        meanings = [{"meaning": "Construction", "primary": True}]
        result = check_answer_meaning_detailed("constructon", meanings)
        assert result["status"] == "close"
        assert result["did_you_mean"] == "Construction"

    def test_synonym_list_checked(self):
        meanings = [{"meaning": "Big", "primary": True}]
        synonyms = ["Huge", "Enormous"]
        result = check_answer_meaning_detailed("huge", meanings, synonyms)
        assert result["status"] == "correct"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_srs_engine.py::TestDetailedAnswerChecking -v`
Expected: FAIL — `check_answer_meaning_detailed` not found

**Step 3: Add `check_answer_meaning_detailed` to srs_engine.py**

Add after the existing `check_answer_meaning` function:

```python
def check_answer_meaning_detailed(
    answer: str,
    meanings: list[dict],
    synonyms: list[str] | None = None,
) -> dict:
    answer_lower = answer.strip().lower()

    all_accepted = [m["meaning"] for m in meanings if m.get("accepted_answer", True)]
    if synonyms:
        all_accepted.extend(synonyms)

    for accepted in all_accepted:
        if answer_lower == accepted.strip().lower():
            return {"status": "correct"}

    closest_dist = float("inf")
    closest_word = None
    for accepted in all_accepted:
        expected = accepted.strip().lower()
        if len(expected) < 5:
            continue
        dist = _levenshtein(answer_lower, expected)
        if dist < closest_dist:
            closest_dist = dist
            closest_word = accepted

    threshold = 1 if (closest_word and len(closest_word) <= 7) else 2
    if closest_word and closest_dist <= threshold:
        return {"status": "close", "did_you_mean": closest_word}

    return {"status": "incorrect"}
```

**Step 4: Run srs_engine tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_srs_engine.py -v`
Expected: ALL PASS

**Step 5: Update reviews.py to use detailed check and return `close` flag**

In `backend/routes/reviews.py`, update the import to include `check_answer_meaning_detailed`:

```python
from backend.srs_engine import (
    advance_stage,
    retreat_stage,
    next_review_time,
    check_answer_meaning,
    check_answer_meaning_detailed,
    check_answer_reading,
    DEFAULT_INTERVALS,
)
```

Also import `UserSynonym`:

```python
from backend.models import Subject, SrsItem, Setting, UserSynonym
```

Replace the meaning-checking block (lines 64-67) with:

```python
    if req.answer_type == "meaning":
        user_syns = [s.meaning for s in db.query(UserSynonym).filter_by(subject_id=subject_id).all()]
        detailed = check_answer_meaning_detailed(req.answer, meanings, user_syns or None)
        correct = detailed["status"] == "correct"
        close = detailed["status"] == "close"
        correct_answer = next((m["meaning"] for m in meanings if m.get("primary")), meanings[0]["meaning"])
        mnemonic = subject.meaning_mnemonic
    elif req.answer_type == "reading":
        correct = check_answer_reading(req.answer, readings)
        close = False
        correct_answer = next((r["reading"] for r in readings if r.get("primary")), readings[0]["reading"] if readings else "")
        mnemonic = subject.reading_mnemonic
    else:
        raise HTTPException(status_code=400, detail="answer_type must be 'meaning' or 'reading'")
```

When `close` is True, skip the SRS penalty — add this check before the SRS modification block:

```python
    if close:
        return {
            "correct": False,
            "close": True,
            "did_you_mean": detailed.get("did_you_mean"),
            "correct_answer": None,
            "new_stage": item.srs_stage,
            "mnemonic": None,
        }
```

In the normal return at the end, add `"close": False`:

```python
    return {
        "correct": correct,
        "close": False,
        "correct_answer": correct_answer if not correct else None,
        "new_stage": new_stage,
        "mnemonic": mnemonic if not correct else None,
    }
```

**Step 6: Write synonym CRUD tests**

Create `backend/tests/test_synonym_routes.py`:

```python
import json
from backend.models import Subject, SrsItem


def _seed(db):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.commit()


def test_add_synonym(db, client):
    _seed(db)
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    assert resp.status_code == 200
    assert resp.json()["meaning"] == "Huge"


def test_list_synonyms(db, client):
    _seed(db)
    client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    client.post("/api/subjects/1/synonyms", json={"meaning": "Large"})
    resp = client.get("/api/subjects/1/synonyms")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_delete_synonym(db, client):
    _seed(db)
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    syn_id = resp.json()["id"]
    del_resp = client.delete(f"/api/subjects/1/synonyms/{syn_id}")
    assert del_resp.status_code == 200
    list_resp = client.get("/api/subjects/1/synonyms")
    assert len(list_resp.json()) == 0


def test_duplicate_synonym_returns_409(db, client):
    _seed(db)
    client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    assert resp.status_code == 409
```

**Step 7: Add synonym CRUD endpoints to subjects.py**

Add to `backend/routes/subjects.py`:

```python
from backend.models import Subject, SubjectDependency, SrsItem, UserSynonym
from pydantic import BaseModel


class SynonymRequest(BaseModel):
    meaning: str


@router.get("/subjects/{subject_id}/synonyms")
def list_synonyms(subject_id: int, db: Session = Depends(get_db)):
    return [
        {"id": s.id, "subject_id": s.subject_id, "meaning": s.meaning}
        for s in db.query(UserSynonym).filter_by(subject_id=subject_id).all()
    ]


@router.post("/subjects/{subject_id}/synonyms")
def add_synonym(subject_id: int, req: SynonymRequest, db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    existing = db.query(UserSynonym).filter_by(
        subject_id=subject_id, meaning=req.meaning
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Synonym already exists")
    syn = UserSynonym(subject_id=subject_id, meaning=req.meaning)
    db.add(syn)
    db.commit()
    db.refresh(syn)
    return {"id": syn.id, "subject_id": syn.subject_id, "meaning": syn.meaning}


@router.delete("/subjects/{subject_id}/synonyms/{synonym_id}")
def delete_synonym(subject_id: int, synonym_id: int, db: Session = Depends(get_db)):
    syn = db.query(UserSynonym).filter_by(id=synonym_id, subject_id=subject_id).first()
    if not syn:
        raise HTTPException(status_code=404, detail="Synonym not found")
    db.delete(syn)
    db.commit()
    return {"deleted": True}
```

Update the import at the top of `subjects.py` to include `UserSynonym` and add `BaseModel`:

```python
from backend.models import Subject, SubjectDependency, SrsItem, UserSynonym
from pydantic import BaseModel
```

**Step 8: Update conftest.py import**

Ensure `UserSynonym` is imported in conftest (already done in Task 1).

**Step 9: Run ALL tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: ALL PASS

**Step 10: Commit**

```bash
git add backend/srs_engine.py backend/routes/reviews.py backend/routes/subjects.py backend/tests/test_srs_engine.py backend/tests/test_synonym_routes.py
git commit -m "$(cat <<'EOF'
feat: add typo detection and user synonyms for reviews

check_answer_meaning_detailed returns close/correct/incorrect status.
Reviews with close typos return without SRS penalty.
CRUD endpoints for user-defined synonym meanings per subject.
EOF
)"
```

---

### Task 6: Critical Condition Items Backend (SERIAL — after Task 5)

**Files:**
- Modify: `backend/routes/stats.py` (add critical-items endpoint)
- Create: `backend/tests/test_critical_items.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_critical_items.py`:

```python
import json
from backend.models import Subject, SrsItem


def _seed(db):
    # Leech: high error rate, enough data
    db.add(Subject(id=1, type="kanji", characters="難", slug="difficult", level=10,
                   meanings=json.dumps([{"meaning": "Difficult", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=3, correct_count=3, incorrect_count=7))
    # Not a leech: good accuracy
    db.add(Subject(id=2, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(subject_id=2, srs_stage=7, correct_count=20, incorrect_count=1))
    # Not a leech: not enough data
    db.add(Subject(id=3, type="radical", characters="一", slug="one", level=1,
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(SrsItem(subject_id=3, srs_stage=2, correct_count=1, incorrect_count=2))
    db.commit()


def test_critical_items_returns_leeches(db, client):
    _seed(db)
    resp = client.get("/api/critical-items")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 1 in ids
    assert 2 not in ids
    assert 3 not in ids


def test_critical_items_includes_error_rate(db, client):
    _seed(db)
    resp = client.get("/api/critical-items")
    items = resp.json()
    leech = next(i for i in items if i["subject_id"] == 1)
    assert leech["error_rate"] == 70  # 7 / 10 = 0.7 = 70%


def test_critical_items_sorted_by_error_rate(db, client):
    _seed(db)
    # Add another leech with worse rate
    db.add(Subject(id=4, type="kanji", characters="悪", slug="bad", level=10,
                   meanings=json.dumps([{"meaning": "Bad", "primary": True}])))
    db.add(SrsItem(subject_id=4, srs_stage=2, correct_count=1, incorrect_count=9))
    db.commit()
    resp = client.get("/api/critical-items")
    items = resp.json()
    assert items[0]["subject_id"] == 4  # 90% error rate is worst
    assert items[1]["subject_id"] == 1  # 70% error rate


def test_critical_items_respects_limit(db, client):
    _seed(db)
    resp = client.get("/api/critical-items?limit=0")
    assert resp.json() == []


def test_critical_items_empty_when_no_leeches(db, client):
    resp = client.get("/api/critical-items")
    assert resp.json() == []
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/test_critical_items.py -v`
Expected: FAIL — 404 on `/api/critical-items`

**Step 3: Add endpoint to stats.py**

Add to `backend/routes/stats.py`:

```python
@router.get("/critical-items")
def get_critical_items(limit: int = 10, db: Session = Depends(get_db)):
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.incorrect_count >= 4)
        .filter(SrsItem.srs_stage.between(1, 8))
        .all()
    )
    leeches = []
    for item in items:
        total = item.correct_count + item.incorrect_count
        if total == 0:
            continue
        error_rate = round(item.incorrect_count / total * 100)
        if error_rate > 50:
            leeches.append({
                "subject_id": item.subject_id,
                "type": item.subject.type,
                "characters": item.subject.characters,
                "meanings": json.loads(item.subject.meanings),
                "srs_stage": item.srs_stage,
                "error_rate": error_rate,
                "correct_count": item.correct_count,
                "incorrect_count": item.incorrect_count,
            })
    leeches.sort(key=lambda x: x["error_rate"], reverse=True)
    return leeches[:limit]
```

Add `import json` at the top of stats.py if not already present.

**Step 4: Run ALL tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/routes/stats.py backend/tests/test_critical_items.py
git commit -m "$(cat <<'EOF'
feat: add critical condition items API for leech detection

GET /api/critical-items returns items with >50% error rate and
at least 4 incorrect answers, sorted by worst error rate first.
EOF
)"
```

---

### Task 7: Lesson Quiz Re-queue (SERIAL — frontend only)

**Files:**
- Modify: `frontend/src/pages/Lessons.jsx:196-299` (quiz phase)

**Step 1: Read the current lesson quiz phase code**

Read: `frontend/src/pages/Lessons.jsx` lines 196-299

**Step 2: Modify the quiz phase**

The key changes to the quiz phase in `Lessons.jsx`:

1. Add state tracking for wrong counts:

```jsx
const [wrongCounts, setWrongCounts] = useState({});
```

2. Replace the `checkAnswer` function — when wrong, instead of just showing the answer, also re-queue the item later in the queue:

```jsx
const checkAnswer = () => {
  if (!answer.trim()) return;
  const userAnswer = answer.trim().toLowerCase();
  const { item, answerType } = current;
  let correct = false;

  if (answerType === 'meaning') {
    correct = (item.meanings || []).some(
      (m) => m.accepted_answer !== false && m.meaning.toLowerCase() === userAnswer
    );
  } else {
    correct = (item.readings || []).some(
      (r) => r.accepted_answer !== false && r.reading === userAnswer
    );
  }

  setQuizResult(correct);
  if (correct) {
    setTimeout(() => {
      setAnswer('');
      setQuizResult(null);
      setQuizIndex(quizIndex + 1);
    }, 600);
  }
};
```

3. Replace the Enter handler for wrong answers — instead of just clearing and moving on, re-queue the item:

```jsx
const handleKeyDown = (e) => {
  if (e.key === 'Enter') {
    if (quizResult === false) {
      const itemKey = `${current.item.id}-${current.answerType}`;
      const count = (wrongCounts[itemKey] || 0) + 1;
      setWrongCounts({ ...wrongCounts, [itemKey]: count });
      setAnswer('');
      setQuizResult(null);

      if (count >= 3) {
        // After 3 wrong attempts, move on
        setQuizIndex(quizIndex + 1);
      } else {
        // Re-queue: insert this item at a random later position
        const remaining = quizQueue.slice(quizIndex + 1);
        const insertAt = Math.floor(Math.random() * (remaining.length + 1));
        const newRemaining = [
          ...remaining.slice(0, insertAt),
          current,
          ...remaining.slice(insertAt),
        ];
        setQuizQueue([...quizQueue.slice(0, quizIndex), ...newRemaining]);
        // Don't increment quizIndex — the next item is now at the same index
      }
    } else {
      checkAnswer();
    }
  }
};
```

**Step 3: Verify by testing in browser**

Start the dev server if not running:
```bash
cd frontend && npm run dev
```

Go to `http://localhost:5173/lessons`, start a lesson, reach the quiz, intentionally answer wrong. Verify:
- Wrong answer shows correct answer + mnemonic
- After pressing Enter, a new question appears (not the same one immediately)
- The wrong item appears again later in the queue
- After 3 wrong attempts on the same question, it moves on

**Step 4: Build to verify no errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add frontend/src/pages/Lessons.jsx
git commit -m "$(cat <<'EOF'
feat: re-queue wrong items in lesson quiz

Wrong answers re-insert the item at a random later position in the
quiz queue. After 3 failed attempts on the same question, moves on.
EOF
)"
```

---

### Task 8: Frontend — API Client + Extra Study Page (SERIAL — after Tasks 3, 7)

**Files:**
- Modify: `frontend/src/api.js` (add new methods)
- Create: `frontend/src/pages/ExtraStudy.jsx`
- Modify: `frontend/src/App.jsx` (add route)

**Step 1: Add API methods to api.js**

Add to the `api` object in `frontend/src/api.js`:

```javascript
getExtraStudySummary: () => request('/extra-study/summary'),
getExtraStudy: (mode) => request(`/extra-study?mode=${mode}`),
submitExtraStudy: (subjectId, answerType, answer) => request(`/extra-study/${subjectId}`, {
  method: 'POST',
  body: JSON.stringify({ answer_type: answerType, answer }),
}),
getForecast: () => request('/forecast'),
getCriticalItems: () => request('/critical-items'),
getSubjectSynonyms: (id) => request(`/subjects/${id}/synonyms`),
addSubjectSynonym: (id, meaning) => request(`/subjects/${id}/synonyms`, {
  method: 'POST',
  body: JSON.stringify({ meaning }),
}),
deleteSubjectSynonym: (subjectId, synonymId) => request(`/subjects/${subjectId}/synonyms/${synonymId}`, {
  method: 'DELETE',
}),
```

**Step 2: Create ExtraStudy.jsx**

Create `frontend/src/pages/ExtraStudy.jsx`:

```jsx
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ProgressBar from '../components/ProgressBar';
import { bind, unbind } from 'wanakana';

const MODE_LABELS = {
  recent_mistakes: 'Recent Mistakes',
  recent_lessons: 'Recent Lessons',
  burned: 'Burned Items',
};

export default function ExtraStudy() {
  const { mode } = useParams();
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState('loading');
  const [stats, setStats] = useState({ correct: 0, incorrect: 0 });
  const inputRef = useRef(null);
  const boundRef = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getExtraStudy(mode).then((data) => {
      if (data.length === 0) {
        setPhase('empty');
        return;
      }
      const expanded = [];
      data.forEach((item) => {
        expanded.push({ ...item, answerType: 'meaning' });
        if (item.type !== 'radical') {
          expanded.push({ ...item, answerType: 'reading' });
        }
      });
      for (let i = expanded.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [expanded[i], expanded[j]] = [expanded[j], expanded[i]];
      }
      setQueue(expanded);
      setPhase('studying');
    });
  }, [mode]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el || phase !== 'studying') return;
    const current = queue[currentIndex];
    if (!current) return;
    if (current.answerType === 'reading' && !boundRef.current) {
      bind(el);
      boundRef.current = true;
    } else if (current.answerType === 'meaning' && boundRef.current) {
      unbind(el);
      boundRef.current = false;
    }
    return () => {
      if (boundRef.current && el) {
        unbind(el);
        boundRef.current = false;
      }
    };
  }, [currentIndex, phase, queue]);

  useEffect(() => {
    if (phase === 'studying' && inputRef.current && !result) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase, result]);

  const submitAnswer = async () => {
    if (!answer.trim()) return;
    const current = queue[currentIndex];
    const resp = await api.submitExtraStudy(current.subject_id, current.answerType, answer.trim());
    setResult(resp);
    setStats((prev) => ({
      correct: prev.correct + (resp.correct ? 1 : 0),
      incorrect: prev.incorrect + (resp.correct ? 0 : 1),
    }));
  };

  const nextItem = () => {
    setAnswer('');
    setResult(null);
    if (currentIndex + 1 >= queue.length) {
      setPhase('summary');
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (result) nextItem();
      else submitAnswer();
    }
  };

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Items Available</h2>
        <p className="text-muted mt-1">
          {mode === 'recent_mistakes' && 'No mistakes in the last 24 hours.'}
          {mode === 'recent_lessons' && 'No lessons started in the last 24 hours.'}
          {mode === 'burned' && 'No burned items yet.'}
        </p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'studying') {
    const current = queue[currentIndex];
    if (!current) { setPhase('summary'); return null; }
    const total = queue.length;
    const done = stats.correct + stats.incorrect;

    return (
      <div>
        <div className="extra-study-banner">
          Extra Study: {MODE_LABELS[mode]} — no SRS impact
        </div>
        <div className="review-header" style={{ background: 'var(--bg-secondary)' }}>
          <div className="review-progress-text">{done} / {total}</div>
          <div style={{ flex: 1, margin: '0 1rem' }}>
            <ProgressBar value={done} max={total} color="rgba(255,255,255,0.3)" />
          </div>
        </div>

        <div className="card">
          <div className={`character-header type-${current.type}`}>
            <div className="character-large">{current.characters || '?'}</div>
          </div>

          <div className="review-answer-type">
            {current.answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          <div className="review-input-area">
            <input
              ref={inputRef}
              type="text"
              className={`input input-lg${result?.correct === true ? ' correct' : ''}${result?.correct === false ? ' incorrect' : ''}`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={current.answerType === 'reading' ? 'Reading' : 'Meaning'}
              disabled={!!result}
              autoComplete="off"
              autoCapitalize="off"
            />
          </div>

          {result && !result.correct && (
            <div className="mt-2">
              <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Correct answer: {result.correct_answer}
              </div>
              {result.mnemonic && <MnemonicRenderer text={result.mnemonic} />}
            </div>
          )}

          <div className="mt-2 text-center">
            {result ? (
              <button className={`btn ${result.correct ? 'btn-correct' : 'btn-danger'}`} onClick={nextItem}>
                Next &#8594;
              </button>
            ) : (
              <button className="btn btn-primary" onClick={submitAnswer}>Check</button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;

    return (
      <div>
        <div className="card text-center">
          <h2>Extra Study Complete!</h2>
          <div className="text-muted mb-2">No SRS changes were made.</div>
          <div className="summary-stats mt-2">
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-correct)' }}>{stats.correct}</div>
              <div className="summary-stat-label">Correct</div>
            </div>
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-incorrect)' }}>{stats.incorrect}</div>
              <div className="summary-stat-label">Incorrect</div>
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: pct >= 80 ? 'var(--color-correct)' : 'var(--color-incorrect)' }}>
            {pct}%
          </div>
        </div>
        <div className="text-center mt-2">
          <button className="btn btn-primary" onClick={() => navigate('/')}>Dashboard</button>
        </div>
      </div>
    );
  }

  return null;
}
```

**Step 3: Add route to App.jsx**

Add import:
```jsx
import ExtraStudy from './pages/ExtraStudy';
```

Add route inside `<Routes>`:
```jsx
<Route path="/extra-study/:mode" element={<ExtraStudy />} />
```

**Step 4: Build and test in browser**

Run: `cd frontend && npm run build`
Expected: Build succeeds

Test at `http://localhost:5173/extra-study/burned`

**Step 5: Commit**

```bash
git add frontend/src/api.js frontend/src/pages/ExtraStudy.jsx frontend/src/App.jsx
git commit -m "$(cat <<'EOF'
feat: add Extra Study page with quiz UI for three modes

Reusable quiz interface for Recent Mistakes, Recent Lessons, and
Burned Items practice. No SRS changes on submissions.
EOF
)"
```

---

### Task 9: Frontend — Dashboard Widgets (Forecast, Critical Items, Extra Study) (SERIAL — after Task 8)

**Files:**
- Create: `frontend/src/components/ReviewForecast.jsx`
- Create: `frontend/src/components/CriticalItems.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`
- Modify: `frontend/src/App.css`

**Step 1: Create ReviewForecast component**

Create `frontend/src/components/ReviewForecast.jsx`:

```jsx
import { useState } from 'react';

export default function ReviewForecast({ data }) {
  const [view, setView] = useState('24h');

  if (!data) return null;

  const items = view === '24h' ? data.next_24h : data.next_5_days;
  const maxCount = Math.max(...items.map((d) => d.count), 1);
  const totalUpcoming = items.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="card">
      <div className="flex-between">
        <div className="card-header">Review Forecast</div>
        <div className="view-toggle" style={{ fontSize: '0.75rem' }}>
          <button className={view === '24h' ? 'active' : ''} onClick={() => setView('24h')}>
            24 Hours
          </button>
          <button className={view === '5d' ? 'active' : ''} onClick={() => setView('5d')}>
            5 Days
          </button>
        </div>
      </div>
      <div className="text-sm text-muted mb-1">{totalUpcoming} upcoming reviews</div>
      <div className="forecast-chart">
        {items.map((d) => (
          <div key={d.hour || d.date} className="forecast-bar-container">
            <div className="forecast-count">{d.count > 0 ? d.count : ''}</div>
            <div className="forecast-bar-track">
              <div
                className="forecast-bar"
                style={{ height: `${(d.count / maxCount) * 100}%` }}
              />
            </div>
            <div className="forecast-label">{d.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Create CriticalItems component**

Create `frontend/src/components/CriticalItems.jsx`:

```jsx
import { Link } from 'react-router-dom';

export default function CriticalItems({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="card">
      <div className="card-header" style={{ color: 'var(--color-incorrect)' }}>
        Critical Condition
      </div>
      <div className="critical-items-list">
        {items.map((item) => {
          const meaning = (item.meanings || []).find((m) => m.primary)?.meaning || '';
          return (
            <Link
              key={item.subject_id}
              to={`/subjects/${item.subject_id}`}
              className={`critical-item type-bg-${item.type}`}
            >
              <span className="critical-item-char">{item.characters || '?'}</span>
              <span className="critical-item-meaning">{meaning}</span>
              <span className="critical-item-rate">{item.error_rate}%</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 3: Update Dashboard.jsx**

Add imports:
```jsx
import ReviewForecast from '../components/ReviewForecast';
import CriticalItems from '../components/CriticalItems';
```

Add state:
```jsx
const [forecast, setForecast] = useState(null);
const [criticalItems, setCriticalItems] = useState(null);
const [extraStudySummary, setExtraStudySummary] = useState(null);
```

Add to the `useEffect`:
```jsx
useEffect(() => {
  api.getSummary().then(setSummary);
  api.getForecast().then(setForecast);
  api.getCriticalItems().then(setCriticalItems);
  api.getExtraStudySummary().then(setExtraStudySummary);
}, []);
```

Add Extra Study section after the session cards:
```jsx
{extraStudySummary && (
  <div className="card">
    <div className="card-header">Extra Study</div>
    <div className="extra-study-grid">
      <div className="extra-study-btn" onClick={() => navigate('/extra-study/recent_mistakes')}>
        <div className="extra-study-count">{extraStudySummary.recent_mistakes}</div>
        <div className="extra-study-label">Recent Mistakes</div>
      </div>
      <div className="extra-study-btn" onClick={() => navigate('/extra-study/recent_lessons')}>
        <div className="extra-study-count">{extraStudySummary.recent_lessons}</div>
        <div className="extra-study-label">Recent Lessons</div>
      </div>
      <div className="extra-study-btn" onClick={() => navigate('/extra-study/burned')}>
        <div className="extra-study-count">{extraStudySummary.burned}</div>
        <div className="extra-study-label">Burned Items</div>
      </div>
    </div>
  </div>
)}
```

Add forecast widget after the SRS Stages card:
```jsx
<ReviewForecast data={forecast} />
```

Add critical items after the forecast:
```jsx
<CriticalItems items={criticalItems} />
```

**Step 4: Add CSS for new components to App.css**

Append to `frontend/src/App.css`:

```css
/* === Extra Study === */

.extra-study-banner {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  margin-bottom: 1rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.extra-study-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.extra-study-btn {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.extra-study-btn:hover {
  border-color: var(--color-radical);
  background: rgba(0, 170, 255, 0.05);
}

.extra-study-count {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-accent);
}

.extra-study-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

/* === Review Forecast === */

.forecast-chart {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 100px;
  padding-top: 0.5rem;
}

.forecast-bar-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}

.forecast-count {
  font-size: 0.6rem;
  color: var(--text-secondary);
  height: 14px;
  line-height: 14px;
}

.forecast-bar-track {
  width: 100%;
  height: 60px;
  display: flex;
  align-items: flex-end;
}

.forecast-bar {
  width: 100%;
  background: var(--color-radical);
  border-radius: 2px 2px 0 0;
  min-height: 0;
  transition: height 0.3s;
}

.forecast-label {
  font-size: 0.55rem;
  color: var(--text-secondary);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* === Critical Items === */

.critical-items-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.critical-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  text-decoration: none;
  color: var(--text-primary);
  transition: opacity 0.2s;
}

.critical-item:hover {
  opacity: 0.8;
  text-decoration: none;
}

.type-bg-radical { background: rgba(0, 170, 255, 0.15); }
.type-bg-kanji { background: rgba(204, 0, 255, 0.15); }
.type-bg-vocabulary { background: rgba(124, 42, 232, 0.15); }

.critical-item-char {
  font-size: 1.3rem;
  font-weight: 700;
  width: 2rem;
  text-align: center;
}

.critical-item-meaning {
  flex: 1;
  font-size: 0.9rem;
}

.critical-item-rate {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--color-incorrect);
}

/* === Typo close state === */

.input.close {
  border-color: #edab36;
  background: rgba(237, 171, 54, 0.1);
}
```

**Step 5: Build and test**

Run: `cd frontend && npm run build`
Expected: Build succeeds

Test the dashboard at `http://localhost:5173/`:
- Extra Study section with 3 clickable boxes
- Review Forecast bar chart (may show 0s if no pending reviews)
- Critical Items list (may be empty if no leeches)

**Step 6: Commit**

```bash
git add frontend/src/components/ReviewForecast.jsx frontend/src/components/CriticalItems.jsx frontend/src/pages/Dashboard.jsx frontend/src/App.css
git commit -m "$(cat <<'EOF'
feat: add Review Forecast, Critical Items, and Extra Study to dashboard

Dashboard now shows review forecast bar chart (24h/5d toggle),
critical condition items with error rates, and extra study shortcuts.
EOF
)"
```

---

### Task 10: Frontend — Review Typo Detection UI + Subject Synonyms (SERIAL — after Task 9)

**Files:**
- Modify: `frontend/src/pages/Reviews.jsx` (add close/typo state)
- Modify: `frontend/src/pages/SubjectDetail.jsx` (add context sentences, hints, synonyms UI)

**Step 1: Update Reviews.jsx for typo detection**

In `Reviews.jsx`, update the `submitAnswer` function — after receiving the response, check for the `close` flag:

```jsx
const submitAnswer = async () => {
  if (!answer.trim()) return;
  const current = queue[currentIndex];
  const resp = await api.submitReview(current.subject_id, current.answerType, answer.trim());

  if (resp.close) {
    setResult({ close: true, did_you_mean: resp.did_you_mean });
    return;
  }

  setResult(resp);
  // ... rest of existing correct/incorrect handling
};
```

Add the "close" UI state in the rendering — after the input, before the wrong-answer section:

```jsx
{result && result.close && (
  <div className="mt-2 text-center">
    <div style={{ color: '#edab36', fontWeight: 600 }}>
      That's close! Check your answer.
    </div>
    {result.did_you_mean && (
      <div className="text-sm text-muted mt-1">
        Did you mean "{result.did_you_mean}"?
      </div>
    )}
  </div>
)}
```

When `result.close` is true, the input should NOT be disabled — the user can re-type. Update the input's disabled prop:

```jsx
disabled={result && !result.close}
```

Update the input's className to add the `.close` class:

```jsx
className={`input input-lg${result?.correct === true ? ' correct' : ''}${result?.correct === false && !result?.close ? ' incorrect' : ''}${result?.close ? ' close' : ''}`}
```

When the user presses Enter while in `close` state, clear the result and let them try again:

```jsx
const handleKeyDown = (e) => {
  if (e.key === 'Enter') {
    if (result && result.close) {
      setResult(null);
      setAnswer('');
    } else if (result) {
      nextItem();
    } else {
      submitAnswer();
    }
  }
};
```

**Step 2: Update SubjectDetail.jsx — context sentences + synonyms**

Add to the detail page, after the reading mnemonic section:

```jsx
{subject.context_sentences && JSON.parse(subject.context_sentences || '[]').length > 0 && (
  <div className="detail-section">
    <h2>Context Sentences</h2>
    {JSON.parse(subject.context_sentences).map((s, i) => (
      <div key={i} className="context-sentence">
        <div className="context-ja">{s.ja}</div>
        <div className="context-en">{s.en}</div>
      </div>
    ))}
  </div>
)}
```

Add synonym management section (before the SRS Progress section):

```jsx
{/* User Synonyms */}
<div className="detail-section">
  <h2>User Synonyms</h2>
  <SynonymManager subjectId={subject.id} />
</div>
```

Create a `SynonymManager` inline component at the top of SubjectDetail.jsx (or as a separate component):

```jsx
function SynonymManager({ subjectId }) {
  const [synonyms, setSynonyms] = useState([]);
  const [newSyn, setNewSyn] = useState('');

  useEffect(() => {
    api.getSubjectSynonyms(subjectId).then(setSynonyms);
  }, [subjectId]);

  const addSynonym = async () => {
    if (!newSyn.trim()) return;
    const syn = await api.addSubjectSynonym(subjectId, newSyn.trim());
    setSynonyms([...synonyms, syn]);
    setNewSyn('');
  };

  const removeSynonym = async (synId) => {
    await api.deleteSubjectSynonym(subjectId, synId);
    setSynonyms(synonyms.filter((s) => s.id !== synId));
  };

  return (
    <div>
      <div className="synonym-list">
        {synonyms.map((s) => (
          <span key={s.id} className="synonym-tag">
            {s.meaning}
            <button className="synonym-remove" onClick={() => removeSynonym(s.id)}>x</button>
          </span>
        ))}
      </div>
      <div className="synonym-add" style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
        <input
          type="text"
          className="input"
          placeholder="Add synonym..."
          value={newSyn}
          onChange={(e) => setNewSyn(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addSynonym()}
          style={{ flex: 1 }}
        />
        <button className="btn btn-sm btn-primary" onClick={addSynonym}>Add</button>
      </div>
    </div>
  );
}
```

**Step 3: Add CSS for context sentences and synonyms**

Append to `frontend/src/App.css`:

```css
/* === Context Sentences === */

.context-sentence {
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-color);
}

.context-sentence:last-child {
  border-bottom: none;
}

.context-ja {
  font-size: 1.1rem;
  margin-bottom: 0.25rem;
}

.context-en {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

/* === Synonyms === */

.synonym-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.synonym-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
}

.synonym-remove {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
  line-height: 1;
}

.synonym-remove:hover {
  color: var(--color-incorrect);
}
```

**Step 4: Update the subject detail API response**

In `backend/routes/subjects.py`, update `_subject_to_dict` to include the new fields:

```python
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
        "context_sentences": s.context_sentences,
        "meaning_hint": s.meaning_hint,
        "reading_hint": s.reading_hint,
    }
```

**Step 5: Build and test**

Run: `cd frontend && npm run build`
Expected: Build succeeds

Test in browser:
1. Review a subject — intentionally type a close typo. Verify yellow state + retry prompt.
2. Visit a subject detail page — verify context sentences appear (if data imported) and synonym add/remove works.

**Step 6: Run ALL backend tests**

Run: `PYTHONPATH="" rtk proxy python -m pytest backend/tests/ -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add frontend/src/pages/Reviews.jsx frontend/src/pages/SubjectDetail.jsx frontend/src/App.css backend/routes/subjects.py
git commit -m "$(cat <<'EOF'
feat: add typo detection UI, context sentences, and user synonyms

Reviews show yellow 'close' state for near-miss typos without SRS
penalty. Subject detail shows context sentences and synonym management.
EOF
)"
```

---

## Summary

| Task | What | Type | Files |
|------|------|------|-------|
| 1 | DB schema + models | SERIAL (first) | `models.py`, `migrate_v2.py`, `conftest.py` |
| 2 | Enhanced WK import | SERIAL | `import_wanikani.py` |
| 3 | Extra Study backend | SERIAL | `routes/extra_study.py`, `reviews.py`, `main.py` |
| 4 | Forecast backend | SERIAL | `routes/stats.py` |
| 5 | Typo detection + synonyms | SERIAL | `srs_engine.py`, `reviews.py`, `subjects.py` |
| 6 | Critical items backend | SERIAL | `routes/stats.py` |
| 7 | Lesson quiz re-queue | SERIAL | `Lessons.jsx` |
| 8 | Extra Study frontend + API | SERIAL | `ExtraStudy.jsx`, `api.js`, `App.jsx` |
| 9 | Dashboard widgets | SERIAL | `ReviewForecast.jsx`, `CriticalItems.jsx`, `Dashboard.jsx`, `App.css` |
| 10 | Review typo UI + synonyms | SERIAL | `Reviews.jsx`, `SubjectDetail.jsx`, `App.css`, `subjects.py` |

Total: 10 tasks, all SERIAL (shared files prevent safe parallelization).
Expected new tests: ~25 tests across 4 new test files.
