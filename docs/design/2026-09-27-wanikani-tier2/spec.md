# WaniKani Tier 2 — Core Parity Features

**Date:** 2026-09-27
**Status:** Validated

## Context
Second round brought extra study, forecast, critical items, typo detection, synonyms, and lesson re-queue. The app still diverges from WaniKani in key areas: no item info during reviews, incomplete lesson data, missing gating, SRS double-penalty bug, no reset/resurrect, no visually similar kanji, no recently unlocked, no level-up history.

## Decision
Implement 6 high-impact features plus 3 bug fixes that together bring the learning experience to WaniKani parity.

## Requirements

### Bug Fixes
- SRS penalty is idempotent per review session (one drop max regardless of how many wrong answers)
- Lesson gating enforces dependency_gating (components must be Guru) and jlpt_gating settings
- Auxiliary meanings are checked during answer validation

### Features
1. **Item Info Panel in Reviews** — collapsible panel after answering showing full item details; toggle with `f` key or button; auto-expanded on wrong
2. **Richer Lessons** — teach phase includes components, context sentences, part of speech, hints; vocab gets a third "Context" screen
3. **SRS Reset / Resurrect** — reset any started item to stage 0; resurrect burned items to stage 1 with immediate review availability
4. **Visually Similar Kanji** — displayed on SubjectDetail and during kanji lessons
5. **Recently Unlocked on Dashboard** — items started in last 48 hours
6. **Level-up History** — persistent level_events table, auto-detected on review, toast on level-up, timeline on dashboard

## Constraints
- No new npm dependencies beyond what's already installed (framer-motion, lucide-react, sonner, wanakana)
- SQLite migration must be idempotent (CREATE TABLE IF NOT EXISTS, ALTER TABLE with column existence check)
- Single-user, no auth changes

## Out of Scope
- Audio playback for vocabulary
- User meaning/reading notes (freetext)
- Review statistics/history tracking
- Global search in nav
- Vacation mode
- Dark/light theme toggle

## Success Criteria
- [ ] Wrong meaning + wrong reading in same review only drops SRS once
- [ ] Lessons respect dependency and JLPT gating settings
- [ ] Auxiliary meanings accepted during reviews
- [ ] Item info panel visible during reviews with full subject data
- [ ] Lessons show components, context sentences, hints, part of speech
- [ ] Can reset and resurrect items from SubjectDetail
- [ ] Visually similar kanji displayed on subject detail and kanji lessons
- [ ] Dashboard shows recently unlocked items
- [ ] Level-up events persisted and displayed with toast notification
- [ ] All existing tests pass, new tests added for all new functionality
