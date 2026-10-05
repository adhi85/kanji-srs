# Kanji SRS -- Agent Context

## What This Is

A WaniKani-style web app for learning Japanese kanji via spaced repetition. JLPT-ordered content (N5-N1), imported once from WaniKani's API v2 into local SQLite. Multi-user with JWT auth.

## Tech Stack

- **Backend:** Python 3.12 (conda env `adhi`), FastAPI, SQLAlchemy, SQLite, JWT auth (python-jose, bcrypt)
- **Frontend:** React 19, Vite 5, React Router, wanakana.js (romaji-to-hiragana), framer-motion, lucide-react, sonner (toasts)
- **DB:** Single file at `data/kanji-srs.db`
- **Auth:** JWT tokens (HS256, 30-day expiry), secret auto-generated at `data/.jwt_secret`
- **Deploy:** Docker multi-stage build, docker-compose with persistent volume

## Project Structure

```
kanji-srs/
├── backend/
│   ├── main.py              # FastAPI app, serves API + static frontend, seeds defaults on startup
│   ├── models.py            # SQLAlchemy: User, Subject, SubjectDependency, SrsItem, Setting, LevelEvent, UserSynonym
│   ├── auth.py              # JWT auth: hash_password, verify_password, create_access_token, get_current_user
│   ├── srs_engine.py        # Stage logic, intervals, answer checking (levenshtein typo tolerance)
│   ├── import_wanikani.py   # One-time WaniKani API v2 data import
│   ├── jlpt_mapping.py      # Character-based N5 set (108 kanji from Nihongo Sou Matome) + level-based N4-N1
│   ├── database.py          # Engine, SessionLocal, Base, get_db
│   ├── routes/
│   │   ├── auth.py          # POST /api/auth/register, /api/auth/login, GET /api/auth/me
│   │   ├── settings.py      # GET/PUT /api/settings (per-user)
│   │   ├── subjects.py      # GET /api/subjects, GET /api/subjects/{id}, synonyms, reset, resurrect
│   │   ├── lessons.py       # GET /api/lessons, POST /api/lessons/start
│   │   ├── reviews.py       # GET /api/reviews, POST /api/reviews/{id}
│   │   ├── stats.py         # GET /api/summary, /forecast, /critical-items, /recently-unlocked, /level-history
│   │   ├── levels.py        # GET /api/levels, GET /api/levels/{level}
│   │   └── extra_study.py   # GET /api/extra-study, POST /api/extra-study/{id}
│   └── tests/               # 116 tests across 17 files, all passing
│       ├── conftest.py       # Shared fixtures (db, client) with StaticPool in-memory SQLite
│       └── test_*.py         # 17 test files
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Router shell with nav (level badge, count badges)
│   │   ├── App.css           # CSS design system with WaniKani type/SRS colors
│   │   ├── api.js            # Fetch wrapper for all API calls (auto-attaches JWT)
│   │   ├── context/
│   │   │   └── AuthContext.jsx   # Auth state provider (login, logout, user)
│   │   ├── components/
│   │   │   ├── CharacterDisplay.jsx  # Renders kanji characters or SVG radical images
│   │   │   ├── TypeBadge.jsx         # Colored pill for radical/kanji/vocab
│   │   │   ├── MnemonicRenderer.jsx  # Parses <radical>/<kanji>/<vocab> tags to colored spans
│   │   │   ├── SrsStageBar.jsx       # Visual SRS stage indicator (9 segments)
│   │   │   ├── ItemCard.jsx          # Clickable card: character + meaning + type color
│   │   │   ├── ItemInfoPanel.jsx     # Side panel with detailed item info
│   │   │   ├── ProgressBar.jsx       # Reusable progress bar with label
│   │   │   ├── CriticalItems.jsx     # Leech/critical items display
│   │   │   ├── ReviewForecast.jsx    # Review forecast chart
│   │   │   ├── ScoreRing.jsx         # Circular score display
│   │   │   └── Skeleton.jsx          # Loading skeleton placeholder
│   │   └── pages/
│   │       ├── Dashboard.jsx     # Level progress, session cards, SRS breakdown, JLPT bars, forecast
│   │       ├── Lessons.jsx       # Multi-phase: teach (meaning/reading/mnemonic) then quiz
│   │       ├── Reviews.jsx       # Shake animation, mnemonic on wrong, visually similar, summary
│   │       ├── Subjects.jsx      # Level grid (60 levels) + filterable list toggle
│   │       ├── SubjectDetail.jsx # Item detail: mnemonics, components, used-in, SRS stats, synonyms
│   │       ├── LevelDetail.jsx   # Level items grouped by type with SRS dots
│   │       ├── TypeBrowse.jsx    # Browse radicals/kanji/vocabulary grouped by level
│   │       ├── ExtraStudy.jsx    # Extra study: recent mistakes, lessons, burned items
│   │       ├── Settings.jsx      # All settings: batch size, gating, SRS intervals
│   │       ├── Login.jsx         # Login page
│   │       └── Register.jsx      # Registration page
│   └── vite.config.js        # Proxies /api to :8000 in dev
├── data/                      # kanji-srs.db lives here (gitignored)
├── docs/design/               # Design documents for features
├── Dockerfile                 # Multi-stage: node frontend build + python production
├── docker-compose.yml         # Compose with kanji-data persistent volume
├── entrypoint.sh              # Seeds DB from baked image on first run
├── run.sh                     # Production start script (uvicorn, 2 workers)
└── requirements.txt           # Python deps: fastapi, uvicorn, sqlalchemy, python-jose, bcrypt, httpx
```

## Key Design Decisions

- **SRS:** 9 stages (0=not started, 1-4=Apprentice, 5-6=Guru, 7=Master, 8=Enlightened, 9=Burned). Correct advances 1, wrong drops 1 (stages 1-4) or 2 (stages 5+). Both meaning AND reading must be correct in a session for advancement. Penalty is idempotent per session.
- **JLPT mapping:** N5 uses a character-based set of 108 kanji sourced from Nihongo Sou Matome N5 (ISBN 978-4-86639-076-5). N4-N1 use WaniKani level ranges as approximation: 11-20=N4, 21-30=N3, 31-40=N2, 41-60=N1. Kanji at WK levels 1-10 not in the N5 set fall back to N4.
- **Configurable:** SRS intervals, lesson batch size, max reviews per session, JLPT gating on/off, dependency gating on/off -- all in `settings` table, per user.
- **Answer checking:** Readings require exact hiragana match. Meanings are case-insensitive with Levenshtein distance <=1 tolerance for words >=5 chars. Auxiliary meanings accepted. User synonyms supported.
- **Timestamps:** Stored as Unix floats (not datetime) for SQLite compatibility.
- **Extra study:** Recent mistakes, recent lessons, and burned items modes (read-only, no SRS updates).
- **Level tracking:** LevelEvent records when user reaches a new level. Visually similar subjects shown during reviews.
- **Multi-user:** JWT auth (bcrypt password hashing, HS256 tokens, 30-day expiry). All SRS state (SrsItem, Setting, LevelEvent, UserSynonym) is scoped per user_id. Open registration creates SrsItems for all subjects. Single process serves everything.
- **Docker:** Multi-stage build bakes frontend dist and seed DB into image. Entrypoint copies seed DB to volume on first run. Compose exposes port 8000 with persistent data volume.

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
# -> http://localhost:8000

# Development (hot reload)
uvicorn backend.main:app --reload  # terminal 1
cd frontend && npm run dev         # terminal 2
# -> http://localhost:5173

# Docker
docker build -t kanji-srs:latest .
docker compose up -d

# Tests
PYTHONPATH="" python -m pytest backend/tests/ -v  # 116 tests
```

## Known Issues

- **PYTHONPATH contamination:** The `adhi` conda env (Python 3.12) has `ros_noetic_ws` (Python 3.9) site-packages on its path via PYTHONPATH. Must run with `PYTHONPATH=""` to avoid import errors.
- **N4-N1 JLPT mapping:** Still uses WaniKani level ranges as approximation. Only N5 has character-level accuracy.

## WaniKani API

- Docs: https://docs.api.wanikani.com/20170710/
- Auth: `Authorization: Bearer <token>` header
- Rate limit: 60 req/min, import script sleeps when <5 remaining
- Subjects endpoint paginates at 1000/page via `page_after_id`
- Data scraped once into SQLite, no ongoing API calls
