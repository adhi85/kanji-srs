# Kanji SRS - Agent Specification

**Status:** Validated

## Requirements

### Functional
- One-time data import from WaniKani API v2 (`/subjects` endpoint, paginated at 1,000 per page) into SQLite
- Map each subject to a JLPT level (N5-N1) based on WaniKani level using a static mapping table
- Store radicals, kanji, vocabulary with: characters, meanings (JSON), readings (JSON), meaning_mnemonic, reading_mnemonic, component_subject_ids, part_of_speech
- SRS engine with 9 stages, configurable intervals, correct=advance 1, wrong=drop 1 (stages 1-4) or drop 2 (stages 5-8)
- Review queue: items where `next_review_at <= now()` and `srs_stage BETWEEN 1 AND 8`
- Lesson system: unlock items at stage 0, present in configurable batch sizes, quiz after reading
- Typed answer validation: exact match for readings (hiragana), fuzzy match for meanings (case-insensitive, accept known synonyms from WaniKani data)
- Both meaning and reading must be answered correctly per review session for the item to advance
- Dashboard: pending review count, next review time, SRS stage histogram, JLPT progress bars
- Item browser: search by characters/meaning, filter by JLPT level, subject type, SRS stage
- Settings: SRS intervals, batch size, JLPT gating toggle, dependency gating toggle

### Non-Functional
- Single-user, no authentication
- Single SQLite database file for all state
- FastAPI serves both API and built React frontend (static files)
- Import script must respect 60 req/min rate limit (sleep between pages if needed)

## Constraints

- Python 3.11+ backend
- React 18+ frontend with Vite
- No CSS framework (plain CSS)
- wanakana.js for romaji-to-hiragana input conversion
- SQLAlchemy for ORM
- httpx for WaniKani API calls in import script

## Approach

Monolith architecture: FastAPI app serves REST API under `/api` and the built React SPA from `static/` or `frontend/dist/`. SQLite via SQLAlchemy. SRS logic is server-side only. Frontend is a thin client that fetches data and renders UI.

## Design

### Architecture

```
Browser (React SPA)
    |
    | HTTP (fetch)
    |
FastAPI Server (:8000)
    ├── /api/*       → REST endpoints
    └── /*           → static React build
    |
    | SQLAlchemy
    |
SQLite (kanji-srs.db)
```

### Key Components

| Component | Responsibility | Location |
|-----------|---------------|----------|
| FastAPI app | HTTP server, route mounting, static files | `backend/main.py` |
| SQLAlchemy models | Subject, SrsItem, Setting schemas | `backend/models.py` |
| SRS engine | Stage logic, interval calculation, review scoring | `backend/srs_engine.py` |
| Review routes | GET due reviews, POST answer submissions | `backend/routes/reviews.py` |
| Lesson routes | GET available lessons, POST start lessons | `backend/routes/lessons.py` |
| Subject routes | GET subject detail, search/filter | `backend/routes/subjects.py` |
| Settings routes | GET/PUT user settings | `backend/routes/settings.py` |
| Stats routes | Dashboard summary, accuracy stats | `backend/routes/stats.py` |
| Import script | One-time WaniKani API pull | `backend/import_wanikani.py` |
| JLPT mapping | WaniKani level to JLPT level table | `backend/jlpt_mapping.py` |
| React app | SPA with 4 views | `frontend/src/` |
| Dashboard page | Review count, countdown, progress | `frontend/src/pages/Dashboard.jsx` |
| Lessons page | Card-based lesson flow + quiz | `frontend/src/pages/Lessons.jsx` |
| Reviews page | Typed answer review session | `frontend/src/pages/Reviews.jsx` |
| Subjects page | Browsable/searchable item list | `frontend/src/pages/Subjects.jsx` |
| API client | Fetch wrapper for all backend calls | `frontend/src/api.js` |

### Database Schema

```sql
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY,          -- WaniKani subject ID
    type TEXT NOT NULL,              -- 'radical', 'kanji', 'vocabulary'
    characters TEXT,                 -- UTF-8 character(s), NULL for image-only radicals
    slug TEXT,
    level INTEGER NOT NULL,          -- WaniKani level (1-60)
    jlpt_level TEXT,                 -- 'N5', 'N4', 'N3', 'N2', 'N1'
    meanings TEXT NOT NULL,          -- JSON: [{"meaning": "...", "primary": true}]
    readings TEXT,                   -- JSON: [{"reading": "...", "primary": true, "type": "onyomi"}]
    meaning_mnemonic TEXT,
    reading_mnemonic TEXT,
    part_of_speech TEXT,             -- JSON array, vocabulary only
    document_url TEXT
);

CREATE TABLE subject_dependencies (
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    component_id INTEGER NOT NULL REFERENCES subjects(id),
    PRIMARY KEY (subject_id, component_id)
);

CREATE TABLE srs_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL UNIQUE REFERENCES subjects(id),
    srs_stage INTEGER NOT NULL DEFAULT 0,  -- 0=not started, 1-8=active, 9=burned
    unlocked_at TIMESTAMP,
    started_at TIMESTAMP,
    next_review_at TIMESTAMP,
    correct_count INTEGER DEFAULT 0,
    incorrect_count INTEGER DEFAULT 0,
    meaning_correct_in_session INTEGER DEFAULT 0,  -- tracks within a review session
    reading_correct_in_session INTEGER DEFAULT 0
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL  -- JSON-encoded value
);
```

### Default Settings

```json
{
    "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
    "lesson_batch_size": 5,
    "jlpt_gating": true,
    "dependency_gating": true,
    "max_reviews_per_session": null
}
```

### SRS Engine Logic

```python
def advance_stage(current_stage: int) -> int:
    return min(current_stage + 1, 9)

def retreat_stage(current_stage: int) -> int:
    if current_stage <= 4:
        return max(current_stage - 1, 1)
    return max(current_stage - 2, 1)

def next_review_time(stage: int, intervals: list[int]) -> datetime | None:
    if stage == 0 or stage == 9:
        return None
    return datetime.utcnow() + timedelta(seconds=intervals[stage])
```

### API Endpoints

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/api/summary` | — | `{reviews_available, next_review_at, lessons_available, srs_stage_counts, jlpt_progress}` |
| GET | `/api/lessons` | — | `[{subject with meanings, readings, mnemonic}]` (batch_size items) |
| POST | `/api/lessons/start` | `{subject_ids: [int]}` | `{started: int}` |
| GET | `/api/reviews` | — | `[{srs_item_id, subject_id, type, characters}]` |
| POST | `/api/reviews/{item_id}` | `{answer_type: "meaning"|"reading", answer: str}` | `{correct: bool, correct_answer: str, new_stage: int, mnemonic: str}` |
| GET | `/api/subjects/{id}` | — | Full subject with dependencies, stats |
| GET | `/api/subjects` | `?jlpt=N5&type=kanji&q=search` | Paginated subject list |
| GET | `/api/settings` | — | Current settings object |
| PUT | `/api/settings` | `{key: value, ...}` | Updated settings |
| GET | `/api/stats` | — | `{accuracy_history, items_by_stage, forecast}` |

### Import Script Flow

1. Accept WaniKani API token as CLI argument
2. Fetch all subjects paginated via `GET /subjects` with `page_after_id`
3. For each subject: extract fields, map to JLPT level, insert into `subjects` table
4. For each subject with `component_subject_ids`: insert into `subject_dependencies`
5. Create an `srs_items` row for every subject at stage 0
6. Sleep if approaching rate limit (60 req/min)
7. Print progress: "Imported 1000/9000 subjects..."

### JLPT Mapping (approximate)

```python
WANIKANI_TO_JLPT = {
    range(1, 11): "N5",    # Levels 1-10
    range(11, 21): "N4",   # Levels 11-20
    range(21, 31): "N3",   # Levels 21-30
    range(31, 41): "N2",   # Levels 31-40
    range(41, 51): "N1",   # Levels 41-50
    range(51, 61): "N1",   # Levels 51-60 (advanced N1)
}
```

### Frontend Review Flow

1. `GET /api/reviews` → load all due items
2. Shuffle items, for each item queue both a meaning question and a reading question (radicals: meaning only)
3. Show character prominently, input field below
4. For reading questions: use wanakana.js to bind input field for automatic romaji→hiragana conversion
5. On submit: `POST /api/reviews/{item_id}` with answer_type and answer
6. Show result (green flash / red flash with mnemonic)
7. When all items answered, show session summary (correct %, items advanced, items dropped)

## File References

No existing implementation files — this is a greenfield project at `~/ADHI/projects/kanji-srs/`.

Reference for WaniKani API structure: https://docs.api.wanikani.com/20170710/

## Success Criteria

- [ ] `import_wanikani.py` imports all ~9,000 subjects with rate limit compliance
- [ ] Each subject has correct JLPT level tag
- [ ] Dependency graph (radicals→kanji→vocabulary) is correctly stored
- [ ] SRS engine correctly advances/retreats stages with configurable intervals
- [ ] Review queue returns exactly the items due at the current time
- [ ] Typed answers validate correctly (hiragana for readings, case-insensitive English for meanings)
- [ ] Both meaning and reading must be correct in a session for stage advancement
- [ ] Lesson flow presents items in batches and moves them to stage 1
- [ ] Dashboard shows accurate counts and progress
- [ ] Settings changes persist and take effect immediately
- [ ] `uvicorn main:app` serves both API and frontend on a single port
