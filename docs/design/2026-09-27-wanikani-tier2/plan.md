# WaniKani Tier 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 SRS bugs and add 6 high-impact features to reach WaniKani parity.

**Architecture:** All changes are additive — existing API contracts gain new fields but don't break. New DB columns/tables added via idempotent migration. Frontend components compose with existing design system.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, React 19, framer-motion, lucide-react, sonner, wanakana

---

## Task Dependencies

- **Task 1** (DB schema) — blocks all other tasks
- **Tasks 2-7** (backend) — depend on Task 1, independent of each other (PARALLEL)
- **Tasks 8-12** (frontend) — depend on their respective backend tasks (SERIAL after backend)
- **Task 13** (build + verify) — depends on all prior tasks

---

### Task 1: DB Schema — Migration + Models (SERIAL — first)

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/migrate_v2.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Step 1: Add `incorrect_in_session` to SrsItem and `LevelEvent` model in `backend/models.py`**

Add to SrsItem class (after `last_incorrect_at`):
```python
    incorrect_in_session = Column(Integer, default=0)
```

Add new model after UserSynonym:
```python
class LevelEvent(Base):
    __tablename__ = "level_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, unique=True, nullable=False)
    reached_at = Column(Float, nullable=False)
```

**Step 2: Update `backend/tests/conftest.py` — add LevelEvent to imports**

Change import line:
```python
from backend.models import Subject, SubjectDependency, SrsItem, Setting, UserSynonym, LevelEvent  # noqa: F401
```

**Step 3: Add migration for new column and table in `backend/migrate_v2.py`**

After the existing `last_incorrect_at` migration block, add:
```python
    if "incorrect_in_session" not in srs_cols:
        cursor.execute("ALTER TABLE srs_items ADD COLUMN incorrect_in_session INTEGER DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER UNIQUE NOT NULL,
            reached_at REAL NOT NULL
        )
    """)
```

**Step 4: Write tests in `backend/tests/test_models.py`**

```python
def test_srs_item_has_incorrect_in_session(db):
    db.add(Subject(id=99, type="radical", characters="x", slug="x", level=1,
                   meanings='[{"meaning":"X","primary":true}]'))
    db.add(SrsItem(subject_id=99, incorrect_in_session=1))
    db.commit()
    item = db.query(SrsItem).filter_by(subject_id=99).first()
    assert item.incorrect_in_session == 1


def test_level_event_model(db):
    from backend.models import LevelEvent
    db.add(LevelEvent(level=2, reached_at=1000000.0))
    db.commit()
    row = db.query(LevelEvent).first()
    assert row.level == 2
    assert row.reached_at == 1000000.0
```

**Step 5: Run tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_models.py -v`
Expected: All pass

**Step 6: Run migration on real DB**

Run: `PYTHONPATH="" python -m backend.migrate_v2`

**Step 7: Commit**

```bash
git add backend/models.py backend/migrate_v2.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat: add incorrect_in_session column and LevelEvent model"
```

---

### Task 2: Bug Fix — SRS Idempotent Penalty (PARALLEL after Task 1)

**Files:**
- Modify: `backend/routes/reviews.py:104-132`
- Test: `backend/tests/test_review_routes.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_review_routes.py`:
```python
def test_double_wrong_only_drops_once(db, client):
    """Both meaning and reading wrong should only drop stage once."""
    s = Subject(id=10, type="kanji", characters="火", slug="fire", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Fire", "primary": True}]),
                readings=json.dumps([{"reading": "ひ", "primary": True, "type": "kunyomi"}]),
                meaning_mnemonic="Flames.")
    db.add(s)
    db.add(SrsItem(subject_id=10, srs_stage=5, next_review_at=time.time() - 100))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    # Wrong meaning — stage should drop from 5 to 3 (guru drops by 2)
    resp1 = client.post("/api/reviews/10", json={"answer_type": "meaning", "answer": "water"})
    assert resp1.json()["correct"] is False
    assert resp1.json()["new_stage"] == 3

    # Wrong reading — stage should NOT drop again (already penalized this session)
    resp2 = client.post("/api/reviews/10", json={"answer_type": "reading", "answer": "か"})
    assert resp2.json()["correct"] is False
    assert resp2.json()["new_stage"] == 3  # stays at 3, not 2
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_review_routes.py::test_double_wrong_only_drops_once -v`
Expected: FAIL — `new_stage` will be 1 instead of 3

**Step 3: Fix the SRS penalty logic in `backend/routes/reviews.py`**

Replace the stage resolution block (after `if correct:` / `else:` block, lines ~114-132) with:

```python
    intervals = _get_intervals(db)
    new_stage = item.srs_stage
    both_needed = subject.type not in ("radical", "kana_vocabulary")
    meaning_done = item.meaning_correct_in_session == 1
    reading_done = item.reading_correct_in_session == 1 if both_needed else True

    if not correct and item.incorrect_in_session == 0:
        new_stage = retreat_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.incorrect_in_session = 1

    if meaning_done and reading_done:
        new_stage = advance_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0
        item.incorrect_in_session = 0
```

Note: remove the old `elif not correct:` block entirely. The new logic retreats FIRST if incorrect and not yet penalized, then checks for advancement separately.

**Step 4: Run all review tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_review_routes.py -v`
Expected: All pass (verify existing `test_one_wrong_retreats_stage` still works — it does meaning wrong then reading correct, which should retreat once then not advance because meaning was wrong)

**Step 5: Commit**

```bash
git add backend/routes/reviews.py backend/tests/test_review_routes.py
git commit -m "fix: SRS penalty is now idempotent per review session"
```

---

### Task 3: Bug Fix — Lesson Gating (PARALLEL after Task 1)

**Files:**
- Modify: `backend/routes/lessons.py:22-45`
- Test: `backend/tests/test_lesson_routes.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_lesson_routes.py`:
```python
def test_dependency_gating_filters_unguru_components(db, client):
    """When dependency_gating=True, items with unguru'd components are excluded."""
    # radical (component) at stage 2 (not guru)
    db.add(Subject(id=100, type="radical", characters="r", slug="r", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R", "primary": True}])))
    db.add(SrsItem(subject_id=100, srs_stage=2))

    # kanji depends on the radical
    db.add(Subject(id=101, type="kanji", characters="k", slug="k", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K", "primary": True}]),
                   readings=json.dumps([{"reading": "か", "primary": True}])))
    db.add(SrsItem(subject_id=101, srs_stage=0))
    db.add(SubjectDependency(subject_id=101, component_id=100))

    # standalone radical (no deps) — should still appear
    db.add(Subject(id=102, type="radical", characters="s", slug="s", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "S", "primary": True}])))
    db.add(SrsItem(subject_id=102, srs_stage=0))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(True)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    assert 102 in ids
    assert 101 not in ids  # blocked by unguru'd component


def test_dependency_gating_allows_guru_components(db, client):
    """When dependency_gating=True, items with guru'd components are allowed."""
    db.add(Subject(id=200, type="radical", characters="r", slug="r2", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R2", "primary": True}])))
    db.add(SrsItem(subject_id=200, srs_stage=5))  # guru!

    db.add(Subject(id=201, type="kanji", characters="k", slug="k2", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K2", "primary": True}]),
                   readings=json.dumps([{"reading": "き", "primary": True}])))
    db.add(SrsItem(subject_id=201, srs_stage=0))
    db.add(SubjectDependency(subject_id=201, component_id=200))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(True)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    assert 201 in ids
```

Also add import at top of file:
```python
from backend.models import Subject, SrsItem, Setting, SubjectDependency
from backend.srs_engine import DEFAULT_INTERVALS
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_lesson_routes.py::test_dependency_gating_filters_unguru_components -v`
Expected: FAIL

**Step 3: Implement gating in `backend/routes/lessons.py`**

Add imports at top:
```python
from backend.models import Subject, SrsItem, Setting, SubjectDependency
from backend.jlpt_mapping import wanikani_level_to_jlpt
from backend.routes.levels import compute_current_level
```

Replace `get_lessons` function body:
```python
@router.get("/lessons")
def get_lessons(db: Session = Depends(get_db)):
    batch_size = _get_setting(db, "lesson_batch_size", 5)
    dep_gating = _get_setting(db, "dependency_gating", False)
    jlpt_gating = _get_setting(db, "jlpt_gating", False)

    query = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage == 0)
    )

    if dep_gating:
        from sqlalchemy import and_, func
        ungated_ids = (
            db.query(SubjectDependency.subject_id)
            .join(SrsItem, SrsItem.subject_id == SubjectDependency.component_id)
            .group_by(SubjectDependency.subject_id)
            .having(func.min(SrsItem.srs_stage) < 5)
            .subquery()
        )
        query = query.filter(~SrsItem.subject_id.in_(db.query(ungated_ids)))

    if jlpt_gating:
        current_level = compute_current_level(db)
        current_jlpt = wanikani_level_to_jlpt(current_level)
        jlpt_order = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}
        current_rank = jlpt_order.get(current_jlpt, 5)
        allowed = [k for k, v in jlpt_order.items() if v <= current_rank]
        query = query.filter(Subject.jlpt_level.in_(allowed))

    items = query.order_by(Subject.level, Subject.id).limit(batch_size).all()

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
```

**Step 4: Run all lesson tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_lesson_routes.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add backend/routes/lessons.py backend/tests/test_lesson_routes.py
git commit -m "fix: enforce dependency and JLPT gating in lessons"
```

---

### Task 4: Bug Fix — Auxiliary Meanings (PARALLEL after Task 1)

**Files:**
- Modify: `backend/srs_engine.py:34-64`
- Modify: `backend/routes/reviews.py:66-70`
- Test: `backend/tests/test_srs_engine.py`
- Test: `backend/tests/test_review_routes.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_srs_engine.py` inside `TestDetailedAnswerChecking`:
```python
    def test_auxiliary_meanings_accepted(self):
        meanings = [{"meaning": "Girl", "primary": True}]
        aux = [{"meaning": "Woman", "type": "whitelist"}]
        result = check_answer_meaning_detailed("woman", meanings, auxiliary_meanings=aux)
        assert result["status"] == "correct"

    def test_auxiliary_meanings_blacklist_rejected(self):
        meanings = [{"meaning": "Girl", "primary": True}]
        aux = [{"meaning": "Female", "type": "blacklist"}]
        result = check_answer_meaning_detailed("female", meanings, auxiliary_meanings=aux)
        assert result["status"] == "incorrect"
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_srs_engine.py::TestDetailedAnswerChecking::test_auxiliary_meanings_accepted -v`
Expected: FAIL — `auxiliary_meanings` is not a valid parameter

**Step 3: Update `check_answer_meaning_detailed` in `backend/srs_engine.py`**

Change the function signature and add aux handling:
```python
def check_answer_meaning_detailed(
    answer: str,
    meanings: list[dict],
    synonyms: list[str] | None = None,
    auxiliary_meanings: list[dict] | None = None,
) -> dict:
    answer_lower = answer.strip().lower()

    all_accepted = [m["meaning"] for m in meanings if m.get("accepted_answer", True)]
    if synonyms:
        all_accepted.extend(synonyms)
    if auxiliary_meanings:
        all_accepted.extend(
            a["meaning"] for a in auxiliary_meanings
            if a.get("type") != "blacklist"
        )
    # ... rest of function unchanged
```

**Step 4: Update `backend/routes/reviews.py` to pass auxiliary_meanings**

In `submit_review`, in the `if req.answer_type == "meaning":` block, add:
```python
        aux_meanings = json.loads(subject.auxiliary_meanings) if subject.auxiliary_meanings else []
        detailed = check_answer_meaning_detailed(req.answer, meanings, user_syns or None, auxiliary_meanings=aux_meanings)
```

**Step 5: Run all tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_srs_engine.py backend/tests/test_review_routes.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/srs_engine.py backend/routes/reviews.py backend/tests/test_srs_engine.py backend/tests/test_review_routes.py
git commit -m "fix: check auxiliary meanings during review validation"
```

---

### Task 5: Richer Review Response + Visually Similar Backend (PARALLEL after Task 1)

**Files:**
- Modify: `backend/routes/reviews.py:28-46` (GET /reviews)
- Modify: `backend/routes/subjects.py:12-28` (_subject_to_dict) and GET /subjects/{id}
- Test: `backend/tests/test_review_routes.py`
- Test: `backend/tests/test_subject_routes.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_review_routes.py`:
```python
def test_get_reviews_returns_full_subject_data(db, client):
    _seed(db)
    resp = client.get("/api/reviews")
    item = resp.json()[0]
    assert "meanings" in item
    assert "readings" in item
    assert "meaning_mnemonic" in item
    assert "components" in item
```

Add to `backend/tests/test_subject_routes.py`:
```python
def test_subject_detail_includes_visually_similar(db, client):
    db.add(Subject(id=10, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}]),
                   visually_similar_subject_ids=json.dumps([11])))
    db.add(Subject(id=11, type="kanji", characters="太", slug="fat", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Fat", "primary": True}]),
                   readings=json.dumps([{"reading": "ふと", "primary": True}])))
    db.add(SrsItem(subject_id=10))
    db.add(SrsItem(subject_id=11))
    db.commit()

    resp = client.get("/api/subjects/10")
    data = resp.json()
    assert "visually_similar" in data
    assert len(data["visually_similar"]) == 1
    assert data["visually_similar"][0]["characters"] == "太"
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_review_routes.py::test_get_reviews_returns_full_subject_data backend/tests/test_subject_routes.py::test_subject_detail_includes_visually_similar -v`
Expected: Both FAIL

**Step 3: Update GET /reviews in `backend/routes/reviews.py`**

Replace the return list in `get_reviews`:
```python
    results = []
    for item in items:
        s = item.subject
        comp_ids = db.query(SubjectDependency.component_id).filter_by(subject_id=s.id).all()
        components = []
        for (cid,) in comp_ids:
            c = db.get(Subject, cid)
            if c:
                components.append({
                    "id": c.id, "characters": c.characters, "type": c.type,
                    "meanings": json.loads(c.meanings),
                })
        synonyms = [{"id": syn.id, "meaning": syn.meaning}
                     for syn in db.query(UserSynonym).filter_by(subject_id=s.id).all()]
        results.append({
            "srs_item_id": item.id,
            "subject_id": item.subject_id,
            "type": s.type,
            "characters": s.characters,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
            "meaning_hint": s.meaning_hint,
            "reading_hint": s.reading_hint,
            "components": components,
            "user_synonyms": synonyms,
        })
    return results
```

Add `SubjectDependency` and `UserSynonym` to the imports in reviews.py:
```python
from backend.models import Subject, SrsItem, Setting, UserSynonym, SubjectDependency
```

**Step 4: Add visually similar to `_subject_to_dict` and GET /subjects/{id}**

In `backend/routes/subjects.py`, add to `_subject_to_dict` return dict:
```python
        "visually_similar_subject_ids": json.loads(s.visually_similar_subject_ids) if s.visually_similar_subject_ids else [],
```

In `get_subject`, after the `used_in` block, add:
```python
    vis_sim_ids = json.loads(subject.visually_similar_subject_ids) if subject.visually_similar_subject_ids else []
    vis_similar = []
    for vid in vis_sim_ids:
        vs = db.get(Subject, vid)
        if vs:
            vis_similar.append({
                "id": vs.id, "characters": vs.characters, "type": vs.type,
                "meanings": json.loads(vs.meanings),
            })
    result["visually_similar"] = vis_similar
```

**Step 5: Run all tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_review_routes.py backend/tests/test_subject_routes.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/routes/reviews.py backend/routes/subjects.py backend/tests/test_review_routes.py backend/tests/test_subject_routes.py
git commit -m "feat: richer review response and visually similar kanji backend"
```

---

### Task 6: SRS Reset, Resurrect, Richer Lessons Backend (PARALLEL after Task 1)

**Files:**
- Modify: `backend/routes/subjects.py` (reset + resurrect endpoints)
- Modify: `backend/routes/lessons.py` (richer response)
- Create: `backend/tests/test_reset_resurrect.py`
- Modify: `backend/tests/test_lesson_routes.py`

**Step 1: Write the failing tests for reset/resurrect**

Create `backend/tests/test_reset_resurrect.py`:
```python
import json
import time
from backend.models import Subject, SrsItem


def _seed(db):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=5, started_at=1000.0,
                   next_review_at=time.time() + 3600,
                   correct_count=10, incorrect_count=3))
    db.commit()


def test_reset_subject(db, client):
    _seed(db)
    resp = client.post("/api/subjects/1/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["srs_stage"] == 0
    assert data["correct_count"] == 0

    item = db.query(SrsItem).filter_by(subject_id=1).first()
    assert item.srs_stage == 0
    assert item.started_at is None
    assert item.next_review_at is None


def test_reset_rejects_stage_0(db, client):
    db.add(Subject(id=2, type="radical", characters="r", slug="r", level=1,
                   meanings=json.dumps([{"meaning": "R", "primary": True}])))
    db.add(SrsItem(subject_id=2, srs_stage=0))
    db.commit()
    resp = client.post("/api/subjects/2/reset")
    assert resp.status_code == 400


def test_resurrect_burned_item(db, client):
    db.add(Subject(id=3, type="kanji", characters="火", slug="fire", level=1,
                   meanings=json.dumps([{"meaning": "Fire", "primary": True}]),
                   readings=json.dumps([{"reading": "ひ", "primary": True}])))
    db.add(SrsItem(subject_id=3, srs_stage=9, started_at=1000.0,
                   correct_count=20, incorrect_count=5))
    db.commit()

    resp = client.post("/api/subjects/3/resurrect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["srs_stage"] == 1
    assert data["correct_count"] == 20  # preserved

    item = db.query(SrsItem).filter_by(subject_id=3).first()
    assert item.srs_stage == 1
    assert item.next_review_at is not None


def test_resurrect_rejects_non_burned(db, client):
    _seed(db)  # stage 5
    resp = client.post("/api/subjects/1/resurrect")
    assert resp.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_reset_resurrect.py -v`
Expected: FAIL — endpoints don't exist

**Step 3: Implement reset and resurrect in `backend/routes/subjects.py`**

Add after the `delete_synonym` endpoint:
```python
@router.post("/subjects/{subject_id}/reset")
def reset_subject(subject_id: int, db: Session = Depends(get_db)):
    item = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    if item.srs_stage < 1:
        raise HTTPException(status_code=400, detail="Item is not started")
    item.srs_stage = 0
    item.started_at = None
    item.next_review_at = None
    item.correct_count = 0
    item.incorrect_count = 0
    item.meaning_correct_in_session = 0
    item.reading_correct_in_session = 0
    item.incorrect_in_session = 0
    db.commit()
    return {"srs_stage": 0, "correct_count": 0, "incorrect_count": 0}


@router.post("/subjects/{subject_id}/resurrect")
def resurrect_subject(subject_id: int, db: Session = Depends(get_db)):
    import time as _time
    item = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    if item.srs_stage != 9:
        raise HTTPException(status_code=400, detail="Only burned items can be resurrected")
    item.srs_stage = 1
    item.next_review_at = _time.time()
    item.meaning_correct_in_session = 0
    item.reading_correct_in_session = 0
    item.incorrect_in_session = 0
    db.commit()
    return {
        "srs_stage": 1,
        "correct_count": item.correct_count,
        "incorrect_count": item.incorrect_count,
    }
```

**Step 4: Add richer data to GET /lessons response**

In `backend/routes/lessons.py`, add imports:
```python
from backend.models import Subject, SrsItem, Setting, SubjectDependency
```

Update the results building loop to include components and new fields:
```python
    results = []
    for item in items:
        s = item.subject
        comp_ids = db.query(SubjectDependency.component_id).filter_by(subject_id=s.id).all()
        components = []
        for (cid,) in comp_ids:
            c = db.get(Subject, cid)
            if c:
                components.append({
                    "id": c.id, "characters": c.characters, "type": c.type,
                    "meanings": json.loads(c.meanings),
                })

        vis_similar = []
        if s.type == "kanji" and s.visually_similar_subject_ids:
            for vid in json.loads(s.visually_similar_subject_ids):
                vs = db.get(Subject, vid)
                if vs:
                    vis_similar.append({
                        "id": vs.id, "characters": vs.characters, "type": vs.type,
                        "meanings": json.loads(vs.meanings),
                    })

        results.append({
            "id": s.id,
            "type": s.type,
            "characters": s.characters,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
            "meaning_hint": s.meaning_hint,
            "reading_hint": s.reading_hint,
            "components": components,
            "context_sentences": json.loads(s.context_sentences) if s.context_sentences else [],
            "part_of_speech": json.loads(s.part_of_speech) if s.part_of_speech else [],
            "visually_similar": vis_similar,
        })
    return results
```

**Step 5: Write test for richer lessons**

Add to `backend/tests/test_lesson_routes.py`:
```python
def test_lessons_include_components_and_context(db, client):
    db.add(Subject(id=300, type="radical", characters="r", slug="r", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R", "primary": True}])))
    db.add(SrsItem(subject_id=300, srs_stage=5))

    db.add(Subject(id=301, type="kanji", characters="k", slug="k", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K", "primary": True}]),
                   readings=json.dumps([{"reading": "か", "primary": True}]),
                   meaning_hint="Think of K",
                   context_sentences=json.dumps([{"ja": "これはKです", "en": "This is K"}])))
    db.add(SrsItem(subject_id=301, srs_stage=0))
    db.add(SubjectDependency(subject_id=301, component_id=300))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(False)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    item = resp.json()[0]
    assert item["id"] == 301
    assert len(item["components"]) == 1
    assert item["meaning_hint"] == "Think of K"
    assert len(item["context_sentences"]) == 1
```

**Step 6: Run all tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_reset_resurrect.py backend/tests/test_lesson_routes.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add backend/routes/subjects.py backend/routes/lessons.py backend/tests/test_reset_resurrect.py backend/tests/test_lesson_routes.py
git commit -m "feat: add SRS reset/resurrect and richer lesson data"
```

---

### Task 7: Recently Unlocked + Level-up History Backend (PARALLEL after Task 1)

**Files:**
- Modify: `backend/routes/stats.py`
- Modify: `backend/routes/reviews.py` (level-up detection in submit)
- Create: `backend/tests/test_level_history.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_level_history.py`:
```python
import json
import time
from backend.models import Subject, SrsItem, Setting, LevelEvent


def test_recently_unlocked(db, client):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=1, started_at=time.time() - 100))
    db.commit()

    resp = client.get("/api/recently-unlocked")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["characters"] == "大"


def test_recently_unlocked_excludes_old(db, client):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=1, started_at=time.time() - 200000))
    db.commit()

    resp = client.get("/api/recently-unlocked")
    assert len(resp.json()) == 0


def test_level_history_empty(db, client):
    resp = client.get("/api/level-history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_level_history_returns_events(db, client):
    db.add(LevelEvent(level=1, reached_at=1000000.0))
    db.add(LevelEvent(level=2, reached_at=2000000.0))
    db.commit()

    resp = client.get("/api/level-history")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["level"] == 1
    assert data[1]["level"] == 2
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_level_history.py -v`
Expected: FAIL — endpoints don't exist

**Step 3: Implement in `backend/routes/stats.py`**

Add imports:
```python
from backend.models import Subject, SrsItem, LevelEvent
```

Add endpoints:
```python
@router.get("/recently-unlocked")
def get_recently_unlocked(db: Session = Depends(get_db)):
    cutoff = time.time() - 172800  # 48 hours
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff)
        .order_by(SrsItem.started_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": item.subject.id,
            "characters": item.subject.characters,
            "type": item.subject.type,
            "meanings": json.loads(item.subject.meanings),
            "srs_stage": item.srs_stage,
        }
        for item in items
    ]


@router.get("/level-history")
def get_level_history(db: Session = Depends(get_db)):
    events = db.query(LevelEvent).order_by(LevelEvent.level.asc()).all()
    return [{"level": e.level, "reached_at": e.reached_at} for e in events]
```

**Step 4: Add level-up detection to `backend/routes/reviews.py`**

Add imports at top:
```python
from backend.models import Subject, SrsItem, Setting, UserSynonym, SubjectDependency, LevelEvent
from backend.routes.levels import compute_current_level
```

At the end of `submit_review`, before the final `return`, add level-up check:
```python
    level_up = None
    if correct and meaning_done and reading_done:
        current_level = compute_current_level(db)
        max_recorded = db.query(func.max(LevelEvent.level)).scalar() or 0
        if current_level > max_recorded:
            db.add(LevelEvent(level=current_level, reached_at=time.time()))
            db.commit()
            level_up = {"new_level": current_level}
```

Also add `from sqlalchemy import func` to imports.

Update the return dict to include `level_up`:
```python
    return {
        "correct": correct,
        "close": False,
        "correct_answer": correct_answer if not correct else None,
        "new_stage": new_stage,
        "mnemonic": mnemonic if not correct else None,
        "level_up": level_up,
    }
```

**Step 5: Run all tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_level_history.py backend/tests/test_review_routes.py -v`
Expected: All pass

**Step 6: Run entire test suite**

Run: `PYTHONPATH="" python -m pytest backend/tests/ -v`
Expected: All 89+ tests pass

**Step 7: Commit**

```bash
git add backend/routes/stats.py backend/routes/reviews.py backend/tests/test_level_history.py
git commit -m "feat: add recently unlocked, level-up history and detection"
```

---

### Task 8: API Client + ItemInfoPanel Component (SERIAL after Tasks 5-7)

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/components/ItemInfoPanel.jsx`
- Modify: `frontend/src/App.css`

**Step 1: Add new API methods to `frontend/src/api.js`**

Add to the api object:
```javascript
  getRecentlyUnlocked: () => request('/recently-unlocked'),
  getLevelHistory: () => request('/level-history'),
  resetSubject: (id) => request(`/subjects/${id}/reset`, { method: 'POST' }),
  resurrectSubject: (id) => request(`/subjects/${id}/resurrect`, { method: 'POST' }),
```

**Step 2: Create `frontend/src/components/ItemInfoPanel.jsx`**

```jsx
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';
import MnemonicRenderer from './MnemonicRenderer';
import ItemCard from './ItemCard';

export default function ItemInfoPanel({ item, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  if (!item) return null;

  return (
    <div className="item-info-panel">
      <button
        className="item-info-toggle"
        onClick={() => setOpen(!open)}
      >
        <Info size={14} />
        Item Info
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="item-info-content"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="item-info-section">
              <h4>Meanings</h4>
              <div>
                {(item.meanings || []).map((m, i) => (
                  <span key={i} className={`meaning-tag${m.primary ? ' primary' : ''}`}>
                    {m.meaning}
                  </span>
                ))}
                {(item.user_synonyms || []).map((s) => (
                  <span key={`syn-${s.id}`} className="synonym-tag">{s.meaning}</span>
                ))}
              </div>
            </div>

            {item.readings && item.readings.length > 0 && (
              <div className="item-info-section">
                <h4>Readings</h4>
                <div className="readings-list">
                  {item.readings.map((r, i) => (
                    <span key={i} className={`reading-tag${r.primary ? ' primary' : ''}`}>
                      {r.reading}
                      {r.type && <span className="reading-label">{r.type}</span>}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {item.meaning_mnemonic && (
              <div className="item-info-section">
                <h4>Meaning Mnemonic</h4>
                <MnemonicRenderer text={item.meaning_mnemonic} />
                {item.meaning_hint && (
                  <div className="hint-text mt-1">Hint: {item.meaning_hint}</div>
                )}
              </div>
            )}

            {item.reading_mnemonic && (
              <div className="item-info-section">
                <h4>Reading Mnemonic</h4>
                <MnemonicRenderer text={item.reading_mnemonic} />
                {item.reading_hint && (
                  <div className="hint-text mt-1">Hint: {item.reading_hint}</div>
                )}
              </div>
            )}

            {item.components && item.components.length > 0 && (
              <div className="item-info-section">
                <h4>Components</h4>
                <div className="item-grid">
                  {item.components.map((c) => (
                    <ItemCard key={c.id} item={c} />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
```

**Step 3: Add CSS for ItemInfoPanel to `frontend/src/App.css`**

Append:
```css
/* === Item Info Panel === */

.item-info-panel {
  margin-top: 1rem;
  border-top: 1px solid var(--border-color);
  padding-top: 0.75rem;
}

.item-info-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  transition: color 0.2s, border-color 0.2s;
  width: 100%;
  justify-content: center;
}

.item-info-toggle:hover {
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.item-info-content {
  overflow: hidden;
  padding-top: 0.75rem;
}

.item-info-section {
  margin-bottom: 0.75rem;
}

.item-info-section h4 {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

/* === Level Timeline === */

.level-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.level-timeline-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.85rem;
}

.level-timeline-level {
  font-weight: 700;
  min-width: 3rem;
}

.level-timeline-date {
  color: var(--text-secondary);
}

/* === Recently Unlocked === */

.recently-unlocked-scroll {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 0.25rem;
}
```

**Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/components/ItemInfoPanel.jsx frontend/src/App.css
git commit -m "feat: add API methods and ItemInfoPanel component"
```

---

### Task 9: Reviews — Item Info Panel + Level-up Toast (SERIAL after Task 8)

**Files:**
- Modify: `frontend/src/pages/Reviews.jsx`

**Step 1: Add ItemInfoPanel and keyboard handler**

Add imports:
```javascript
import ItemInfoPanel from '../components/ItemInfoPanel';
import { toast } from 'sonner';
```

In `submitAnswer`, after `setResult(resp)`, add level-up check:
```javascript
    if (resp.level_up) {
      toast(`Level up! You reached Level ${resp.level_up.new_level}!`, {
        icon: <Sparkles size={18} style={{ color: 'var(--color-correct)' }} />,
        duration: 5000,
      });
    }
```

In the reviewing phase JSX, after the result buttons div and before the closing `</motion.div>`, add:
```jsx
          {result && (
            <ItemInfoPanel item={current} defaultOpen={!result.correct} />
          )}
```

Add `f` key handler to `handleKeyDown`:
```javascript
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (result) {
        nextItem();
      } else {
        submitAnswer();
      }
    }
  };
```

Add a global keydown listener for `f` key (separate from input). Add a `useEffect`:
```javascript
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'f' && result && phase === 'reviewing' && document.activeElement?.tagName !== 'INPUT') {
        setInfoOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [result, phase]);
```

Note: You'll need to lift the info panel open state to Reviews. Add `const [infoOpen, setInfoOpen] = useState(false);` and pass it to `ItemInfoPanel` as `open={infoOpen}` with an `onToggle` callback. Alternatively, keep it simpler by making ItemInfoPanel controlled — add `open` and `onToggle` props.

**Step 2: Commit**

```bash
git add frontend/src/pages/Reviews.jsx
git commit -m "feat: item info panel in reviews with f-key toggle and level-up toast"
```

---

### Task 10: Lessons — Context Screen + Visually Similar (SERIAL after Task 8)

**Files:**
- Modify: `frontend/src/pages/Lessons.jsx`

**Step 1: Add context screen to lesson study phase**

The existing study phase has `infoScreen` cycling `'meaning' -> 'reading'`. Extend it:

Update `goNext` logic:
```javascript
    const goNext = () => {
      setSlideDir(1);
      const hasReadings = item.type !== 'radical';
      const hasContext = (item.type === 'vocabulary' || item.type === 'kana_vocabulary') &&
        item.context_sentences && item.context_sentences.length > 0;

      if (infoScreen === 'meaning' && hasReadings) {
        setInfoScreen('reading');
      } else if ((infoScreen === 'meaning' || infoScreen === 'reading') && hasContext) {
        setInfoScreen('context');
      } else if (currentIndex < items.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setInfoScreen('meaning');
      } else {
        // transition to quiz...
      }
    };
```

Update `goPrev` to handle 3 screens:
```javascript
    const goPrev = () => {
      setSlideDir(-1);
      if (infoScreen === 'context') {
        setInfoScreen('reading');
      } else if (infoScreen === 'reading') {
        setInfoScreen('meaning');
      } else if (currentIndex > 0) {
        const prevItem = items[currentIndex - 1];
        const prevHasContext = (prevItem.type === 'vocabulary' || prevItem.type === 'kana_vocabulary') &&
          prevItem.context_sentences && prevItem.context_sentences.length > 0;
        setCurrentIndex(currentIndex - 1);
        setInfoScreen(prevHasContext ? 'context' : (prevItem.type !== 'radical' ? 'reading' : 'meaning'));
      }
    };
```

Add context screen JSX alongside existing meaning/reading screens:
```jsx
              {infoScreen === 'context' && (
                <div>
                  <div className="lesson-info-section">
                    <h3>Context Sentences</h3>
                    {(item.context_sentences || []).map((s, i) => (
                      <div key={i} className="context-sentence">
                        <div className="context-ja">{s.ja}</div>
                        <div className="context-en">{s.en}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
```

On the meaning screen for kanji, add visually similar below components:
```jsx
                  {item.visually_similar && item.visually_similar.length > 0 && (
                    <div className="lesson-info-section">
                      <h3>Visually Similar</h3>
                      <div className="item-grid">
                        {item.visually_similar.map((c) => (
                          <ItemCard key={c.id} item={c} />
                        ))}
                      </div>
                    </div>
                  )}
```

On the meaning screen, add part of speech and hints:
```jsx
                  {item.part_of_speech && item.part_of_speech.length > 0 && (
                    <div className="lesson-info-section">
                      <h3>Part of Speech</h3>
                      <div className="flex gap-1">
                        {item.part_of_speech.map((pos, i) => (
                          <span key={i} className="pos-badge">{pos}</span>
                        ))}
                      </div>
                    </div>
                  )}
```

Add hint after meaning mnemonic:
```jsx
                  {item.meaning_hint && (
                    <div className="hint-text mt-1">Hint: {item.meaning_hint}</div>
                  )}
```

And on the reading screen, add reading hint:
```jsx
                  {item.reading_hint && (
                    <div className="hint-text mt-1">Hint: {item.reading_hint}</div>
                  )}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Lessons.jsx
git commit -m "feat: context sentences screen and visually similar in lessons"
```

---

### Task 11: SubjectDetail — Visually Similar + Reset/Resurrect (SERIAL after Task 8)

**Files:**
- Modify: `frontend/src/pages/SubjectDetail.jsx`

**Step 1: Add visually similar section**

After the context sentences section and before components, add:
```jsx
        {subject.type === 'kanji' && subject.visually_similar && subject.visually_similar.length > 0 && (
          <div className="detail-section">
            <h2>Visually Similar</h2>
            <div className="item-grid">
              {subject.visually_similar.map((c) => (
                <ItemCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        )}
```

**Step 2: Add reset/resurrect buttons**

Add import:
```javascript
import { toast } from 'sonner';
import { ArrowLeft, Plus, X, RotateCcw, Sunrise } from 'lucide-react';
```

In the SRS Progress section, after the srs-info-grid, add:
```jsx
            {srs.srs_stage >= 1 && srs.srs_stage <= 8 && (
              <button
                className="btn btn-sm btn-secondary mt-1"
                onClick={async () => {
                  if (window.confirm('Reset this item to the beginning? All progress will be lost.')) {
                    await api.resetSubject(id);
                    toast.success('Item reset');
                    api.getSubject(id).then(setSubject);
                  }
                }}
              >
                <RotateCcw size={14} /> Reset Progress
              </button>
            )}
            {srs.srs_stage === 9 && (
              <button
                className="btn btn-sm btn-secondary mt-1"
                onClick={async () => {
                  await api.resurrectSubject(id);
                  toast.success('Item resurrected! It will appear in your reviews.');
                  api.getSubject(id).then(setSubject);
                }}
              >
                <Sunrise size={14} /> Resurrect
              </button>
            )}
```

**Step 3: Commit**

```bash
git add frontend/src/pages/SubjectDetail.jsx
git commit -m "feat: visually similar kanji and SRS reset/resurrect on subject detail"
```

---

### Task 12: Dashboard — Recently Unlocked + Level Timeline (SERIAL after Task 8)

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Step 1: Add state and data fetching**

Add to imports:
```javascript
import { Award, Unlock } from 'lucide-react';
import ItemCard from '../components/ItemCard';
```

Add state:
```javascript
  const [recentlyUnlocked, setRecentlyUnlocked] = useState(null);
  const [levelHistory, setLevelHistory] = useState(null);
```

Add to useEffect:
```javascript
    api.getRecentlyUnlocked().then(setRecentlyUnlocked);
    api.getLevelHistory().then(setLevelHistory);
```

**Step 2: Add Recently Unlocked card**

Place between the session cards and Extra Study:
```jsx
      {recentlyUnlocked && recentlyUnlocked.length > 0 && (
        <motion.div variants={fadeUp} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Unlock size={13} />
            Recently Unlocked
          </div>
          <div className="recently-unlocked-scroll">
            {recentlyUnlocked.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </motion.div>
      )}
```

**Step 3: Add Level Timeline card**

Place after JLPT Progress:
```jsx
      {levelHistory && levelHistory.length > 0 && (
        <motion.div variants={fadeUp} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Award size={13} />
            Level Timeline
          </div>
          <div className="level-timeline">
            {levelHistory.map((e) => (
              <div key={e.level} className="level-timeline-row">
                <span className="level-timeline-level">Lv {e.level}</span>
                <span className="level-timeline-date">
                  {new Date(e.reached_at * 1000).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'short', day: 'numeric',
                  })}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
```

**Step 4: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: recently unlocked items and level timeline on dashboard"
```

---

### Task 13: Build, Full Test, Final Commit (SERIAL — last)

**Step 1: Run all backend tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/ -v`
Expected: All tests pass (89 existing + ~15 new)

**Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Clean build

**Step 3: Run migration on real DB**

Run: `PYTHONPATH="" python -m backend.migrate_v2`
Expected: "Migration complete"

**Step 4: Start server and manually verify**

Run: `PYTHONPATH="" uvicorn backend.main:app`
Check:
- Dashboard shows recently unlocked, level timeline, extra study, forecast, critical items
- Reviews show item info panel (toggle with `f` key)
- Lessons show components, context sentences, hints, visually similar
- SubjectDetail shows visually similar, reset/resurrect buttons
- Settings gating toggles affect lesson availability

**Step 5: Final commit if any adjustments needed**

```bash
git add -A
git commit -m "chore: final adjustments for WaniKani tier 2"
```
