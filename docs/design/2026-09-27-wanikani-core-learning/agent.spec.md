# WaniKani Core Learning Parity - Agent Specification

## Requirements

### Functional
- Import context_sentences, meaning_hint, reading_hint, auxiliary_meanings, visually_similar_subject_ids from WK API
- Three Extra Study modes (recent_mistakes, recent_lessons, burned) with no SRS impact
- Review forecast API returning hourly (24h) and daily (5-day) bucketed counts
- Lesson quiz re-queues wrong items to later positions in the queue
- Levenshtein-based typo detection with "close" state (no penalty, re-try prompt)
- User synonym table for custom accepted meanings per subject
- Critical condition / leech detection (incorrect_count >= 4 AND error_rate > 50%)

### Non-Functional
- No new pip/npm dependencies
- All existing 54 backend tests must continue to pass
- Pure CSS for all new UI (no Tailwind, no component library)

## Constraints

- SQLite: use ALTER TABLE ADD COLUMN for schema changes (no migration framework)
- PYTHONPATH="" must prefix all python commands (ros_noetic_ws contamination)
- Use `rtk proxy <cmd>` for pytest to bypass hook filtering
- WaniKani API token stored in environment, not committed

## Approach

Six features implemented incrementally, each with backend API + frontend UI + tests.

## Design

### Architecture

Existing architecture stays the same: FastAPI backend, React 19 frontend, SQLite DB. New features add endpoints to existing route files or create minimal new route files.

### Key Components

| Component | Responsibility | Location |
|-----------|---------------|----------|
| DB migration script | Add columns to subjects + srs_items | `backend/migrate_v2.py` |
| Enhanced import | Pull additional WK API fields | `backend/import_wanikani.py` (modify) |
| Extra Study API | Fetch practice items, submit without SRS | `backend/routes/extra_study.py` (new) |
| Forecast API | Bucket upcoming reviews by time | `backend/routes/stats.py` (modify) |
| Levenshtein util | Edit distance calculation | `backend/srs_engine.py` (modify) |
| User synonyms | CRUD for custom meanings | `backend/routes/subjects.py` (modify) |
| User synonyms model | DB model | `backend/models.py` (modify) |
| Critical items API | Leech detection query | `backend/routes/stats.py` (modify) |
| Extra Study page | Quiz UI for practice modes | `frontend/src/pages/ExtraStudy.jsx` (new) |
| Forecast widget | Bar chart on dashboard | `frontend/src/components/ReviewForecast.jsx` (new) |
| CriticalItems widget | Leech display on dashboard | `frontend/src/components/CriticalItems.jsx` (new) |
| Lesson quiz fix | Re-queue wrong items | `frontend/src/pages/Lessons.jsx` (modify) |
| Review typo handling | Close-enough detection UI | `frontend/src/pages/Reviews.jsx` (modify) |

### Data Flow

**Extra Study:**
1. Dashboard shows counts for each mode via `/api/extra-study/summary`
2. User clicks a mode -> navigates to `/extra-study/:mode`
3. Page fetches items from `GET /api/extra-study?mode=:mode`
4. Quiz answers submitted to `POST /api/extra-study/:subject_id` (no SRS changes)
5. Session ends -> summary shown -> back to dashboard

**Review Forecast:**
1. Dashboard fetches `GET /api/forecast`
2. Backend queries `SELECT next_review_at FROM srs_items WHERE srs_stage BETWEEN 1 AND 8 AND next_review_at > :now`
3. Groups into hourly buckets (next 24h) and daily buckets (next 5 days)
4. Frontend renders CSS-only bar chart

**Typo Detection:**
1. User submits answer in review
2. Backend calls `check_answer_meaning()` or `check_answer_reading()`
3. If exact match: correct
4. If no match: compute Levenshtein distance to all accepted answers
5. If distance <= threshold: return `{"correct": false, "close": true}` (no SRS penalty applied yet)
6. Frontend shows yellow state, user can re-type
7. If truly wrong (distance > threshold): normal wrong flow with SRS penalty

**Lesson Re-queue:**
1. User answers wrong in lesson quiz
2. Show correct answer + mnemonic
3. On continue: splice current item into random later position in queue
4. Track per-item wrong count; after 3 failures on same question, accept and move on

### Code Patterns

Follow existing patterns in the codebase:

```python
# Route pattern (from backend/routes/reviews.py)
@router.get("/extra-study")
def get_extra_study(mode: str, db: Session = Depends(get_db)):
    ...
    return [{"subject_id": ..., "type": ..., "characters": ...}]
```

```python
# Levenshtein (pure implementation, no dependency)
def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]
```

```jsx
// Frontend component pattern (from Dashboard.jsx)
export default function ReviewForecast({ data }) {
  const maxCount = Math.max(...data.map(d => d.count), 1);
  return (
    <div className="forecast-chart">
      {data.map(d => (
        <div key={d.hour} className="forecast-bar-container">
          <div className="forecast-bar" style={{ height: `${(d.count / maxCount) * 100}%` }} />
          <div className="forecast-label">{d.label}</div>
        </div>
      ))}
    </div>
  );
}
```

### DB Schema Changes

```sql
-- subjects table additions
ALTER TABLE subjects ADD COLUMN context_sentences TEXT;
ALTER TABLE subjects ADD COLUMN meaning_hint TEXT;
ALTER TABLE subjects ADD COLUMN reading_hint TEXT;
ALTER TABLE subjects ADD COLUMN auxiliary_meanings TEXT;
ALTER TABLE subjects ADD COLUMN visually_similar_subject_ids TEXT;

-- srs_items table additions
ALTER TABLE srs_items ADD COLUMN last_incorrect_at REAL;

-- new table for user synonyms
CREATE TABLE IF NOT EXISTS user_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    meaning TEXT NOT NULL,
    UNIQUE(subject_id, meaning)
);
```

## File References

Files the plan agent MUST read before planning:
- `backend/models.py` - current SQLAlchemy models
- `backend/srs_engine.py` - SRS logic, answer checking functions
- `backend/routes/reviews.py` - review submission flow
- `backend/routes/lessons.py` - lesson fetch and start flow
- `backend/routes/stats.py` - summary endpoint (add forecast + critical items)
- `backend/routes/subjects.py` - subject detail endpoint (add synonyms)
- `backend/import_wanikani.py` - current import script
- `frontend/src/pages/Dashboard.jsx` - dashboard layout (add widgets)
- `frontend/src/pages/Lessons.jsx` - lesson quiz logic (fix re-queue)
- `frontend/src/pages/Reviews.jsx` - review quiz logic (add typo detection)
- `frontend/src/App.jsx` - routes and navigation
- `frontend/src/App.css` - CSS design system
- `frontend/src/api.js` - API client methods

## Success Criteria

- [ ] DB schema has new columns; migration script runs idempotently
- [ ] Import script pulls all new fields from WK API
- [ ] GET /api/extra-study?mode=recent_mistakes returns items failed in last 24h
- [ ] GET /api/extra-study?mode=recent_lessons returns items started in last 24h
- [ ] GET /api/extra-study?mode=burned returns items at stage 9
- [ ] POST /api/extra-study/:id does NOT change srs_stage
- [ ] GET /api/forecast returns hourly + daily bucketed review counts
- [ ] Lesson quiz re-queues wrong items (max 3 retries per question)
- [ ] Typo within edit distance 1-2 shows "close" state, no SRS penalty
- [ ] User synonyms CRUD works; synonyms checked during review
- [ ] Critical items endpoint returns top leeches by error rate
- [ ] Dashboard shows forecast chart, critical items, extra study buttons
- [ ] All existing + new backend tests pass
- [ ] Frontend builds without errors
