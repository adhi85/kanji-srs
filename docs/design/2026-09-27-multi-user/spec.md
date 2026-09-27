# Multi-User Support Specification

**Date:** 2026-09-27
**Status:** Validated

## Context

The app is currently single-user — one SQLite database stores all SRS progress with no user isolation. A friend wants to use the app too, but they'd share the same progress data. We need to separate learning state per user while keeping shared reference data (kanji definitions, dependencies) global.

## Decision

Add user accounts with username/password authentication (JWT). All user-specific data (SRS progress, settings, synonyms, level history) gets a `user_id` foreign key. Shared reference data (subjects, dependencies) remains global.

## Requirements

- Users register with username + password and log in to get a JWT token
- Each user has independent SRS progress, settings, synonyms, and level history
- Existing data is migrated to a default `adhi` account
- Open registration — anyone with access can create an account
- JWT tokens last 30 days, no refresh token mechanism
- All API endpoints (except auth) require authentication

## Approach

- **Auth:** JWT access tokens via `python-jose` + `passlib[bcrypt]`. Secret key stored in `data/.jwt_secret` (generated once on first startup).
- **Data model:** New `User` table. Add `user_id` FK to `SrsItem`, `UserSynonym`, `LevelEvent`, `Setting`. Update unique constraints to be per-user.
- **Settings:** Per-user. Default settings seeded at registration time (not globally on startup).
- **SrsItem creation:** Lazy — created per-user when a lesson is started, not bulk-created at registration.
- **Frontend:** Auth context + protected routes. Login/Register pages. Token in localStorage, sent as Bearer header. Nav shows username + logout.

## Constraints

- SQLite — no concurrent write concerns at this scale, but ALTER TABLE is limited (no column rename/drop). Migration uses raw SQL.
- Single-process deployment — no session store needed beyond JWT.
- Subject/SubjectDependency tables unchanged — shared reference data.

## Out of Scope

- Admin role / user management UI
- Password reset or email verification
- Profile editing (username change)
- Rate limiting on auth endpoints
- "Remember me" toggle
- Concurrent session limits
- Refresh tokens

## Open Questions

- None

## Success Criteria

- [ ] Two users can register, log in, and have fully independent SRS progress
- [ ] Existing `adhi` user retains all current learning data after migration
- [ ] All existing tests pass (updated for auth)
- [ ] Unauthenticated requests to `/api/*` (except `/api/auth/*`) return 401
