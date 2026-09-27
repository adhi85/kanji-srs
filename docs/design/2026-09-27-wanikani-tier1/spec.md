# WaniKani Tier 1 Features — Spec

## Status: Approved

## Features

### 1. Meaning/Reading Visual Differentiation
- Meaning questions: charcoal (#333) answer-type bar with white text
- Reading questions: type-colored answer-type bar with white text
- Applies to Reviews and Lesson quiz phases

### 2. On'yomi/Kun'yomi Reading Hints
- Fix: `check_answer_reading` must respect `accepted_answer: false` flag
- When kanji review reading answer matches a non-accepted reading (e.g., kun'yomi when on'yomi wanted):
  - Backend returns `{retry: true, hint: "We're looking for the on'yomi reading"}`
  - No SRS penalty applied
  - Frontend shakes, shows hint, clears input for retry

### 3. Wrong Input Type Warning
- Frontend-only detection:
  - Meaning asked + all kana typed → shake + "We want the meaning, not the reading"
  - Reading asked + all ASCII typed → shake + "We want the reading, not the meaning"
- No API call, no SRS penalty, input cleared for retry

### 4. Retype Button
- After wrong answer, show "Retype" alongside "Next →"
- Clears answer, hides result, re-focuses input
- SRS penalty already applied (no reversal)

### 5. Extra Study Modes
- `GET /extra-study?mode=recent_mistakes|recent_lessons`
  - recent_mistakes: items with incorrect_count > 0, sorted by last_incorrect_at desc, limit 25
  - recent_lessons: items where started_at > now - 86400, limit 25
- Returns same format as lessons endpoint (with components)
- Frontend: `/extra-study` page with mode selector, quiz UI, no SRS changes
- Dashboard: third card linking to extra study

### 6. User Synonyms
- Table `user_synonyms` already exists in model
- Endpoints: `POST /subjects/{id}/synonyms`, `DELETE /subjects/{id}/synonyms/{synonym_id}`
- Review endpoint loads user synonyms and checks alongside official meanings
- SubjectDetail: "Add Synonym" input with remove buttons
- `GET /subjects/{id}` response includes `user_synonyms` array

### 7. Review Forecast
- `GET /forecast` — review counts for next 24 hours grouped by hour
- Dashboard: CSS bar chart showing upcoming reviews per hour

## Bug Fix
- `check_answer_reading` currently accepts ALL readings regardless of `accepted_answer` flag
- Must filter to only accept readings where `accepted_answer` is not false

## Existing Infrastructure
- `UserSynonym` model exists (id, subject_id, meaning)
- `last_incorrect_at` column exists on SrsItem (never set)
- `accepted_answer` flag exists in readings JSON data
- Readings have `type` field: "onyomi", "kunyomi", "nanori"
