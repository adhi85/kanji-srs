# WaniKani-Style Full Polish Specification

**Date:** 2026-09-27
**Status:** Validated

## Context

The kanji-srs app has a working backend (9,452 subjects across 60 WK levels, SRS engine, mnemonics with markup tags, 17k component relationships) but a bare-bones frontend. The UI needs a full polish pass to deliver a WaniKani-like learning experience.

## Decision

Incremental enhancement of the existing 4-page React app: introduce a CSS design system with WaniKani-matching type colors, build shared components, deeply enhance each page, and add new routes for level browsing, item detail, and settings.

## Requirements

### Design System
- WaniKani type colors: radicals (blue #00aaff), kanji (purple #cc00ff), vocabulary (violet #7c2ae8)
- SRS stage colors: Apprentice (pink #dd0093), Guru (purple #882d9e), Master (blue #294ddb), Enlightened (blue #0093dd), Burned (gray #434343)
- CSS custom properties for all colors
- Shared components: TypeBadge, MnemonicRenderer, SrsStageBar, ItemCard, ProgressBar

### Dashboard
- Level progress display showing current WK level with progress bar (% of kanji at Guru+)
- Lesson/review count cards with type breakdowns
- SRS stage breakdown as color-coded bar/grid (clickable to filter subjects)
- JLPT progress as secondary compact bars

### Lessons
- Multi-phase flow: teaching screens (meaning, reading, components with rendered mnemonics) then quiz
- Type-colored backgrounds per item
- MnemonicRenderer parsing <radical>, <kanji>, <vocabulary> tags
- Component items shown as clickable ItemCards
- Quiz with separate meaning/reading questions, wrong-answer mnemonic display

### Reviews
- Wrap-up button to finish current items and end session
- Type-colored header with progress counter
- Feedback animations (green correct, red incorrect with shake)
- Wrong-answer display: correct answer + rendered mnemonic + item context
- Enhanced session summary: items grouped by advancement/retreat, new SRS stages shown

### Subjects Browser
- Level grid view (60 levels with mini progress indicators)
- List view with ItemCard components and filters (type, JLPT, SRS stage, search)
- Type tabs: All / Radicals / Kanji / Vocabulary

### Level Detail Page (/levels/:level)
- Items grouped by type (Radicals, Kanji, Vocabulary) as ItemCard grids
- SRS stage indicator per card

### Item Detail Page (/subjects/:id)
- Proper route (not in-component state)
- Large character on type-colored background
- All meanings and readings with labels
- Rendered meaning and reading mnemonics
- "Built from" components and "Found in" reverse lookups
- SRS progress: stage, correct/incorrect counts, dates
- Part of speech for vocabulary

### Settings Page (/settings)
- Lesson batch size, max reviews, JLPT gating toggle, dependency gating toggle
- SRS intervals (advanced, collapsible)
- Save with feedback

### Navigation
- Fixed top bar with app name, current level badge, nav links with count badges
- Mobile-friendly hamburger menu

## Constraints
- No new JS dependencies beyond what's already installed (React 19, React Router, wanakana)
- Keep the existing dark theme as base
- All data already exists in the SQLite DB; minimal backend changes
- Single-user, no auth

## Out of Scope
- Audio playback
- Context/example sentences (data not imported)
- User authentication
- Reordering lesson queue manually
- Undo/redo for review answers

## Backend Changes Required
- Enhanced `GET /api/summary`: include current level, level-specific progress
- New `GET /api/levels`: level list with progress summary per level
- New `GET /api/levels/{level}`: items in a level grouped by type
- Enhanced `GET /api/subjects/{id}`: add "used_in" reverse component lookup
- Current level computation: highest level where 90%+ kanji are Guru+, next level is current

## Success Criteria
- [ ] Type-colored UI matching WaniKani's visual identity
- [ ] Mnemonics render with highlighted radical/kanji/vocabulary tags
- [ ] Lessons teach with info screens before quizzing
- [ ] Reviews have wrap-up and feedback animations
- [ ] Subjects browsable by WK level grid and as filterable list
- [ ] Item detail pages with components, used-in, and SRS stats
- [ ] Settings page exposes all backend settings
- [ ] Navigation shows level and count badges
- [ ] JLPT shown as secondary indicator alongside WK levels
