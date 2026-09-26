# Kanji SRS — Project Context

## What This Is

A personal WaniKani clone — a web app for learning Japanese kanji via spaced repetition. JLPT-ordered content (N5-N1), imported once from WaniKani's API v2 into local SQLite.

## Tech Stack

- **Backend:** Python 3.12 (conda env `adhi`), FastAPI, SQLAlchemy, SQLite
- **Frontend:** React 19, Vite 5, React Router, wanakana.js (romaji→hiragana)
- **DB:** Single file at `data/kanji-srs.db`

## Project Structure

```
kanji-srs/
├── backend/
│   ├── main.py              # FastAPI app, serves API + static frontend, seeds defaults on startup
│   ├── models.py            # SQLAlchemy: Subject, SubjectDependency, SrsItem, Setting
│   ├── srs_engine.py        # Stage logic, intervals, answer checking (levenshtein typo tolerance)
│   ├── import_wanikani.py   # One-time WaniKani API v2 data import
│   ├── jlpt_mapping.py      # WaniKani level (1-60) → JLPT level (N5-N1)
│   ├── database.py          # Engine, SessionLocal, Base, get_db
│   ├── conftest.py          # Root pytest conftest (db fixture)
│   ├── routes/
│   │   ├── settings.py      # GET/PUT /api/settings
│   │   ├── subjects.py      # GET /api/subjects, GET /api/subjects/{id} (with used_in)
│   │   ├── lessons.py       # GET /api/lessons, POST /api/lessons/start
│   │   ├── reviews.py       # GET /api/reviews, POST /api/reviews/{id}
│   │   ├── stats.py         # GET /api/summary (with current_level, level_progress)
│   │   └── levels.py        # GET /api/levels, GET /api/levels/{level}
│   └── tests/               # 54 tests, all passing
│       ├── conftest.py       # Shared fixtures (db, client) with StaticPool in-memory SQLite
│       └── test_*.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Router shell with nav (level badge, count badges)
│   │   ├── App.css           # CSS design system with WaniKani type/SRS colors
│   │   ├── api.js            # Fetch wrapper for all API calls
│   │   ├── components/
│   │   │   ├── TypeBadge.jsx       # Colored pill for radical/kanji/vocab
│   │   │   ├── MnemonicRenderer.jsx # Parses <radical>/<kanji>/<vocab> tags → colored spans
│   │   │   ├── SrsStageBar.jsx     # Visual SRS stage indicator (9 segments)
│   │   │   ├── ItemCard.jsx        # Clickable card: character + meaning + type color
│   │   │   └── ProgressBar.jsx     # Reusable progress bar with label
│   │   └── pages/
│   │       ├── Dashboard.jsx  # Level progress, session cards, SRS breakdown, JLPT bars
│   │       ├── Lessons.jsx    # Multi-phase: teach (meaning/reading/mnemonic) → quiz
│   │       ├── Reviews.jsx    # Wrap-up, shake animation, mnemonic on wrong, summary
│   │       ├── Subjects.jsx   # Level grid (60 levels) + filterable list toggle
│   │       ├── SubjectDetail.jsx # Item detail: mnemonics, components, used-in, SRS stats
│   │       ├── LevelDetail.jsx   # Level items grouped by type with SRS dots
│   │       └── Settings.jsx      # All settings: batch size, gating, SRS intervals
│   └── vite.config.js        # Proxies /api to :8000 in dev
├── data/                      # kanji-srs.db lives here (gitignored)
└── docs/design/
    ├── 2026-09-26-kanji-srs/  # Original project design
    └── 2026-09-27-wanikani-polish/ # WaniKani polish design + plan
```

## Key Design Decisions

- **SRS:** 9 stages (0=not started, 1-4=Apprentice, 5-6=Guru, 7=Master, 8=Enlightened, 9=Burned). Correct→advance 1, wrong→drop 1 (stages 1-4) or drop 2 (stages 5+). Both meaning AND reading must be correct in a session for advancement.
- **Configurable:** SRS intervals, lesson batch size, JLPT gating on/off, dependency gating on/off — all in `settings` table.
- **Answer checking:** Readings require exact hiragana match. Meanings are case-insensitive with Levenshtein distance ≤1 tolerance for words ≥5 chars.
- **Timestamps:** Stored as Unix floats (not datetime) for SQLite compatibility.
- **Single user:** No auth. Single process serves everything.

## Running

```bash
# Activate correct env
conda activate adhi

# IMPORTANT: Clear PYTHONPATH to avoid ros_noetic_ws contamination
export PYTHONPATH=""

# First time: import WaniKani data
python -m backend.import_wanikani <WANIKANI_API_TOKEN>

# Production: build frontend, run server
cd frontend && npm run build && cd ..
uvicorn backend.main:app
# → http://localhost:8000

# Development (hot reload)
uvicorn backend.main:app --reload  # terminal 1
cd frontend && npm run dev         # terminal 2
# → http://localhost:5173

# Tests
python -m pytest backend/tests/ -v  # 47 tests
```

## Known Issues

- **PYTHONPATH contamination:** The `adhi` conda env (Python 3.12) has `ros_noetic_ws` (Python 3.9) site-packages on its path via PYTHONPATH. Must run with `PYTHONPATH=""` to avoid import errors.
- **Python 3.9 compat:** Code uses `from __future__ import annotations` in srs_engine.py and jlpt_mapping.py for `X | None` syntax. The adhi env is 3.12 so this isn't needed there, but keeps things compatible.

## WaniKani API

- Docs: https://docs.api.wanikani.com/20170710/
- Auth: `Authorization: Bearer <token>` header
- Rate limit: 60 req/min, import script sleeps when <5 remaining
- Subjects endpoint paginates at 1000/page via `page_after_id`
- Data scraped once into SQLite, no ongoing API calls
