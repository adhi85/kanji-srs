# WaniKani Tier 1 — Implementation Plan

## Tasks

### Task 1: Fix check_answer_reading to respect accepted_answer
- File: `backend/srs_engine.py`
- Filter readings to only accept where `accepted_answer` is not explicitly false
- Add `check_reading_hint` function that checks non-accepted readings for hint text

### Task 2: Backend — On'yomi hint in review endpoint
- File: `backend/routes/reviews.py`
- When answer_type=reading and subject is kanji:
  - If answer is a valid-but-non-accepted reading, return `{retry: true, hint: "..."}`
  - No SRS stage change, no incorrect_count increment

### Task 3: Backend — Set last_incorrect_at on wrong answers
- File: `backend/routes/reviews.py`
- Set `item.last_incorrect_at = time.time()` when answer is incorrect

### Task 4: Backend — Extra study endpoint
- File: `backend/routes/extra_study.py` (new)
- `GET /extra-study?mode=recent_mistakes|recent_lessons`
- Returns subjects with meanings, readings, mnemonics, components
- Register in main.py

### Task 5: Backend — User synonym endpoints
- File: `backend/routes/synonyms.py` (new)
- `POST /subjects/{id}/synonyms` and `DELETE /subjects/{id}/synonyms/{synonym_id}`
- Modify `backend/routes/subjects.py` to include user_synonyms in detail
- Modify `backend/routes/reviews.py` to check user synonyms for meaning answers
- Register in main.py

### Task 6: Backend — Review forecast endpoint
- File: `backend/routes/stats.py`
- Add `GET /forecast` endpoint
- Group next 24h reviews by hour

### Task 7: Frontend — Meaning/Reading visual differentiation
- File: `frontend/src/App.css` — add `.answer-type-meaning` and `.answer-type-reading` styles
- File: `frontend/src/pages/Reviews.jsx` — apply classes based on answerType
- File: `frontend/src/pages/Lessons.jsx` — apply classes in quiz phase

### Task 8: Frontend — Review hints, warnings, and retype
- File: `frontend/src/pages/Reviews.jsx`
- On'yomi hint: handle `retry` response, show hint, clear input
- Wrong type warning: detect kana-for-meaning / ascii-for-reading before submit
- Retype button: add alongside Next when result is wrong

### Task 9: Frontend — Extra Study page
- File: `frontend/src/pages/ExtraStudy.jsx` (new)
- Mode selector, quiz UI (practice, no SRS)
- File: `frontend/src/App.jsx` — add route
- File: `frontend/src/api.js` — add getExtraStudy method
- File: `frontend/src/pages/Dashboard.jsx` — add Extra Study card

### Task 10: Frontend — User Synonyms on SubjectDetail
- File: `frontend/src/pages/SubjectDetail.jsx` — add synonym section
- File: `frontend/src/api.js` — add addSynonym, deleteSynonym methods

### Task 11: Frontend — Review Forecast on Dashboard
- File: `frontend/src/pages/Dashboard.jsx` — add forecast chart
- File: `frontend/src/App.css` — add forecast chart styles
- File: `frontend/src/api.js` — add getForecast method

### Task 12: Backend tests
- Test reading hint, extra study, synonyms, forecast endpoints

### Task 13: Verify and fix
- Run all tests
- Build frontend
- Manual verification
