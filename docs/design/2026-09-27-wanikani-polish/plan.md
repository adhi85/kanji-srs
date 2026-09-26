# WaniKani-Style Full Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Transform the basic kanji-srs frontend into a WaniKani-like experience with type-colored design system, rich mnemonic rendering, multi-phase lessons, enhanced reviews, level-based browsing, and settings UI.

**Architecture:** Incremental enhancement of existing React + FastAPI app. Add 3 backend endpoints (levels list, level detail, enhanced summary/subjects), build a CSS design system with WaniKani type colors, create 5 shared React components, then rewrite/enhance all pages.

**Tech Stack:** React 19, React Router v7, wanakana.js, FastAPI, SQLAlchemy, SQLite, pure CSS.

---

## Task Dependencies

```
Task 1 (Backend: Levels API)        ──┐
Task 2 (Backend: Enhance APIs)      ──┼── PARALLEL
                                      │
Task 3 (CSS Design System)         ───┤── Can start immediately (no backend dep)
                                      │
Task 4 (Shared Components)         ───┴── After Task 3
Task 5 (api.js + App.jsx routing)  ───── After Tasks 1,2
                                      │
Tasks 6-12 (Pages)                 ───── After Tasks 4,5 — PARALLEL with each other
```

- **PARALLEL:** Tasks 1, 2, 3
- **PARALLEL:** Tasks 6, 7, 8, 9, 10, 11, 12 (after 4+5)
- **SERIAL chains:** 3→4, (1+2)→5, (4+5)→pages

---

### Task 1: Backend — Levels API Routes

**Files:**
- Create: `backend/routes/levels.py`
- Modify: `backend/main.py:20-25` (add router include)
- Test: `backend/tests/test_level_routes.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_level_routes.py`:

```python
import json
import time


def _seed_level(db, level, num_kanji=3, num_radical=1, num_vocab=2):
    from backend.models import Subject, SrsItem
    ids = []
    counter = level * 100
    for i in range(num_radical):
        counter += 1
        s = Subject(id=counter, type="radical", characters=None, slug=f"r-{counter}",
                     level=level, meanings=json.dumps([{"meaning": f"Rad{counter}", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    for i in range(num_kanji):
        counter += 1
        s = Subject(id=counter, type="kanji", characters=f"K{counter}",
                     level=level, meanings=json.dumps([{"meaning": f"Kanji{counter}", "primary": True}]),
                     readings=json.dumps([{"reading": "か", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    for i in range(num_vocab):
        counter += 1
        s = Subject(id=counter, type="vocabulary", characters=f"V{counter}",
                     level=level, meanings=json.dumps([{"meaning": f"Vocab{counter}", "primary": True}]),
                     readings=json.dumps([{"reading": "か", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    db.commit()
    return ids


def test_get_levels_empty(client):
    resp = client.get("/api/levels")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_level"] == 1
    assert data["levels"] == []


def test_get_levels_with_data(client, db):
    _seed_level(db, 1)
    _seed_level(db, 2)
    resp = client.get("/api/levels")
    data = resp.json()
    assert data["current_level"] == 1
    assert len(data["levels"]) == 2
    lvl1 = data["levels"][0]
    assert lvl1["level"] == 1
    assert lvl1["radical_count"] == 1
    assert lvl1["kanji_count"] == 3
    assert lvl1["vocab_count"] == 2


def test_current_level_advances(client, db):
    from backend.models import SrsItem
    _seed_level(db, 1, num_kanji=3)
    _seed_level(db, 2, num_kanji=3)
    kanji_items = db.query(SrsItem).join(SrsItem.subject).filter(
        SrsItem.subject.has(type="kanji", level=1)).all()
    for item in kanji_items:
        item.srs_stage = 5
    db.commit()
    resp = client.get("/api/levels")
    assert resp.json()["current_level"] == 2


def test_get_level_detail(client, db):
    _seed_level(db, 1)
    resp = client.get("/api/levels/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert len(data["radicals"]) == 1
    assert len(data["kanji"]) == 3
    assert len(data["vocabulary"]) == 2
    assert "id" in data["kanji"][0]
    assert "characters" in data["kanji"][0]
    assert "meanings" in data["kanji"][0]
    assert "srs_stage" in data["kanji"][0]


def test_get_level_detail_empty(client):
    resp = client.get("/api/levels/99")
    assert resp.status_code == 200
    data = resp.json()
    assert data["radicals"] == []
    assert data["kanji"] == []
    assert data["vocabulary"] == []
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_level_routes.py -v`
Expected: FAIL (404 on /api/levels)

**Step 3: Write the implementation**

Create `backend/routes/levels.py`:

```python
import json

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Subject, SrsItem

router = APIRouter()


def compute_current_level(db: Session) -> int:
    rows = (
        db.query(
            Subject.level,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
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


@router.get("/levels")
def get_levels(db: Session = Depends(get_db)):
    current = compute_current_level(db)
    rows = (
        db.query(
            Subject.level,
            Subject.type,
            func.count(Subject.id).label("count"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
        .group_by(Subject.level, Subject.type)
        .all()
    )
    levels = {}
    for row in rows:
        lvl = row.level
        if lvl not in levels:
            levels[lvl] = {
                "level": lvl,
                "radical_count": 0, "kanji_count": 0, "vocab_count": 0,
                "radical_passed": 0, "kanji_passed": 0, "vocab_passed": 0,
            }
        key = "radical" if row.type == "radical" else "kanji" if row.type == "kanji" else "vocab"
        levels[lvl][f"{key}_count"] = row.count
        levels[lvl][f"{key}_passed"] = row.passed or 0
    return {
        "current_level": current,
        "levels": sorted(levels.values(), key=lambda x: x["level"]),
    }


@router.get("/levels/{level}")
def get_level_detail(level: int, db: Session = Depends(get_db)):
    subjects = (
        db.query(Subject)
        .outerjoin(SrsItem)
        .filter(Subject.level == level)
        .all()
    )
    result = {"level": level, "radicals": [], "kanji": [], "vocabulary": []}
    for s in subjects:
        item = {
            "id": s.id,
            "characters": s.characters,
            "type": s.type,
            "meanings": json.loads(s.meanings) if s.meanings else [],
            "srs_stage": s.srs_item.srs_stage if s.srs_item else 0,
        }
        if s.type == "radical":
            result["radicals"].append(item)
        elif s.type == "kanji":
            result["kanji"].append(item)
        else:
            result["vocabulary"].append(item)
    return result
```

Add the router to `backend/main.py`. After the existing router imports, add:

```python
from backend.routes import levels
```

And add to the router includes (after the existing ones):

```python
app.include_router(levels.router, prefix="/api")
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_level_routes.py -v`
Expected: All PASS

**Step 5: Run full test suite to check for regressions**

Run: `PYTHONPATH="" python -m pytest backend/tests/ -v`
Expected: All 47 existing tests + new tests PASS

**Step 6: Commit**

```bash
git add backend/routes/levels.py backend/tests/test_level_routes.py backend/main.py
git commit -m "feat: add levels API routes with current level computation"
```

---

### Task 2: Backend — Enhance Stats and Subjects APIs

**Files:**
- Modify: `backend/routes/stats.py:1-63`
- Modify: `backend/routes/subjects.py:30-68`
- Modify: `backend/tests/test_stats_routes.py`
- Modify: `backend/tests/test_subject_routes.py`

**Step 1: Write failing tests for enhanced summary**

Add to `backend/tests/test_stats_routes.py`:

```python
def test_summary_includes_current_level(client, db):
    from backend.models import Subject, SrsItem
    import json
    s = Subject(id=1, type="kanji", characters="一", level=1,
                meanings=json.dumps([{"meaning": "One", "primary": True}]),
                readings=json.dumps([{"reading": "いち", "primary": True}]))
    db.add(s)
    db.flush()
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.commit()
    resp = client.get("/api/summary")
    data = resp.json()
    assert "current_level" in data
    assert "level_progress" in data
    assert data["current_level"] == 1
    assert data["level_progress"]["level"] == 1
    assert data["level_progress"]["kanji_total"] >= 1
```

**Step 2: Write failing tests for subjects used_in**

Add to `backend/tests/test_subject_routes.py`:

```python
def test_subject_detail_includes_used_in(client, db):
    from backend.models import Subject, SrsItem, SubjectDependency
    import json
    radical = Subject(id=1, type="radical", characters="一", level=1,
                      meanings=json.dumps([{"meaning": "Ground", "primary": True}]))
    kanji = Subject(id=2, type="kanji", characters="大", level=1,
                    meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                    readings=json.dumps([{"reading": "おお", "primary": True}]))
    db.add_all([radical, kanji])
    db.flush()
    db.add(SubjectDependency(subject_id=2, component_id=1))
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.add(SrsItem(subject_id=2, srs_stage=0))
    db.commit()
    resp = client.get("/api/subjects/1")
    data = resp.json()
    assert "used_in" in data
    assert len(data["used_in"]) == 1
    assert data["used_in"][0]["id"] == 2
    assert data["used_in"][0]["characters"] == "大"
```

**Step 3: Run tests to verify they fail**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_stats_routes.py::test_summary_includes_current_level backend/tests/test_subject_routes.py::test_subject_detail_includes_used_in -v`
Expected: FAIL

**Step 4: Enhance stats.py**

In `backend/routes/stats.py`, add import for `compute_current_level` from the levels module (or duplicate the logic if levels.py isn't merged yet — if running in parallel, inline the computation).

Add at the top of `stats.py`:

```python
from sqlalchemy import case
```

At the end of the `get_summary` function, before the return, add `current_level` and `level_progress`:

```python
    # Current level computation
    level_rows = (
        db.query(
            Subject.level,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
        .filter(Subject.type == "kanji")
        .group_by(Subject.level)
        .all()
    )
    level_map = {r.level: (r.total, r.passed or 0) for r in level_rows}
    current_level = 1
    for lvl in range(1, 61):
        if lvl not in level_map:
            break
        total, passed = level_map[lvl]
        if total > 0 and passed / total >= 0.9:
            current_level = lvl + 1
        else:
            break
    current_level = min(current_level, 60)

    # Level progress for current level
    progress_rows = (
        db.query(
            Subject.type,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
        .filter(Subject.level == current_level)
        .group_by(Subject.type)
        .all()
    )
    level_progress = {"level": current_level, "kanji_total": 0, "kanji_passed": 0,
                      "radical_total": 0, "radical_passed": 0}
    for row in progress_rows:
        if row.type == "kanji":
            level_progress["kanji_total"] = row.total
            level_progress["kanji_passed"] = row.passed or 0
        elif row.type == "radical":
            level_progress["radical_total"] = row.total
            level_progress["radical_passed"] = row.passed or 0
```

Add to the return dict: `"current_level": current_level, "level_progress": level_progress`.

**Step 5: Enhance subjects.py — add used_in to detail**

In the `get_subject` function in `backend/routes/subjects.py`, after fetching components, add a reverse lookup:

```python
    used_in_rows = (
        db.query(Subject)
        .join(SubjectDependency, SubjectDependency.subject_id == Subject.id)
        .filter(SubjectDependency.component_id == subject_id)
        .all()
    )
    result["used_in"] = [_subject_to_dict(s) for s in used_in_rows]
```

**Step 6: Run tests to verify they pass**

Run: `PYTHONPATH="" python -m pytest backend/tests/test_stats_routes.py backend/tests/test_subject_routes.py -v`
Expected: All PASS

**Step 7: Run full test suite**

Run: `PYTHONPATH="" python -m pytest backend/tests/ -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add backend/routes/stats.py backend/routes/subjects.py backend/tests/test_stats_routes.py backend/tests/test_subject_routes.py
git commit -m "feat: add current level to summary, used_in to subject detail"
```

---

### Task 3: CSS Design System

**Files:**
- Modify: `frontend/src/App.css` (full rewrite)

**Step 1: Rewrite App.css with CSS variables and design system**

Replace the entire `frontend/src/App.css` with:

```css
/* === CSS Design System === */

:root {
  /* Type colors (WaniKani) */
  --color-radical: #00aaff;
  --color-kanji: #cc00ff;
  --color-vocabulary: #7c2ae8;
  --color-kana-vocabulary: #7c2ae8;

  /* SRS stage colors */
  --color-locked: #555555;
  --color-initiate: #555555;
  --color-apprentice: #dd0093;
  --color-guru: #882d9e;
  --color-master: #294ddb;
  --color-enlightened: #0093dd;
  --color-burned: #434343;

  /* Base theme */
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-card: #1f2940;
  --bg-input: #0f1a2e;
  --border-color: #2a3a5c;
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0b0;
  --text-accent: #ffffff;

  /* Feedback */
  --color-correct: #4ecca3;
  --color-incorrect: #e94560;
}

/* === Reset & Base === */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  min-height: 100vh;
}

a { color: var(--color-radical); text-decoration: none; }
a:hover { text-decoration: underline; }

/* === Navigation === */

.nav {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  height: 56px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-accent);
  margin-right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
}

.nav-level-badge {
  background: var(--color-kanji);
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}

.nav-links {
  display: flex;
  gap: 0.25rem;
  list-style: none;
  flex: 1;
}

.nav-link {
  color: var(--text-secondary);
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  font-size: 0.9rem;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.nav-link:hover {
  background: rgba(255,255,255,0.05);
  color: var(--text-primary);
  text-decoration: none;
}

.nav-link.active {
  background: rgba(255,255,255,0.1);
  color: var(--text-accent);
}

.nav-badge {
  background: var(--color-incorrect);
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.nav-badge.lessons {
  background: var(--color-radical);
}

/* === Layout === */

.main {
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
}

/* === Cards === */

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.card-header {
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.75rem;
}

/* === Buttons === */

.btn {
  padding: 0.6rem 1.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  transition: opacity 0.15s, transform 0.1s;
  color: white;
}

.btn:hover { opacity: 0.9; }
.btn:active { transform: scale(0.98); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-primary { background: var(--color-radical); }
.btn-danger { background: var(--color-incorrect); }
.btn-correct { background: var(--color-correct); color: #1a1a2e; }
.btn-secondary { background: var(--border-color); }
.btn-radical { background: var(--color-radical); }
.btn-kanji { background: var(--color-kanji); }
.btn-vocabulary { background: var(--color-vocabulary); }

.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.85rem; }
.btn-lg { padding: 0.8rem 2rem; font-size: 1.1rem; }

/* === Type Colors === */

.type-radical { background: var(--color-radical); color: white; }
.type-kanji { background: var(--color-kanji); color: white; }
.type-vocabulary { background: var(--color-vocabulary); color: white; }
.type-kana_vocabulary { background: var(--color-kana-vocabulary); color: white; }

.type-text-radical { color: var(--color-radical); }
.type-text-kanji { color: var(--color-kanji); }
.type-text-vocabulary { color: var(--color-vocabulary); }

/* === SRS Stage Colors === */

.srs-locked { color: var(--color-locked); }
.srs-initiate { color: var(--color-initiate); }
.srs-apprentice { color: var(--color-apprentice); }
.srs-guru { color: var(--color-guru); }
.srs-master { color: var(--color-master); }
.srs-enlightened { color: var(--color-enlightened); }
.srs-burned { color: var(--color-burned); }

.srs-bg-apprentice { background: var(--color-apprentice); color: white; }
.srs-bg-guru { background: var(--color-guru); color: white; }
.srs-bg-master { background: var(--color-master); color: white; }
.srs-bg-enlightened { background: var(--color-enlightened); color: white; }
.srs-bg-burned { background: var(--color-burned); color: white; }

/* === TypeBadge === */

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  color: white;
  text-transform: capitalize;
}

/* === ItemCard === */

.item-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.15s;
  min-width: 64px;
  text-decoration: none;
  color: white;
}

.item-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  text-decoration: none;
}

.item-card-character {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.3;
}

.item-card-meaning {
  font-size: 0.65rem;
  opacity: 0.9;
  text-align: center;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-card-srs-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 0.2rem;
}

.item-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

/* === MnemonicRenderer === */

.mnemonic-text {
  line-height: 1.8;
  font-size: 0.95rem;
}

.mnemonic-radical {
  background: var(--color-radical);
  color: white;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-weight: 600;
}

.mnemonic-kanji {
  background: var(--color-kanji);
  color: white;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-weight: 600;
}

.mnemonic-vocabulary {
  background: var(--color-vocabulary);
  color: white;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-weight: 600;
}

.mnemonic-meaning {
  font-weight: 700;
  color: var(--text-accent);
}

.mnemonic-reading {
  font-weight: 700;
  color: var(--text-accent);
  background: rgba(255,255,255,0.1);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
}

/* === ProgressBar === */

.progress-bar {
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  overflow: hidden;
  height: 12px;
  width: 100%;
}

.progress-bar.lg { height: 20px; }

.progress-fill {
  height: 100%;
  border-radius: 10px;
  transition: width 0.4s ease;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

/* === SrsStageBar === */

.srs-stage-bar {
  display: flex;
  gap: 3px;
  align-items: center;
}

.srs-stage-segment {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: rgba(255,255,255,0.1);
}

.srs-stage-segment.filled {
  opacity: 1;
}

/* === Character Display === */

.character-large {
  font-size: 5rem;
  text-align: center;
  font-weight: 700;
  color: white;
  padding: 1.5rem;
}

.character-header {
  border-radius: 10px 10px 0 0;
  padding: 2rem 1rem;
  text-align: center;
  margin: -1.25rem -1.25rem 1.25rem -1.25rem;
}

/* === Forms & Inputs === */

.input {
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  color: var(--text-primary);
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  font-size: 1rem;
  width: 100%;
  outline: none;
  transition: border-color 0.15s;
}

.input:focus { border-color: var(--color-radical); }
.input.correct { border-color: var(--color-correct); background: rgba(78, 204, 163, 0.1); }
.input.incorrect { border-color: var(--color-incorrect); background: rgba(233, 69, 96, 0.1); }

.input-lg { font-size: 1.3rem; padding: 0.8rem 1rem; text-align: center; }

select.input {
  appearance: auto;
  cursor: pointer;
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 0.3rem;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--border-color);
  border-radius: 12px;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-switch.active {
  background: var(--color-correct);
}

.toggle-switch::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
}

.toggle-switch.active::after {
  transform: translateX(20px);
}

/* === Level Grid === */

.level-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 0.5rem;
}

.level-cell {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.75rem 0.5rem;
  text-align: center;
  cursor: pointer;
  transition: transform 0.1s, border-color 0.15s;
  text-decoration: none;
  color: var(--text-primary);
}

.level-cell:hover {
  transform: translateY(-2px);
  border-color: var(--color-kanji);
  text-decoration: none;
}

.level-cell.current {
  border-color: var(--color-kanji);
  box-shadow: 0 0 0 1px var(--color-kanji);
}

.level-number {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-accent);
}

.level-cell-progress {
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  margin-top: 0.4rem;
  overflow: hidden;
}

.level-cell-progress-fill {
  height: 100%;
  background: var(--color-correct);
  border-radius: 2px;
  transition: width 0.3s;
}

/* === Dashboard === */

.dashboard-level {
  text-align: center;
  padding: 1.5rem;
}

.dashboard-level-number {
  font-size: 3rem;
  font-weight: 700;
  color: var(--color-kanji);
}

.dashboard-level-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.dashboard-sessions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.session-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  text-align: center;
  cursor: pointer;
  transition: transform 0.1s, border-color 0.15s;
}

.session-card:hover {
  transform: translateY(-2px);
}

.session-card.reviews { border-top: 3px solid var(--color-incorrect); }
.session-card.lessons { border-top: 3px solid var(--color-radical); }

.session-count {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--text-accent);
}

.session-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.srs-breakdown {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
}

.srs-breakdown-item {
  text-align: center;
  padding: 0.75rem 0.25rem;
  border-radius: 8px;
}

.srs-breakdown-count {
  font-size: 1.5rem;
  font-weight: 700;
  color: white;
}

.srs-breakdown-label {
  font-size: 0.7rem;
  color: rgba(255,255,255,0.8);
}

/* === Lesson Screens === */

.lesson-progress-dots {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.lesson-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
}

.lesson-dot.active { background: var(--text-accent); }
.lesson-dot.completed { background: var(--color-correct); }

.lesson-info-section {
  margin-bottom: 1.5rem;
}

.lesson-info-section h3 {
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.lesson-nav {
  display: flex;
  justify-content: space-between;
  margin-top: 1.5rem;
}

/* === Review Session === */

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-radius: 10px;
  margin-bottom: 1rem;
  color: white;
}

.review-progress-text {
  font-size: 0.85rem;
  font-weight: 600;
}

.review-input-area {
  margin-top: 1.5rem;
}

.review-answer-type {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 0.5rem;
}

/* === Feedback Animations === */

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-5px); }
  40%, 80% { transform: translateX(5px); }
}

@keyframes flash-correct {
  0% { background: var(--color-correct); }
  100% { background: transparent; }
}

@keyframes flash-incorrect {
  0% { background: var(--color-incorrect); }
  100% { background: transparent; }
}

.shake { animation: shake 0.4s ease; }
.flash-correct { animation: flash-correct 0.6s ease; }
.flash-incorrect { animation: flash-incorrect 0.6s ease; }

/* === Review Summary === */

.summary-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-stat {
  text-align: center;
  padding: 1rem;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
}

.summary-stat-value {
  font-size: 2rem;
  font-weight: 700;
}

.summary-stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.summary-items-list {
  margin-top: 1rem;
}

.summary-item-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.summary-item-char {
  font-size: 1.2rem;
  font-weight: 600;
  width: 40px;
  text-align: center;
}

/* === Subject Detail === */

.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h2 {
  font-size: 1rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.readings-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.reading-tag {
  background: rgba(255,255,255,0.08);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 1.1rem;
}

.reading-tag.primary {
  background: rgba(255,255,255,0.15);
  font-weight: 600;
}

.reading-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-left: 0.25rem;
}

.meaning-tag {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin: 0.15rem;
}

.meaning-tag.primary {
  background: rgba(255,255,255,0.12);
  font-weight: 600;
}

.pos-badge {
  display: inline-block;
  background: rgba(255,255,255,0.08);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.srs-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
}

.srs-info-item {
  text-align: center;
  padding: 0.75rem;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}

.srs-info-value {
  font-size: 1.3rem;
  font-weight: 700;
}

.srs-info-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* === Settings === */

.settings-section {
  margin-bottom: 2rem;
}

.settings-section h2 {
  font-size: 1.1rem;
  margin-bottom: 1rem;
  color: var(--text-accent);
}

.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 0.5rem 0;
}

.collapsible-header::after {
  content: '▸';
  transition: transform 0.2s;
}

.collapsible-header.open::after {
  transform: rotate(90deg);
}

/* === Countdown === */

.countdown {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

/* === Tabs === */

.tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.tab {
  padding: 0.5rem 1rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.9rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover { color: var(--text-primary); }
.tab.active {
  color: var(--text-accent);
  border-bottom-color: var(--color-radical);
}

/* === View Toggle === */

.view-toggle {
  display: flex;
  gap: 0.25rem;
  background: var(--bg-secondary);
  border-radius: 6px;
  padding: 0.2rem;
}

.view-toggle button {
  padding: 0.35rem 0.75rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}

.view-toggle button.active {
  background: var(--bg-card);
  color: var(--text-accent);
}

/* === Filters Row === */

.filters-row {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  align-items: center;
}

.filters-row .input {
  width: auto;
  min-width: 120px;
}

.filters-row .input[type="search"] {
  flex: 1;
  min-width: 200px;
}

/* === JLPT Progress === */

.jlpt-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
}

.jlpt-item {
  text-align: center;
}

.jlpt-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.jlpt-fraction {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}

/* === Table === */

table {
  width: 100%;
  border-collapse: collapse;
}

th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-color);
}

td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

tr:hover td {
  background: rgba(255,255,255,0.02);
}

tr { cursor: pointer; }

/* === Pagination === */

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

/* === Utility === */

.text-center { text-align: center; }
.text-sm { font-size: 0.85rem; }
.text-muted { color: var(--text-secondary); }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.flex { display: flex; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 1rem;
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
}

.back-link:hover { color: var(--text-primary); }

/* === Toast / Success === */

.toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  padding: 0.75rem 1.25rem;
  border-radius: 8px;
  font-weight: 600;
  z-index: 200;
  animation: slide-up 0.3s ease;
}

.toast.success { background: var(--color-correct); color: #1a1a2e; }
.toast.error { background: var(--color-incorrect); color: white; }

@keyframes slide-up {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
```

**Step 2: Verify dev server still loads without errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds (CSS is valid)

**Step 3: Commit**

```bash
git add frontend/src/App.css
git commit -m "feat: rewrite CSS with WaniKani design system and variables"
```

---

### Task 4: Shared Components

**Files:**
- Create: `frontend/src/components/TypeBadge.jsx`
- Create: `frontend/src/components/MnemonicRenderer.jsx`
- Create: `frontend/src/components/SrsStageBar.jsx`
- Create: `frontend/src/components/ItemCard.jsx`
- Create: `frontend/src/components/ProgressBar.jsx`

**Step 1: Create TypeBadge**

Create `frontend/src/components/TypeBadge.jsx`:

```jsx
const TYPE_LABELS = {
  radical: 'Radical',
  kanji: 'Kanji',
  vocabulary: 'Vocabulary',
  kana_vocabulary: 'Kana',
};

export default function TypeBadge({ type }) {
  return (
    <span className={`type-badge type-${type}`}>
      {TYPE_LABELS[type] || type}
    </span>
  );
}
```

**Step 2: Create MnemonicRenderer**

Create `frontend/src/components/MnemonicRenderer.jsx`:

```jsx
const TAG_REGEX = /<(radical|kanji|vocabulary|meaning|reading)>(.*?)<\/\1>/g;

export default function MnemonicRenderer({ text }) {
  if (!text) return null;

  const parts = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  const regex = new RegExp(TAG_REGEX.source, 'g');
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <span key={key++} className={`mnemonic-${match[1]}`}>
        {match[2]}
      </span>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <span className="mnemonic-text">{parts}</span>;
}
```

**Step 3: Create SrsStageBar**

Create `frontend/src/components/SrsStageBar.jsx`:

```jsx
const STAGE_COLORS = [
  null,
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-guru)',
  'var(--color-guru)',
  'var(--color-master)',
  'var(--color-enlightened)',
  'var(--color-burned)',
];

const STAGE_NAMES = [
  'Locked', 'Apprentice I', 'Apprentice II', 'Apprentice III', 'Apprentice IV',
  'Guru I', 'Guru II', 'Master', 'Enlightened', 'Burned',
];

export function getStageName(stage) {
  return STAGE_NAMES[stage] || 'Unknown';
}

export function getStageCategory(stage) {
  if (stage === 0) return 'locked';
  if (stage <= 4) return 'apprentice';
  if (stage <= 6) return 'guru';
  if (stage === 7) return 'master';
  if (stage === 8) return 'enlightened';
  if (stage === 9) return 'burned';
  return 'locked';
}

export default function SrsStageBar({ stage }) {
  return (
    <div className="srs-stage-bar" title={STAGE_NAMES[stage]}>
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((s) => (
        <div
          key={s}
          className={`srs-stage-segment${s <= stage ? ' filled' : ''}`}
          style={s <= stage ? { background: STAGE_COLORS[s] } : undefined}
        />
      ))}
    </div>
  );
}
```

**Step 4: Create ItemCard**

Create `frontend/src/components/ItemCard.jsx`:

```jsx
import { Link } from 'react-router-dom';
import { getStageCategory } from './SrsStageBar';

const SRS_DOT_COLORS = {
  locked: 'var(--color-locked)',
  apprentice: 'var(--color-apprentice)',
  guru: 'var(--color-guru)',
  master: 'var(--color-master)',
  enlightened: 'var(--color-enlightened)',
  burned: 'var(--color-burned)',
};

export default function ItemCard({ item, showSrs = false }) {
  const primaryMeaning = item.meanings?.find((m) => m.primary)?.meaning
    || item.meanings?.[0]?.meaning || '';
  const category = getStageCategory(item.srs_stage ?? 0);

  return (
    <Link to={`/subjects/${item.id}`} className={`item-card type-${item.type}`}>
      <span className="item-card-character">
        {item.characters || '?'}
      </span>
      <span className="item-card-meaning">{primaryMeaning}</span>
      {showSrs && (
        <span
          className="item-card-srs-dot"
          style={{ background: SRS_DOT_COLORS[category] }}
        />
      )}
    </Link>
  );
}
```

**Step 5: Create ProgressBar**

Create `frontend/src/components/ProgressBar.jsx`:

```jsx
export default function ProgressBar({ value, max, label, sublabel, color, size }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      {(label || sublabel) && (
        <div className="progress-label">
          <span>{label}</span>
          <span>{sublabel || `${pct}%`}</span>
        </div>
      )}
      <div className={`progress-bar${size === 'lg' ? ' lg' : ''}`}>
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: color || 'var(--color-correct)' }}
        />
      </div>
    </div>
  );
}
```

**Step 6: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 7: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add shared components (TypeBadge, MnemonicRenderer, SrsStageBar, ItemCard, ProgressBar)"
```

---

### Task 5: api.js + App.jsx (Routing & Navigation)

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`

**Step 1: Enhance api.js**

Replace `frontend/src/api.js` with:

```js
async function request(path, options = {}) {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const api = {
  getSummary: () => request('/api/summary'),
  getLessons: () => request('/api/lessons'),
  startLessons: (ids) => request('/api/lessons/start', {
    method: 'POST', body: JSON.stringify({ subject_ids: ids }),
  }),
  getReviews: () => request('/api/reviews'),
  submitReview: (subjectId, answerType, answer) => request(`/api/reviews/${subjectId}`, {
    method: 'POST', body: JSON.stringify({ answer_type: answerType, answer }),
  }),
  getSubjects: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, v); });
    return request(`/api/subjects?${qs}`);
  },
  getSubject: (id) => request(`/api/subjects/${id}`),
  getSettings: () => request('/api/settings'),
  updateSettings: (updates) => request('/api/settings', {
    method: 'PUT', body: JSON.stringify(updates),
  }),
  getLevels: () => request('/api/levels'),
  getLevelDetail: (level) => request(`/api/levels/${level}`),
};
```

**Step 2: Rewrite App.jsx with new routes and navigation**

Replace `frontend/src/App.jsx` with:

```jsx
import { BrowserRouter, Routes, Route, NavLink, Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from './api';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import Reviews from './pages/Reviews';
import Subjects from './pages/Subjects';
import SubjectDetail from './pages/SubjectDetail';
import LevelDetail from './pages/LevelDetail';
import Settings from './pages/Settings';
import './App.css';

function Nav() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    api.getSummary().then(setSummary).catch(() => {});
    const interval = setInterval(() => {
      api.getSummary().then(setSummary).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const reviews = summary?.reviews_available || 0;
  const lessons = summary?.lessons_available || 0;
  const level = summary?.current_level || 1;

  return (
    <nav className="nav">
      <Link to="/" className="nav-brand">
        漢字 Kanji SRS
      </Link>
      <Link to={`/levels/${level}`} className="nav-level-badge">
        Lv {level}
      </Link>
      <ul className="nav-links">
        <li>
          <NavLink to="/" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} end>
            Dashboard
          </NavLink>
        </li>
        <li>
          <NavLink to="/lessons" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Lessons
            {lessons > 0 && <span className="nav-badge lessons">{lessons}</span>}
          </NavLink>
        </li>
        <li>
          <NavLink to="/reviews" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Reviews
            {reviews > 0 && <span className="nav-badge">{reviews}</span>}
          </NavLink>
        </li>
        <li>
          <NavLink to="/subjects" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Subjects
          </NavLink>
        </li>
        <li>
          <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Settings
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lessons" element={<Lessons />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/subjects" element={<Subjects />} />
          <Route path="/subjects/:id" element={<SubjectDetail />} />
          <Route path="/levels/:level" element={<LevelDetail />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

> **Note:** This will cause build errors until the new page components (SubjectDetail, LevelDetail, Settings) are created. Create placeholder files for them now to unblock:

Create `frontend/src/pages/SubjectDetail.jsx`:
```jsx
export default function SubjectDetail() {
  return <div>Subject Detail — coming soon</div>;
}
```

Create `frontend/src/pages/LevelDetail.jsx`:
```jsx
export default function LevelDetail() {
  return <div>Level Detail — coming soon</div>;
}
```

Create `frontend/src/pages/Settings.jsx`:
```jsx
export default function Settings() {
  return <div>Settings — coming soon</div>;
}
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/App.jsx frontend/src/pages/SubjectDetail.jsx frontend/src/pages/LevelDetail.jsx frontend/src/pages/Settings.jsx
git commit -m "feat: add new routes, navigation with level badge and count badges"
```

---

### Task 6: Dashboard Rewrite

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx` (full rewrite)

**Step 1: Rewrite Dashboard.jsx**

Replace `frontend/src/pages/Dashboard.jsx` with:

```jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import ProgressBar from '../components/ProgressBar';

const SRS_STAGES = [
  { key: 'apprentice', label: 'Apprentice', stages: [1, 2, 3, 4], className: 'srs-bg-apprentice' },
  { key: 'guru', label: 'Guru', stages: [5, 6], className: 'srs-bg-guru' },
  { key: 'master', label: 'Master', stages: [7], className: 'srs-bg-master' },
  { key: 'enlightened', label: 'Enlightened', stages: [8], className: 'srs-bg-enlightened' },
  { key: 'burned', label: 'Burned', stages: [9], className: 'srs-bg-burned' },
];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [countdown, setCountdown] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getSummary().then(setSummary);
  }, []);

  useEffect(() => {
    if (!summary?.next_review_at || summary.reviews_available > 0) return;
    const tick = () => {
      const diff = summary.next_review_at - Date.now() / 1000;
      if (diff <= 0) { setCountdown('Now!'); return; }
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = Math.floor(diff % 60);
      setCountdown(`${h}h ${m}m ${s}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [summary]);

  if (!summary) return <div className="text-center text-muted mt-3">Loading...</div>;

  const stageCounts = summary.srs_stage_counts || {};
  const lp = summary.level_progress || {};

  return (
    <div>
      {/* Level Progress */}
      <div className="card dashboard-level">
        <div className="dashboard-level-label">Current Level</div>
        <div className="dashboard-level-number">{summary.current_level || 1}</div>
        <div style={{ maxWidth: 400, margin: '0.75rem auto 0' }}>
          <ProgressBar
            value={lp.kanji_passed || 0}
            max={lp.kanji_total || 1}
            label={`Kanji: ${lp.kanji_passed || 0} / ${lp.kanji_total || 0} passed`}
            color="var(--color-kanji)"
            size="lg"
          />
          <div className="mt-1">
            <ProgressBar
              value={lp.radical_passed || 0}
              max={lp.radical_total || 1}
              label={`Radicals: ${lp.radical_passed || 0} / ${lp.radical_total || 0} passed`}
              color="var(--color-radical)"
            />
          </div>
        </div>
      </div>

      {/* Session Cards */}
      <div className="dashboard-sessions">
        <div className="session-card reviews" onClick={() => navigate('/reviews')}>
          <div className="session-count">{summary.reviews_available}</div>
          <div className="session-label">Reviews</div>
          {summary.reviews_available === 0 && countdown && (
            <div className="countdown">Next in {countdown}</div>
          )}
        </div>
        <div className="session-card lessons" onClick={() => navigate('/lessons')}>
          <div className="session-count">{summary.lessons_available}</div>
          <div className="session-label">Lessons</div>
        </div>
      </div>

      {/* SRS Breakdown */}
      <div className="card">
        <div className="card-header">SRS Stages</div>
        <div className="srs-breakdown">
          {SRS_STAGES.map((group) => {
            const count = group.stages.reduce((sum, s) => sum + (stageCounts[s] || 0), 0);
            return (
              <div key={group.key} className={`srs-breakdown-item ${group.className}`}>
                <div className="srs-breakdown-count">{count}</div>
                <div className="srs-breakdown-label">{group.label}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* JLPT Progress */}
      <div className="card">
        <div className="card-header">JLPT Progress</div>
        <div className="jlpt-grid">
          {(summary.jlpt_progress || []).map((j) => (
            <div key={j.jlpt_level} className="jlpt-item">
              <div className="jlpt-label">{j.jlpt_level}</div>
              <ProgressBar
                value={j.burned}
                max={j.total}
                color="var(--color-burned)"
              />
              <div className="jlpt-fraction">{j.burned}/{j.total}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser**

Run the dev server and check http://localhost:5173/. Verify:
- Level number displays
- Progress bars show for kanji and radicals
- Session cards are clickable
- SRS breakdown shows colored boxes
- JLPT progress shows at bottom

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: rewrite dashboard with level progress, SRS breakdown, session cards"
```

---

### Task 7: Lessons Rewrite

**Files:**
- Modify: `frontend/src/pages/Lessons.jsx` (full rewrite)

**Step 1: Rewrite Lessons.jsx with multi-phase teaching flow**

Replace `frontend/src/pages/Lessons.jsx` with:

```jsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ItemCard from '../components/ItemCard';
import TypeBadge from '../components/TypeBadge';
import { toHiragana, bind, unbind } from 'wanakana';

export default function Lessons() {
  const [items, setItems] = useState([]);
  const [phase, setPhase] = useState('loading');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [infoScreen, setInfoScreen] = useState('meaning');
  const navigate = useNavigate();

  // Quiz state
  const [quizQueue, setQuizQueue] = useState([]);
  const [quizIndex, setQuizIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [quizResult, setQuizResult] = useState(null);
  const inputRef = useRef(null);
  const boundRef = useRef(false);

  useEffect(() => {
    api.getLessons().then((data) => {
      if (data.length === 0) {
        setPhase('empty');
      } else {
        setItems(data);
        setPhase('study');
      }
    });
  }, []);

  // Wanakana binding for reading quiz
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    const current = quizQueue[quizIndex];
    if (current?.answerType === 'reading' && !boundRef.current) {
      bind(el);
      boundRef.current = true;
    } else if (current?.answerType === 'meaning' && boundRef.current) {
      unbind(el);
      boundRef.current = false;
    }
    return () => {
      if (boundRef.current && el) {
        unbind(el);
        boundRef.current = false;
      }
    };
  }, [quizIndex, quizQueue, phase]);

  useEffect(() => {
    if (phase === 'quiz' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [quizIndex, phase]);

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Lessons Available</h2>
        <p className="text-muted mt-1">Complete some reviews to unlock new items.</p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  // === STUDY PHASE ===
  if (phase === 'study') {
    const item = items[currentIndex];
    const hasReadings = item.type !== 'radical';

    const goNext = () => {
      if (infoScreen === 'meaning' && hasReadings) {
        setInfoScreen('reading');
      } else if (currentIndex < items.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setInfoScreen('meaning');
      } else {
        // Build quiz queue
        const queue = [];
        items.forEach((it) => {
          queue.push({ item: it, answerType: 'meaning' });
          if (it.type !== 'radical') {
            queue.push({ item: it, answerType: 'reading' });
          }
        });
        // Shuffle
        for (let i = queue.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [queue[i], queue[j]] = [queue[j], queue[i]];
        }
        setQuizQueue(queue);
        setQuizIndex(0);
        setPhase('quiz');
      }
    };

    const goPrev = () => {
      if (infoScreen === 'reading') {
        setInfoScreen('meaning');
      } else if (currentIndex > 0) {
        setCurrentIndex(currentIndex - 1);
        setInfoScreen(items[currentIndex - 1].type !== 'radical' ? 'reading' : 'meaning');
      }
    };

    return (
      <div>
        {/* Progress dots */}
        <div className="lesson-progress-dots">
          {items.map((_, i) => (
            <div
              key={i}
              className={`lesson-dot${i === currentIndex ? ' active' : ''}${i < currentIndex ? ' completed' : ''}`}
            />
          ))}
        </div>

        <div className="card">
          {/* Character header */}
          <div className={`character-header type-${item.type}`}>
            <div className="character-large">{item.characters || '?'}</div>
            <TypeBadge type={item.type} />
          </div>

          {infoScreen === 'meaning' ? (
            <div>
              <div className="lesson-info-section">
                <h3>Meaning</h3>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                  {(item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')}
                </div>
                <div className="text-muted text-sm mt-1">
                  {(item.meanings || []).filter((m) => !m.primary).map((m) => m.meaning).join(', ')}
                </div>
              </div>

              {item.meaning_mnemonic && (
                <div className="lesson-info-section">
                  <h3>Meaning Mnemonic</h3>
                  <MnemonicRenderer text={item.meaning_mnemonic} />
                </div>
              )}

              {item.components && item.components.length > 0 && (
                <div className="lesson-info-section">
                  <h3>Components</h3>
                  <div className="item-grid">
                    {item.components.map((c) => (
                      <ItemCard key={c.id} item={c} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div>
              <div className="lesson-info-section">
                <h3>Reading</h3>
                {(item.readings || []).map((r, i) => (
                  <div key={i} style={{ fontSize: '1.3rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: r.primary ? 700 : 400 }}>{r.reading}</span>
                    {r.type && <span className="reading-label">{r.type}</span>}
                  </div>
                ))}
              </div>

              {item.reading_mnemonic && (
                <div className="lesson-info-section">
                  <h3>Reading Mnemonic</h3>
                  <MnemonicRenderer text={item.reading_mnemonic} />
                </div>
              )}
            </div>
          )}

          {/* Navigation */}
          <div className="lesson-nav">
            <button
              className="btn btn-secondary"
              onClick={goPrev}
              disabled={currentIndex === 0 && infoScreen === 'meaning'}
            >
              ← Back
            </button>
            <button className={`btn btn-${item.type}`} onClick={goNext}>
              {currentIndex === items.length - 1 && (infoScreen === 'reading' || !hasReadings)
                ? 'Start Quiz →'
                : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // === QUIZ PHASE ===
  if (phase === 'quiz') {
    const current = quizQueue[quizIndex];
    if (!current) {
      // All done — start lessons
      api.startLessons(items.map((i) => i.id)).then(() => setPhase('done'));
      return <div className="text-center text-muted mt-3">Completing lessons...</div>;
    }

    const { item, answerType } = current;

    const checkAnswer = () => {
      if (!answer.trim()) return;
      const userAnswer = answer.trim().toLowerCase();
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

    const handleKeyDown = (e) => {
      if (e.key === 'Enter') {
        if (quizResult === false) {
          setAnswer('');
          setQuizResult(null);
        } else {
          checkAnswer();
        }
      }
    };

    return (
      <div>
        <div className="lesson-progress-dots">
          {quizQueue.map((_, i) => (
            <div
              key={i}
              className={`lesson-dot${i === quizIndex ? ' active' : ''}${i < quizIndex ? ' completed' : ''}`}
            />
          ))}
        </div>

        <div className="card">
          <div className={`character-header type-${item.type}`}>
            <div className="character-large">{item.characters || '?'}</div>
          </div>

          <div className="review-answer-type">
            {answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          <div className="review-input-area">
            <input
              ref={inputRef}
              type="text"
              className={`input input-lg${quizResult === true ? ' correct' : ''}${quizResult === false ? ' incorrect' : ''}`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={answerType === 'reading' ? 'Type reading in hiragana' : 'Type the meaning'}
              disabled={quizResult === true}
              autoComplete="off"
              autoCapitalize="off"
            />
          </div>

          {quizResult === false && (
            <div className="mt-2">
              <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Correct answer: {answerType === 'meaning'
                  ? (item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')
                  : (item.readings || []).filter((r) => r.primary).map((r) => r.reading).join(', ')}
              </div>
              <MnemonicRenderer text={answerType === 'meaning' ? item.meaning_mnemonic : item.reading_mnemonic} />
              <div className="mt-2 text-center">
                <span className="text-muted text-sm">Press Enter to continue</span>
              </div>
            </div>
          )}

          {quizResult === null && (
            <div className="mt-2 text-center">
              <button className={`btn btn-${item.type}`} onClick={checkAnswer}>
                Check
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // === DONE PHASE ===
  if (phase === 'done') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2 style={{ color: 'var(--color-correct)' }}>Lessons Complete!</h2>
        <p className="text-muted mt-1">{items.length} items learned. They'll appear in your reviews soon.</p>
        <div className="mt-2 flex gap-2" style={{ justifyContent: 'center' }}>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            More Lessons
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            Dashboard
          </button>
        </div>
      </div>
    );
  }

  return null;
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/lessons. Verify:
- Study phase shows character on colored background
- Meaning mnemonic renders with colored tags
- Reading screen shows readings
- Quiz phase separates meaning and reading
- Wrong answer shows correct answer + mnemonic

**Step 3: Commit**

```bash
git add frontend/src/pages/Lessons.jsx
git commit -m "feat: rewrite lessons with multi-phase teaching and rich mnemonics"
```

---

### Task 8: Reviews Enhancement

**Files:**
- Modify: `frontend/src/pages/Reviews.jsx` (full rewrite)

**Step 1: Rewrite Reviews.jsx**

Replace `frontend/src/pages/Reviews.jsx` with:

```jsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import TypeBadge from '../components/TypeBadge';
import ProgressBar from '../components/ProgressBar';
import { toHiragana, bind, unbind } from 'wanakana';

export default function Reviews() {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState('loading');
  const [stats, setStats] = useState({ correct: 0, incorrect: 0, items: [] });
  const [wrappingUp, setWrappingUp] = useState(false);
  const [shakeClass, setShakeClass] = useState('');
  const inputRef = useRef(null);
  const boundRef = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getReviews().then((data) => {
      if (data.length === 0) {
        setPhase('empty');
        return;
      }
      // Expand into meaning + reading pairs, shuffle
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
      setPhase('reviewing');
    });
  }, []);

  // Wanakana binding
  useEffect(() => {
    const el = inputRef.current;
    if (!el || phase !== 'reviewing') return;
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
    if (phase === 'reviewing' && inputRef.current && !result) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase, result]);

  const submitAnswer = async () => {
    if (!answer.trim()) return;
    const current = queue[currentIndex];
    const resp = await api.submitReview(current.subject_id, current.answerType, answer.trim());
    setResult(resp);

    if (resp.correct) {
      setStats((prev) => ({
        ...prev,
        correct: prev.correct + 1,
        items: [...prev.items, { ...current, correct: true, new_stage: resp.new_stage }],
      }));
    } else {
      setShakeClass('shake');
      setTimeout(() => setShakeClass(''), 400);
      setStats((prev) => ({
        ...prev,
        incorrect: prev.incorrect + 1,
        items: [...prev.items, { ...current, correct: false, new_stage: resp.new_stage }],
      }));
    }
  };

  const nextItem = () => {
    setAnswer('');
    setResult(null);

    if (wrappingUp) {
      // In wrap-up: check if we've seen all subjects' pairs
      const seenSubjects = new Set(stats.items.map((i) => `${i.subject_id}-${i.answerType}`));
      let nextIdx = currentIndex + 1;
      while (nextIdx < queue.length) {
        const next = queue[nextIdx];
        if (seenSubjects.has(`${next.subject_id}-meaning`) || seenSubjects.has(`${next.subject_id}-reading`)) {
          // This subject was already started, include it
          break;
        }
        nextIdx++;
      }
      if (nextIdx >= queue.length) {
        setPhase('summary');
        return;
      }
      setCurrentIndex(nextIdx);
    } else if (currentIndex + 1 >= queue.length) {
      setPhase('summary');
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (result) {
        nextItem();
      } else {
        submitAnswer();
      }
    }
  };

  const handleWrapUp = () => {
    setWrappingUp(true);
  };

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Reviews Available</h2>
        <p className="text-muted mt-1">Check back later for new reviews.</p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  // === REVIEWING ===
  if (phase === 'reviewing') {
    const current = queue[currentIndex];
    if (!current) {
      setPhase('summary');
      return null;
    }
    const total = queue.length;
    const done = stats.correct + stats.incorrect;

    return (
      <div>
        {/* Review header */}
        <div className={`review-header type-${current.type}`}>
          <div className="review-progress-text">{done} / {total}</div>
          <ProgressBar
            value={done}
            max={total}
            color="rgba(255,255,255,0.3)"
          />
          {!wrappingUp && (
            <button className="btn btn-sm btn-secondary" onClick={handleWrapUp}>
              Wrap Up
            </button>
          )}
          {wrappingUp && (
            <span className="text-sm" style={{ opacity: 0.8 }}>Wrapping up...</span>
          )}
        </div>

        <div className={`card ${shakeClass}`}>
          {/* Character */}
          <div className={`character-header type-${current.type}`}>
            <div className="character-large">{current.characters || '?'}</div>
          </div>

          {/* Answer type */}
          <div className="review-answer-type">
            {current.answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          {/* Input */}
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

          {/* Result feedback */}
          {result && !result.correct && (
            <div className="mt-2">
              <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Correct answer: {result.correct_answer}
              </div>
              {result.mnemonic && <MnemonicRenderer text={result.mnemonic} />}
            </div>
          )}

          {/* Action */}
          <div className="mt-2 text-center">
            {result ? (
              <button className={`btn ${result.correct ? 'btn-correct' : 'btn-danger'}`} onClick={nextItem}>
                Next →
              </button>
            ) : (
              <button className="btn btn-primary" onClick={submitAnswer}>
                Check
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // === SUMMARY ===
  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;

    return (
      <div>
        <div className="card text-center">
          <h2>Review Complete!</h2>
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

        {stats.items.length > 0 && (
          <div className="card">
            <div className="card-header">Results</div>
            <div className="summary-items-list">
              {stats.items.map((item, i) => (
                <div key={i} className="summary-item-row">
                  <span className={`type-badge type-${item.type}`} style={{ width: 32, textAlign: 'center', fontSize: '1rem' }}>
                    {item.characters || '?'}
                  </span>
                  <span style={{ flex: 1 }}>
                    {item.answerType === 'meaning' ? 'Meaning' : 'Reading'}
                  </span>
                  <span style={{ color: item.correct ? 'var(--color-correct)' : 'var(--color-incorrect)', fontWeight: 600 }}>
                    {item.correct ? '✓' : '✗'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-center mt-2">
          <button className="btn btn-primary" onClick={() => navigate('/')}>Dashboard</button>
        </div>
      </div>
    );
  }

  return null;
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/reviews (must have reviews available). Verify:
- Type-colored header with progress
- Wrap-up button works
- Wrong answers shake and show mnemonic
- Summary shows results with correct/incorrect

**Step 3: Commit**

```bash
git add frontend/src/pages/Reviews.jsx
git commit -m "feat: enhance reviews with wrap-up, animations, mnemonic display"
```

---

### Task 9: Subjects Page Rewrite (Level Grid + List)

**Files:**
- Modify: `frontend/src/pages/Subjects.jsx` (full rewrite)

**Step 1: Rewrite Subjects.jsx**

Replace `frontend/src/pages/Subjects.jsx` with:

```jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import TypeBadge from '../components/TypeBadge';

export default function Subjects() {
  const [view, setView] = useState('levels');
  const [levels, setLevels] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ jlpt: '', type: '', q: '' });

  useEffect(() => {
    api.getLevels().then(setLevels);
  }, []);

  useEffect(() => {
    if (view === 'list') {
      api.getSubjects({ ...filters, page, per_page: 50 }).then((data) => {
        setSubjects(data.items);
        setTotal(data.total);
      });
    }
  }, [view, page, filters]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  return (
    <div>
      <div className="flex-between mb-2">
        <h1 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Subjects</h1>
        <div className="view-toggle">
          <button className={view === 'levels' ? 'active' : ''} onClick={() => setView('levels')}>
            Levels
          </button>
          <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            List
          </button>
        </div>
      </div>

      {/* === Level Grid View === */}
      {view === 'levels' && levels && (
        <div className="level-grid">
          {levels.levels.map((lvl) => {
            const totalItems = lvl.radical_count + lvl.kanji_count + lvl.vocab_count;
            const passedItems = lvl.radical_passed + lvl.kanji_passed + lvl.vocab_passed;
            const pct = totalItems > 0 ? Math.round((passedItems / totalItems) * 100) : 0;
            return (
              <Link
                key={lvl.level}
                to={`/levels/${lvl.level}`}
                className={`level-cell${lvl.level === levels.current_level ? ' current' : ''}`}
              >
                <div className="level-number">{lvl.level}</div>
                <div className="level-cell-progress">
                  <div className="level-cell-progress-fill" style={{ width: `${pct}%` }} />
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* === List View === */}
      {view === 'list' && (
        <div>
          <div className="filters-row">
            <select
              className="input"
              value={filters.type}
              onChange={(e) => updateFilter('type', e.target.value)}
            >
              <option value="">All Types</option>
              <option value="radical">Radical</option>
              <option value="kanji">Kanji</option>
              <option value="vocabulary">Vocabulary</option>
              <option value="kana_vocabulary">Kana Vocab</option>
            </select>
            <select
              className="input"
              value={filters.jlpt}
              onChange={(e) => updateFilter('jlpt', e.target.value)}
            >
              <option value="">All JLPT</option>
              <option value="N5">N5</option>
              <option value="N4">N4</option>
              <option value="N3">N3</option>
              <option value="N2">N2</option>
              <option value="N1">N1</option>
            </select>
            <input
              type="search"
              className="input"
              placeholder="Search..."
              value={filters.q}
              onChange={(e) => updateFilter('q', e.target.value)}
            />
          </div>

          <table>
            <thead>
              <tr>
                <th>Character</th>
                <th>Meaning</th>
                <th>Type</th>
                <th>JLPT</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => {
                const meaning = (s.meanings || []).find((m) => m.primary)?.meaning || '';
                return (
                  <tr key={s.id}>
                    <td>
                      <Link to={`/subjects/${s.id}`} className="type-text-${s.type}" style={{ fontWeight: 600, fontSize: '1.1rem', color: `var(--color-${s.type})` }}>
                        {s.characters || s.slug || '?'}
                      </Link>
                    </td>
                    <td>{meaning}</td>
                    <td><TypeBadge type={s.type} /></td>
                    <td>{s.jlpt_level || '—'}</td>
                    <td>{s.level}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="pagination">
            <button
              className="btn btn-sm btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              ← Prev
            </button>
            <span className="text-muted text-sm">
              Page {page} of {Math.ceil(total / 50)}
            </span>
            <button
              className="btn btn-sm btn-secondary"
              disabled={page >= Math.ceil(total / 50)}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/subjects. Verify:
- Level grid shows 60 levels with progress bars
- Current level is highlighted
- Clicking a level goes to /levels/:level
- Toggle to list view shows filterable table
- Clicking a subject goes to /subjects/:id

**Step 3: Commit**

```bash
git add frontend/src/pages/Subjects.jsx
git commit -m "feat: rewrite subjects with level grid and filterable list views"
```

---

### Task 10: Level Detail Page

**Files:**
- Modify: `frontend/src/pages/LevelDetail.jsx` (replace placeholder)

**Step 1: Implement LevelDetail.jsx**

Replace `frontend/src/pages/LevelDetail.jsx` with:

```jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import ItemCard from '../components/ItemCard';
import ProgressBar from '../components/ProgressBar';

export default function LevelDetail() {
  const { level } = useParams();
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getLevelDetail(level).then(setData);
  }, [level]);

  if (!data) return <div className="text-center text-muted mt-3">Loading...</div>;

  const totalItems = data.radicals.length + data.kanji.length + data.vocabulary.length;
  const passedItems = [...data.radicals, ...data.kanji, ...data.vocabulary]
    .filter((i) => i.srs_stage >= 5).length;

  const sections = [
    { key: 'radicals', label: 'Radicals', items: data.radicals, color: 'var(--color-radical)' },
    { key: 'kanji', label: 'Kanji', items: data.kanji, color: 'var(--color-kanji)' },
    { key: 'vocabulary', label: 'Vocabulary', items: data.vocabulary, color: 'var(--color-vocabulary)' },
  ];

  return (
    <div>
      <button className="back-link" onClick={() => navigate('/subjects')}>
        ← Back to Subjects
      </button>

      <div className="card">
        <div className="flex-between">
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Level {data.level}</h1>
          <div className="flex gap-1">
            <button
              className="btn btn-sm btn-secondary"
              disabled={parseInt(level) <= 1}
              onClick={() => navigate(`/levels/${parseInt(level) - 1}`)}
            >
              ←
            </button>
            <button
              className="btn btn-sm btn-secondary"
              disabled={parseInt(level) >= 60}
              onClick={() => navigate(`/levels/${parseInt(level) + 1}`)}
            >
              →
            </button>
          </div>
        </div>
        <div className="mt-1">
          <ProgressBar
            value={passedItems}
            max={totalItems}
            label={`${passedItems} / ${totalItems} items passed`}
            color="var(--color-correct)"
          />
        </div>
      </div>

      {sections.map((section) => (
        section.items.length > 0 && (
          <div key={section.key} className="card">
            <div className="card-header" style={{ color: section.color }}>
              {section.label} ({section.items.length})
            </div>
            <div className="item-grid">
              {section.items.map((item) => (
                <ItemCard key={item.id} item={item} showSrs />
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  );
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/levels/1. Verify:
- Back button goes to /subjects
- Level number and progress bar display
- Previous/Next level buttons work
- Items grouped by type with colored cards
- SRS dots show on each card
- Clicking a card goes to /subjects/:id

**Step 3: Commit**

```bash
git add frontend/src/pages/LevelDetail.jsx
git commit -m "feat: implement level detail page with grouped items and progress"
```

---

### Task 11: Subject Detail Page

**Files:**
- Modify: `frontend/src/pages/SubjectDetail.jsx` (replace placeholder)

**Step 1: Implement SubjectDetail.jsx**

Replace `frontend/src/pages/SubjectDetail.jsx` with:

```jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import TypeBadge from '../components/TypeBadge';
import ItemCard from '../components/ItemCard';
import SrsStageBar, { getStageName, getStageCategory } from '../components/SrsStageBar';

export default function SubjectDetail() {
  const { id } = useParams();
  const [subject, setSubject] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getSubject(id).then(setSubject);
  }, [id]);

  if (!subject) return <div className="text-center text-muted mt-3">Loading...</div>;

  const srs = subject.srs || {};
  const category = getStageCategory(srs.srs_stage ?? 0);

  return (
    <div>
      <button className="back-link" onClick={() => navigate(-1)}>
        ← Back
      </button>

      <div className="card">
        {/* Character header */}
        <div className={`character-header type-${subject.type}`}>
          <div className="character-large">{subject.characters || subject.slug || '?'}</div>
          <TypeBadge type={subject.type} />
        </div>

        {/* Meanings */}
        <div className="detail-section">
          <h2>Meanings</h2>
          <div>
            {(subject.meanings || []).map((m, i) => (
              <span key={i} className={`meaning-tag${m.primary ? ' primary' : ''}`}>
                {m.meaning}
              </span>
            ))}
          </div>
        </div>

        {/* Readings */}
        {subject.readings && subject.readings.length > 0 && (
          <div className="detail-section">
            <h2>Readings</h2>
            <div className="readings-list">
              {subject.readings.map((r, i) => (
                <span key={i} className={`reading-tag${r.primary ? ' primary' : ''}`}>
                  {r.reading}
                  {r.type && <span className="reading-label">{r.type}</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Part of speech */}
        {subject.part_of_speech && subject.part_of_speech.length > 0 && (
          <div className="detail-section">
            <h2>Part of Speech</h2>
            <div className="flex gap-1">
              {subject.part_of_speech.map((pos, i) => (
                <span key={i} className="pos-badge">{pos}</span>
              ))}
            </div>
          </div>
        )}

        {/* Meaning Mnemonic */}
        {subject.meaning_mnemonic && (
          <div className="detail-section">
            <h2>Meaning Mnemonic</h2>
            <MnemonicRenderer text={subject.meaning_mnemonic} />
          </div>
        )}

        {/* Reading Mnemonic */}
        {subject.reading_mnemonic && (
          <div className="detail-section">
            <h2>Reading Mnemonic</h2>
            <MnemonicRenderer text={subject.reading_mnemonic} />
          </div>
        )}

        {/* Components */}
        {subject.components && subject.components.length > 0 && (
          <div className="detail-section">
            <h2>Components</h2>
            <div className="item-grid">
              {subject.components.map((c) => (
                <ItemCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        )}

        {/* Used In */}
        {subject.used_in && subject.used_in.length > 0 && (
          <div className="detail-section">
            <h2>Used In</h2>
            <div className="item-grid">
              {subject.used_in.map((c) => (
                <ItemCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        )}

        {/* SRS Progress */}
        <div className="detail-section">
          <h2>SRS Progress</h2>
          <div className="srs-info-grid">
            <div className="srs-info-item">
              <div className={`srs-info-value srs-${category}`}>
                {getStageName(srs.srs_stage ?? 0)}
              </div>
              <div className="srs-info-label">Stage</div>
              <div className="mt-1">
                <SrsStageBar stage={srs.srs_stage ?? 0} />
              </div>
            </div>
            <div className="srs-info-item">
              <div className="srs-info-value" style={{ color: 'var(--color-correct)' }}>
                {srs.correct_count ?? 0}
              </div>
              <div className="srs-info-label">Correct</div>
            </div>
            <div className="srs-info-item">
              <div className="srs-info-value" style={{ color: 'var(--color-incorrect)' }}>
                {srs.incorrect_count ?? 0}
              </div>
              <div className="srs-info-label">Incorrect</div>
            </div>
            {srs.next_review_at && (
              <div className="srs-info-item">
                <div className="srs-info-value text-sm">
                  {new Date(srs.next_review_at * 1000).toLocaleDateString()}
                </div>
                <div className="srs-info-label">Next Review</div>
              </div>
            )}
          </div>
        </div>

        {/* Meta */}
        <div className="detail-section">
          <div className="text-sm text-muted">
            Level {subject.level} {subject.jlpt_level && `· ${subject.jlpt_level}`}
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/subjects/1. Verify:
- Character displays on type-colored background
- Meanings and readings display correctly
- Mnemonics render with colored tags
- Components show as clickable cards
- Used-in section shows (if applicable)
- SRS stage bar and stats display
- Back button works

**Step 3: Commit**

```bash
git add frontend/src/pages/SubjectDetail.jsx
git commit -m "feat: implement subject detail page with mnemonics, components, SRS stats"
```

---

### Task 12: Settings Page

**Files:**
- Modify: `frontend/src/pages/Settings.jsx` (replace placeholder)

**Step 1: Implement Settings.jsx**

Replace `frontend/src/pages/Settings.jsx` with:

```jsx
import { useState, useEffect } from 'react';
import { api } from '../api';

const DEFAULT_INTERVALS = [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0];

function formatInterval(seconds) {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  if (seconds < 604800) return `${(seconds / 86400).toFixed(1)}d`;
  return `${(seconds / 604800).toFixed(1)}w`;
}

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [saved, setSaved] = useState(false);
  const [showIntervals, setShowIntervals] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  const save = async () => {
    await api.updateSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const updateInterval = (index, value) => {
    const intervals = [...(settings.srs_intervals || DEFAULT_INTERVALS)];
    intervals[index] = parseInt(value) || 0;
    updateSetting('srs_intervals', intervals);
  };

  const resetIntervals = () => {
    updateSetting('srs_intervals', [...DEFAULT_INTERVALS]);
  };

  if (!settings) return <div className="text-center text-muted mt-3">Loading...</div>;

  const intervals = settings.srs_intervals || DEFAULT_INTERVALS;

  return (
    <div>
      <h1 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.5rem' }}>Settings</h1>

      <div className="card">
        <div className="settings-section">
          <h2>Lessons</h2>
          <div className="form-group">
            <label className="form-label">Batch Size</label>
            <input
              type="number"
              className="input"
              style={{ width: 120 }}
              min={1}
              max={20}
              value={settings.lesson_batch_size || 5}
              onChange={(e) => updateSetting('lesson_batch_size', parseInt(e.target.value) || 5)}
            />
            <div className="text-sm text-muted mt-1">Number of items per lesson session (1-20)</div>
          </div>
        </div>

        <div className="settings-section">
          <h2>Reviews</h2>
          <div className="form-group">
            <label className="form-label">Max Reviews Per Session</label>
            <input
              type="number"
              className="input"
              style={{ width: 120 }}
              min={10}
              max={500}
              value={settings.max_reviews_per_session || ''}
              onChange={(e) => updateSetting('max_reviews_per_session', parseInt(e.target.value) || null)}
              placeholder="No limit"
            />
            <div className="text-sm text-muted mt-1">Leave empty for no limit</div>
          </div>
        </div>

        <div className="settings-section">
          <h2>Gating</h2>
          <div className="form-group">
            <label
              className="toggle"
              onClick={() => updateSetting('jlpt_gating', !settings.jlpt_gating)}
            >
              <span className={`toggle-switch${settings.jlpt_gating ? ' active' : ''}`} />
              <span>JLPT Gating</span>
            </label>
            <div className="text-sm text-muted mt-1">Items unlock in JLPT order (N5 first)</div>
          </div>
          <div className="form-group">
            <label
              className="toggle"
              onClick={() => updateSetting('dependency_gating', !settings.dependency_gating)}
            >
              <span className={`toggle-switch${settings.dependency_gating ? ' active' : ''}`} />
              <span>Dependency Gating</span>
            </label>
            <div className="text-sm text-muted mt-1">Component items must reach Guru before dependent items unlock</div>
          </div>
        </div>

        <div className="settings-section">
          <div
            className={`collapsible-header${showIntervals ? ' open' : ''}`}
            onClick={() => setShowIntervals(!showIntervals)}
          >
            <h2 style={{ margin: 0 }}>SRS Intervals</h2>
          </div>
          {showIntervals && (
            <div className="mt-1">
              <table>
                <thead>
                  <tr>
                    <th>Stage</th>
                    <th>Interval (seconds)</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {['Apprentice I', 'Apprentice II', 'Apprentice III', 'Apprentice IV',
                    'Guru I', 'Guru II', 'Master', 'Enlightened'].map((name, i) => (
                    <tr key={i}>
                      <td>{name}</td>
                      <td>
                        <input
                          type="number"
                          className="input"
                          style={{ width: 120 }}
                          value={intervals[i + 1]}
                          onChange={(e) => updateInterval(i + 1, e.target.value)}
                        />
                      </td>
                      <td className="text-muted">{formatInterval(intervals[i + 1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button className="btn btn-sm btn-secondary mt-1" onClick={resetIntervals}>
                Reset to Defaults
              </button>
            </div>
          )}
        </div>

        <div className="flex-between mt-2">
          <button className="btn btn-primary" onClick={save}>Save Settings</button>
          {saved && <span style={{ color: 'var(--color-correct)', fontWeight: 600 }}>Saved!</span>}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify in browser**

Navigate to http://localhost:5173/settings. Verify:
- Batch size input works
- Toggle switches animate
- SRS intervals section collapses/expands
- Save button persists changes (reload page to confirm)

**Step 3: Commit**

```bash
git add frontend/src/pages/Settings.jsx
git commit -m "feat: implement settings page with all configurable options"
```

---

### Task 13: Final Build Verification & Frontend Build

**Files:** None new — verification only.

**Step 1: Run backend tests**

Run: `PYTHONPATH="" python -m pytest backend/tests/ -v`
Expected: All tests pass

**Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 3: Full manual verification**

Start the production server:
```bash
PYTHONPATH="" uvicorn backend.main:app
```

Visit http://localhost:8000 and verify:
- [ ] Dashboard shows level, session cards, SRS breakdown, JLPT progress
- [ ] Navigation has level badge and count badges
- [ ] Lessons show teaching screens with rendered mnemonics, then quiz
- [ ] Reviews have wrap-up, shake animation on wrong, mnemonic display
- [ ] Subjects page toggles between level grid and list view
- [ ] Level detail shows items grouped by type with SRS dots
- [ ] Subject detail shows mnemonics, components, used-in, SRS stats
- [ ] Settings page reads and saves all settings
- [ ] All links between pages work (clicking items, levels, nav)

**Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address issues found during final verification"
```
