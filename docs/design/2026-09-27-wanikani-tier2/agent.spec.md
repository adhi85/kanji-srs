# WaniKani Tier 2 — Agent Specification

## Requirements

### Bug Fixes
1. **SRS idempotent penalty**: wrong answer on meaning + wrong on reading in same review = only ONE stage drop. Add `incorrect_in_session` column to SrsItem. On wrong answer, only call retreat_stage if `incorrect_in_session == 0`, then set `incorrect_in_session = 1`. Reset all three session flags (meaning_correct, reading_correct, incorrect) together after stage resolution.
2. **Lesson gating**: GET /lessons must read `dependency_gating` and `jlpt_gating` settings. If dependency_gating is on, filter out subjects whose component subjects aren't all at stage >= 5. If jlpt_gating is on, filter to current JLPT level or earlier.
3. **Auxiliary meanings**: `check_answer_meaning_detailed` should accept `auxiliary_meanings` parameter. Load from Subject.auxiliary_meanings JSON, include entries where `accepted_answer` is not `false` in the accepted meanings list.

### Feature 1: Item Info Panel in Reviews
- **Backend**: GET /api/reviews response adds per-item: `meanings`, `readings`, `meaning_mnemonic`, `reading_mnemonic`, `meaning_hint`, `reading_hint`, `components` (list of {id, characters, type, meanings}), `user_synonyms`
- **Frontend**: After answer submission, render a collapsible `<ItemInfoPanel>` component. Toggle with `f` key or button. Auto-expanded on incorrect, collapsed on correct. Shows: meanings, readings with type labels, meaning mnemonic + hint, reading mnemonic + hint, components as ItemCard grid, user synonyms.

### Feature 2: Richer Lessons
- **Backend**: GET /api/lessons adds per-item: `components` (with component data), `context_sentences` (parsed JSON), `part_of_speech` (parsed JSON), `meaning_hint`, `reading_hint`, `visually_similar` (for kanji, resolved subject data)
- **Frontend**: Lesson study phase:
  - Meaning screen: meanings, meaning mnemonic + hint, components grid, part of speech badges
  - Reading screen: readings with type labels, reading mnemonic + hint
  - Context screen (vocab/kana_vocab only): context sentences ja/en pairs
  - Navigation: `infoScreen` cycles `'meaning' -> 'reading' -> 'context'` for vocab, `'meaning' -> 'reading'` for kanji, `'meaning'` only for radicals
  - Kanji meaning screen also shows "Visually Similar" section below components

### Feature 3: SRS Reset / Resurrect
- **Backend**:
  - `POST /api/subjects/{id}/reset` — set srs_stage=0, clear started_at, next_review_at, correct_count=0, incorrect_count=0, all session flags=0. Only for items with stage >= 1.
  - `POST /api/subjects/{id}/resurrect` — only for stage=9 (burned). Set srs_stage=1, next_review_at=now, started_at preserved. Keep correct/incorrect counts.
- **Frontend (SubjectDetail.jsx)**: conditional buttons in SRS Progress section. "Reset Progress" (stage 1-9, with confirm dialog), "Resurrect" (stage 9 only). Refresh subject data after. Toast on success.
- **API client**: add `resetSubject(id)` and `resurrectSubject(id)`.

### Feature 4: Visually Similar Kanji
- **Backend**: In `_subject_to_dict`, parse `visually_similar_subject_ids` JSON. In GET /subjects/{id}, resolve those IDs to basic subject data (id, characters, type, meanings).
- **Frontend (SubjectDetail.jsx)**: new section "Visually Similar" after reading mnemonic, before components. Rendered as ItemCard grid. Only for kanji type.

### Feature 5: Recently Unlocked on Dashboard
- **Backend**: `GET /api/recently-unlocked` — query SrsItem where started_at >= now - 172800 (48h), join Subject, return {id, characters, type, meanings, srs_stage}. Order by started_at desc, limit 10.
- **Frontend (Dashboard.jsx)**: new card "Recently Unlocked" between session cards and extra study. Horizontal scroll of ItemCards. Hidden when empty.

### Feature 6: Level-up History
- **Model**: `LevelEvent` table: id (PK autoincrement), level (Integer, unique), reached_at (Float).
- **Migration**: `CREATE TABLE IF NOT EXISTS level_events (...)` in migrate_v2.py.
- **Detection**: In POST /api/reviews/{subject_id}, after committing stage changes, compute current_level. Query max level from level_events. If current > max (or no rows), insert new LevelEvent. Return `level_up: {new_level: N}` in response when triggered.
- **Backend**: `GET /api/level-history` — all LevelEvent rows ordered by level asc.
- **Frontend (Dashboard.jsx)**: "Level Timeline" card below JLPT progress. Compact list: "Level N — YYYY-MM-DD".
- **Frontend (Reviews.jsx)**: when response has `level_up`, show toast with Sparkles icon and "Level up! You reached Level N!"
- **API client**: add `getLevelHistory()`.

## Constraints
- No new npm packages
- SQLite migration must be idempotent
- All existing 89 tests must still pass
- Use existing CSS design system patterns (cards, detail-sections, ItemCard, TypeBadge, etc.)
- Use framer-motion for new animations (collapse/expand, item grid entry)

## Design

### Architecture
All changes are additive. No existing API contracts change (only additions to response payloads). New DB columns/tables added via idempotent migration.

### Key Components
| Component | Responsibility | Location |
|-----------|---------------|----------|
| SrsItem model | Add incorrect_in_session column | `backend/models.py` |
| LevelEvent model | New model for level history | `backend/models.py` |
| Migration | Add columns + level_events table | `backend/migrate_v2.py` |
| srs_engine | Accept auxiliary_meanings | `backend/srs_engine.py` |
| reviews route | Richer response, idempotent penalty, level-up detection | `backend/routes/reviews.py` |
| lessons route | Richer response with components/context/hints | `backend/routes/lessons.py` |
| subjects route | Visually similar, reset, resurrect endpoints | `backend/routes/subjects.py` |
| stats route | Recently unlocked, level history endpoints | `backend/routes/stats.py` |
| ItemInfoPanel | New component for review info panel | `frontend/src/components/ItemInfoPanel.jsx` |
| Reviews.jsx | Integrate info panel, level-up toast | `frontend/src/pages/Reviews.jsx` |
| Lessons.jsx | Context screen, visually similar, richer data | `frontend/src/pages/Lessons.jsx` |
| SubjectDetail.jsx | Visually similar section, reset/resurrect buttons | `frontend/src/pages/SubjectDetail.jsx` |
| Dashboard.jsx | Recently unlocked, level timeline | `frontend/src/pages/Dashboard.jsx` |
| api.js | New endpoints | `frontend/src/api.js` |

### Data Flow

**Review submission with level-up detection:**
```
POST /reviews/{id} -> grade answer -> update SRS (idempotent penalty)
                   -> compute current_level -> compare to max level_events
                   -> if new level: insert LevelEvent, include level_up in response
                   -> frontend shows toast
```

**Lesson gating:**
```
GET /lessons -> read gating settings -> base query: srs_stage == 0
            -> if dependency_gating: subquery to check components at stage >= 5
            -> if jlpt_gating: filter by computed current JLPT level
            -> order by level, id -> limit batch_size
```

### Code Patterns

Existing review route pattern (reviews.py):
```python
@router.post("/reviews/{subject_id}")
def submit_review(subject_id: int, req: AnswerRequest, db: Session = Depends(get_db)):
    item = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    # ... grade, update SRS, commit, return result
```

Existing subject dict pattern (subjects.py):
```python
def _subject_to_dict(s: Subject) -> dict:
    return {
        "id": s.id, "type": s.type, "characters": s.characters,
        # ... parse JSON fields
    }
```

Existing migration pattern (migrate_v2.py):
```python
def add_column_if_not_exists(conn, table, column, col_type, default=None):
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        # ALTER TABLE ...
```

## File References
- `backend/routes/reviews.py` — SRS penalty logic to fix (lines 104-132)
- `backend/routes/lessons.py` — lesson query to add gating (lines 22-45)
- `backend/srs_engine.py` — check_answer_meaning_detailed to extend
- `backend/models.py` — SrsItem, new LevelEvent model
- `backend/migrate_v2.py` — idempotent migration additions
- `backend/routes/subjects.py` — _subject_to_dict, reset/resurrect endpoints
- `backend/routes/stats.py` — recently-unlocked, level-history endpoints
- `backend/tests/conftest.py` — shared test fixtures
- `frontend/src/pages/Reviews.jsx` — info panel integration
- `frontend/src/pages/Lessons.jsx` — context screen, richer study phase
- `frontend/src/pages/SubjectDetail.jsx` — visually similar, reset/resurrect
- `frontend/src/pages/Dashboard.jsx` — recently unlocked, level timeline
- `frontend/src/api.js` — new API methods

## Success Criteria
- [ ] Wrong meaning + wrong reading = single stage drop (test with stage 5+ item)
- [ ] Lessons filtered by dependency gating when enabled
- [ ] Lessons filtered by JLPT gating when enabled
- [ ] "auxilary" accepted meanings pass review validation
- [ ] GET /reviews returns full subject data including components
- [ ] Item info panel toggles with f key during review
- [ ] Lessons show context sentences for vocabulary
- [ ] Lessons show visually similar for kanji
- [ ] POST /subjects/{id}/reset returns item to stage 0
- [ ] POST /subjects/{id}/resurrect returns burned item to stage 1
- [ ] Visually similar kanji section appears on SubjectDetail for kanji
- [ ] Recently unlocked items appear on dashboard
- [ ] Level-up event persisted in level_events table
- [ ] Level-up toast displayed after triggering review
- [ ] Level timeline card appears on dashboard
- [ ] All 89+ existing tests pass
