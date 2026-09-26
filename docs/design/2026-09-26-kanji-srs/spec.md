# Kanji SRS - Personal WaniKani Clone

**Date:** 2026-09-26
**Status:** Validated

## Context

WaniKani is an effective kanji learning tool but its pacing is rigid and non-configurable. Building a personal clone allows fully customizable SRS intervals, no gating restrictions, and JLPT-ordered content instead of WaniKani's proprietary level ordering.

## Decision

Build a monolith web app (FastAPI + React + SQLite) that imports all WaniKani data once via their API v2, reorders it by JLPT level, and provides a fully self-contained SRS experience with typed-answer reviews.

## Requirements

- One-time import of all radicals, kanji, and vocabulary from WaniKani API v2 into local SQLite
- JLPT-based ordering (N5 through N1) instead of WaniKani levels
- 9-stage SRS system matching WaniKani defaults (Apprentice 1-4, Guru 1-2, Master, Enlightened, Burned)
- All SRS intervals configurable by the user
- Lesson/review gating toggleable (JLPT level gating and dependency gating independently)
- Configurable lesson batch sizes with no upper cap
- Typed answers: English for meanings, hiragana (via romaji input) for readings
- Both meaning and reading must be correct for an item to advance
- Dashboard with review count, next review countdown, SRS stage breakdown, JLPT progress
- Item browser with search and filtering by JLPT level, type, and SRS stage
- Single process to run: one command starts the server and serves the frontend

## Constraints

- Personal use only, single user, no auth
- Requires a WaniKani API token for the one-time import
- WaniKani API rate limited to 60 requests/minute (import script must respect this)
- Data is stored in a single SQLite file for easy backup

## Out of Scope

- Multi-user support or authentication
- Mobile app (browser on mobile is fine)
- Syncing across devices
- Custom content creation (adding your own kanji/vocab)
- Audio playback for vocabulary
- Community features (forums, shared mnemonics)

## Open Questions

- [ ] Exact JLPT mapping for all 60 WaniKani levels (community mappings exist but vary slightly)

## Success Criteria

- [ ] Import script successfully pulls all ~9,000 subjects from WaniKani API
- [ ] Can complete a full lesson + review cycle with typed answers
- [ ] SRS intervals are configurable and persist across restarts
- [ ] Gating toggles work (can access any JLPT level when gating is off)
- [ ] Dashboard accurately shows review counts and JLPT progress
- [ ] Entire app runs with a single command
