# Kanji SRS — Project Context

## What This Is

A personal WaniKani clone — a web app for learning Japanese kanji via spaced repetition. JLPT-ordered content (N5-N1), imported once from WaniKani's API v2 into local SQLite.

## Tech Stack

- **Backend:** Python 3.12 (conda env `adhi`), FastAPI, SQLAlchemy, SQLite, JWT auth (python-jose, bcrypt)
- **Frontend:** React 19, Vite 5, React Router, wanakana.js (romaji→hiragana)
- **DB:** Single file at `data/kanji-srs.db`
- **Auth:** JWT tokens (HS256, 30-day expiry), secret auto-generated at `data/.jwt_secret`

## Project Structure

```
kanji-srs/
├── backend/
│   ├── main.py              # FastAPI app, serves API + static frontend, seeds defaults on startup
│   ├── models.py            # SQLAlchemy: User, Subject, SubjectDependency, SrsItem, Setting, LevelEvent, UserSynonym
│   ├── auth.py              # JWT auth: hash_password, verify_password, create_access_token, get_current_user
│   ├── srs_engine.py        # Stage logic, intervals, answer checking (levenshtein typo tolerance)
│   ├── import_wanikani.py   # One-time WaniKani API v2 data import
│   ├── jlpt_mapping.py      # WaniKani level (1-60) → JLPT level (N5-N1)
│   ├── database.py          # Engine, SessionLocal, Base, get_db
│   ├── conftest.py          # Root pytest conftest (db fixture)
│   ├── routes/
│   │   ├── auth.py          # POST /api/auth/register, /api/auth/login, GET /api/auth/me
│   │   ├── settings.py      # GET/PUT /api/settings (per-user)
│   │   ├── subjects.py      # GET /api/subjects, GET /api/subjects/{id}, synonyms, reset, resurrect
│   │   ├── lessons.py       # GET /api/lessons, POST /api/lessons/start
│   │   ├── reviews.py       # GET /api/reviews, POST /api/reviews/{id}
│   │   ├── stats.py         # GET /api/summary, /forecast, /critical-items, /recently-unlocked, /level-history
│   │   ├── levels.py        # GET /api/levels, GET /api/levels/{level}
│   │   └── extra_study.py   # GET /api/extra-study, POST /api/extra-study/{id}
│   └── tests/               # 114 tests, all passing
│       ├── conftest.py       # Shared fixtures (db, client) with StaticPool in-memory SQLite
│       └── test_*.py         # 16 test files
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Router shell with nav (level badge, count badges)
│   │   ├── App.css           # CSS design system with WaniKani type/SRS colors
│   │   ├── api.js            # Fetch wrapper for all API calls (auto-attaches JWT)
│   │   ├── context/
│   │   │   └── AuthContext.jsx   # Auth state provider (login, logout, user)
│   │   ├── components/
│   │   │   ├── TypeBadge.jsx       # Colored pill for radical/kanji/vocab
│   │   │   ├── MnemonicRenderer.jsx # Parses <radical>/<kanji>/<vocab> tags → colored spans
│   │   │   ├── SrsStageBar.jsx     # Visual SRS stage indicator (9 segments)
│   │   │   ├── ItemCard.jsx        # Clickable card: character + meaning + type color
│   │   │   ├── ItemInfoPanel.jsx   # Side panel with detailed item info
│   │   │   ├── ProgressBar.jsx     # Reusable progress bar with label
│   │   │   ├── CriticalItems.jsx   # Leech/critical items display
│   │   │   ├── ReviewForecast.jsx  # Review forecast chart
│   │   │   ├── ScoreRing.jsx       # Circular score display
│   │   │   └── Skeleton.jsx        # Loading skeleton placeholder
│   │   └── pages/
│   │       ├── Dashboard.jsx  # Level progress, session cards, SRS breakdown, JLPT bars, forecast
│   │       ├── Lessons.jsx    # Multi-phase: teach (meaning/reading/mnemonic) → quiz
│   │       ├── Reviews.jsx    # Wrap-up, shake animation, mnemonic on wrong, summary
│   │       ├── Subjects.jsx   # Level grid (60 levels) + filterable list toggle
│   │       ├── SubjectDetail.jsx # Item detail: mnemonics, components, used-in, SRS stats, synonyms
│   │       ├── LevelDetail.jsx   # Level items grouped by type with SRS dots
│   │       ├── ExtraStudy.jsx    # Extra study modes: recent mistakes, lessons, burned items
│   │       ├── Settings.jsx      # All settings: batch size, gating, SRS intervals
│   │       ├── Login.jsx         # Login page
│   │       └── Register.jsx      # Registration page
│   └── vite.config.js        # Proxies /api to :8000 in dev
├── data/                      # kanji-srs.db lives here (gitignored)
└── docs/design/
    ├── 2026-09-26-kanji-srs/            # Original project design
    ├── 2026-09-27-wanikani-polish/      # WaniKani polish design + plan
    └── 2026-09-27-multi-user/           # Multi-user support design
```

## Key Design Decisions

- **SRS:** 9 stages (0=not started, 1-4=Apprentice, 5-6=Guru, 7=Master, 8=Enlightened, 9=Burned). Correct→advance 1, wrong→drop 1 (stages 1-4) or drop 2 (stages 5+). Both meaning AND reading must be correct in a session for advancement. Penalty is idempotent per session.
- **Configurable:** SRS intervals, lesson batch size, max reviews per session, JLPT gating on/off, dependency gating on/off — all in `settings` table.
- **Answer checking:** Readings require exact hiragana match. Meanings are case-insensitive with Levenshtein distance ≤1 tolerance for words ≥5 chars. Auxiliary meanings accepted. User synonyms supported.
- **Timestamps:** Stored as Unix floats (not datetime) for SQLite compatibility.
- **Extra study:** Recent mistakes, recent lessons, and burned items modes (read-only, no SRS updates).
- **Level tracking:** LevelEvent records when user reaches a new level. Visually similar subjects shown during reviews.
- **Multi-user:** JWT auth (bcrypt password hashing, HS256 tokens, 30-day expiry). All SRS state (SrsItem, Setting, LevelEvent, UserSynonym) is scoped per user_id. Open registration creates SrsItems for all subjects. Single process serves everything.

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
python -m pytest backend/tests/ -v  # 114 tests
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
