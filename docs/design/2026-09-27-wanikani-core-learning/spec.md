# WaniKani Core Learning Parity Specification

**Date:** 2026-09-27
**Status:** Draft

## Context

The kanji-srs app has a working foundation (dashboard, lessons, reviews, browsing, settings) but is missing several WaniKani features that make the difference between a prototype and a daily study tool. This round focuses on the core learning loop: the features you interact with every study session.

## Decision

Build six features that close the biggest gaps with WaniKani's learning experience:

1. **Enhanced data import** — Pull context_sentences, meaning/reading hints, auxiliary meanings, and visually similar kanji IDs from WaniKani's API
2. **Extra Study modes** — Practice recent mistakes, recent lessons, and burned items without affecting SRS
3. **Review Forecast** — Dashboard widget showing upcoming reviews by hour and day
4. **Lesson quiz re-queue** — Wrong items re-appear later in the quiz (matching WK behavior)
5. **Answer validation** — Levenshtein-based typo tolerance and user-defined synonym meanings
6. **Critical condition items** — Identify and display leech items on dashboard

## Requirements

- Extra Study must not affect SRS progress (practice-only)
- Review forecast should cover next 24 hours (hourly) and next 5 days (daily)
- Typo detection must distinguish "close enough" from "wrong" without accepting truly wrong answers
- Leech detection must require sufficient data (minimum 4 incorrect) before flagging
- Re-import must preserve existing SRS progress
- No new npm or pip dependencies (pure implementations only)

## Constraints

- SQLite database; schema changes via ALTER TABLE
- Frontend: React 19 + pure CSS, no component libraries
- WaniKani API token needed for re-import of enriched data
- Must not break existing 54 backend tests

## Out of Scope

- Audio playback (requires hosting/proxying audio files)
- Mobile app or PWA
- Full dashboard widget system (WK's new modular dashboard)
- Review reordering/priority settings
- Radical SVG images

## Open Questions

- [ ] None — proceeding with recommended approach

## Success Criteria

- [ ] All six features functional and tested
- [ ] Extra Study modes accessible from dashboard
- [ ] Review forecast displays on dashboard
- [ ] Wrong lesson quiz items re-queued until correct
- [ ] Typo tolerance prevents frustrating false negatives
- [ ] Critical condition items shown on dashboard
- [ ] All existing + new tests pass
