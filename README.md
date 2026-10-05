# Kanji SRS

A WaniKani-style web app for learning Japanese kanji through spaced repetition, ordered by JLPT level (N5 through N1). Kanji data is imported once from WaniKani's API v2 into a local SQLite database; no ongoing API calls are needed after the initial import.

## Features

- **Spaced repetition system** with 9 stages: Apprentice (1-4), Guru (5-6), Master (7), Enlightened (8), Burned (9). Both meaning and reading must be correct in a review session for advancement.
- **JLPT-ordered content** from N5 to N1, with character-level N5 classification sourced from Nihongo Sou Matome.
- **Lessons** with multi-phase teaching (meaning, reading, mnemonics) followed by a quiz.
- **Reviews** with shake animation on wrong answers, mnemonic hints, visually similar kanji display, and a wrap-up summary.
- **Extra study modes** for recent mistakes, recent lessons, and burned items (read-only, no SRS impact).
- **Answer checking**: readings require exact hiragana match; meanings are case-insensitive with Levenshtein tolerance for longer words. User synonyms supported.
- **Configurable**: SRS intervals, lesson batch size, max reviews per session, JLPT gating, dependency gating -- all per-user settings.
- **Multi-user**: JWT authentication (bcrypt + HS256, 30-day tokens), all SRS state scoped per user. Open registration.
- **Level tracking**: level-up history, per-level progress, dashboard with SRS breakdown and review forecast.
- **Browse**: radicals, kanji, and vocabulary pages grouped by level, with detailed item pages showing mnemonics, components, and usage.
- **Docker support**: multi-stage build with baked-in seed database.

## Tech Stack

| Layer    | Technology                                          |
|----------|-----------------------------------------------------|
| Backend  | Python 3.12, FastAPI, SQLAlchemy, SQLite            |
| Frontend | React 19, Vite 5, React Router, wanakana.js         |
| Auth     | JWT (python-jose, bcrypt)                           |
| Database | SQLite (single file at `data/kanji-srs.db`)         |
| Deploy   | Docker (multi-stage), docker-compose                |

## Getting Started

### Prerequisites

- Python 3.12+ (conda env `adhi` or any virtualenv)
- Node.js 22+
- A WaniKani API token (for the one-time data import)

### Initial Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Import kanji data from WaniKani (one-time)
PYTHONPATH="" python -m backend.import_wanikani <WANIKANI_API_TOKEN>
```

### Development

```bash
# Terminal 1: backend with hot reload
PYTHONPATH="" uvicorn backend.main:app --reload

# Terminal 2: frontend dev server (proxies /api to :8000)
cd frontend && npm run dev
```

Open http://localhost:5173 in your browser.

### Production

```bash
# Build frontend and start server
cd frontend && npm run build && cd ..
PYTHONPATH="" uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Or run `./run.sh` which handles PYTHONPATH and worker config.

### Docker

```bash
# Build
docker build -t kanji-srs:latest .

# Run with persistent data volume
docker compose up -d
```

The Docker image bakes in the seed database. On first run, it copies it to the data volume. Access at http://localhost:8000.

## Tests

```bash
PYTHONPATH="" python -m pytest backend/tests/ -v
```

116 tests across 17 test files covering SRS engine logic, all API routes, import, authentication, and JLPT mapping.

## API Routes

| Method | Endpoint                      | Description                      |
|--------|-------------------------------|----------------------------------|
| POST   | `/api/auth/register`          | Create account                   |
| POST   | `/api/auth/login`             | Get JWT token                    |
| GET    | `/api/auth/me`                | Current user info                |
| GET    | `/api/subjects`               | List/filter subjects             |
| GET    | `/api/subjects/{id}`          | Subject detail                   |
| GET    | `/api/lessons`                | Available lessons                |
| POST   | `/api/lessons/start`          | Start lesson batch               |
| GET    | `/api/reviews`                | Available reviews                |
| POST   | `/api/reviews/{id}`           | Submit review answer             |
| GET    | `/api/summary`                | Dashboard summary                |
| GET    | `/api/forecast`               | Review forecast                  |
| GET    | `/api/critical-items`         | Leech/critical items             |
| GET    | `/api/recently-unlocked`      | Recently unlocked items          |
| GET    | `/api/level-history`          | Level-up history                 |
| GET    | `/api/levels`                 | All levels overview              |
| GET    | `/api/levels/{level}`         | Single level detail              |
| GET    | `/api/extra-study`            | Extra study items                |
| POST   | `/api/extra-study/{id}`       | Submit extra study answer        |
| GET    | `/api/settings`               | User settings                    |
| PUT    | `/api/settings`               | Update user settings             |

## Project Structure

```
kanji-srs/
├── backend/
│   ├── main.py              # FastAPI app, serves API + static frontend
│   ├── models.py            # SQLAlchemy models
│   ├── auth.py              # JWT auth helpers
│   ├── srs_engine.py        # SRS stage logic, intervals, answer checking
│   ├── database.py          # Engine, session, base
│   ├── import_wanikani.py   # One-time WaniKani data import
│   ├── jlpt_mapping.py      # Character-based N5 + level-based N4-N1 mapping
│   ├── routes/              # API route modules
│   └── tests/               # 116 tests across 17 files
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Router shell with navigation
│   │   ├── api.js           # API client with JWT
│   │   ├── context/         # Auth state provider
│   │   ├── components/      # Reusable UI components
│   │   └── pages/           # Route pages
│   └── vite.config.js       # Dev proxy config
├── data/                    # SQLite database (gitignored)
├── docs/design/             # Design documents
├── Dockerfile               # Multi-stage production build
├── docker-compose.yml       # Compose with persistent volume
├── requirements.txt         # Python dependencies
└── run.sh                   # Production start script
```
