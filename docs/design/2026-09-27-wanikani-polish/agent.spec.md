# WaniKani-Style Full Polish - Agent Specification
**Status:** Validated

## Requirements

### Functional
- Design system with WaniKani type colors and shared React components
- Dashboard with level progress, session cards, SRS breakdown
- Multi-phase lesson flow (teach then quiz) with rendered mnemonics
- Enhanced review flow with wrap-up, animations, mnemonic display on wrong
- Level grid browser, level detail page, item detail page with proper routes
- Settings page exposing all backend settings
- Enhanced navigation with level badge and count badges

### Non-functional
- No new frontend dependencies
- Keep dark theme base
- All pages must work without JavaScript errors
- Responsive on desktop (mobile nice-to-have but not required)

## Constraints
- React 19 + React Router v7 + wanakana.js (existing stack, no additions)
- Pure CSS (no Tailwind, no component library)
- SQLite backend, single-user
- Backend is FastAPI + SQLAlchemy

## Approach

Incremental enhancement: create a CSS design system, build shared components, then enhance each page one at a time. Add 3 new backend endpoints and enhance 2 existing ones. Add 3 new frontend routes.

## Design

### Architecture

```
frontend/src/
  components/           # NEW: shared components
    TypeBadge.jsx        # Colored pill for radical/kanji/vocab
    MnemonicRenderer.jsx # Parses <radical>/<kanji>/<vocabulary> tags → colored spans
    SrsStageBar.jsx      # Visual SRS stage indicator
    ItemCard.jsx         # Clickable card: character + meaning + type color
    ProgressBar.jsx      # Reusable progress bar with label
  pages/
    Dashboard.jsx        # REWRITE: level progress, session cards, SRS breakdown
    Lessons.jsx          # REWRITE: multi-phase teach → quiz flow
    Reviews.jsx          # ENHANCE: wrap-up, animations, better feedback
    Subjects.jsx         # REWRITE: level grid + list views
    SubjectDetail.jsx    # NEW: item detail page
    LevelDetail.jsx      # NEW: level detail page
    Settings.jsx         # NEW: settings form
  App.jsx                # ENHANCE: new routes, nav redesign
  App.css                # REWRITE: CSS variables, design system, all styles
  api.js                 # ENHANCE: new API calls

backend/routes/
  levels.py              # NEW: level list + detail endpoints
  subjects.py            # ENHANCE: add used_in to detail
  stats.py               # ENHANCE: add current level + level progress
```

### Key Components

| Component | Responsibility | Location |
|-----------|---------------|----------|
| TypeBadge | Render colored type pill | `frontend/src/components/TypeBadge.jsx` |
| MnemonicRenderer | Parse mnemonic HTML tags → React elements | `frontend/src/components/MnemonicRenderer.jsx` |
| SrsStageBar | Show SRS stage visually | `frontend/src/components/SrsStageBar.jsx` |
| ItemCard | Clickable item display card | `frontend/src/components/ItemCard.jsx` |
| ProgressBar | Generic progress bar | `frontend/src/components/ProgressBar.jsx` |
| LevelDetail | Level page with grouped items | `frontend/src/pages/LevelDetail.jsx` |
| SubjectDetail | Item detail with mnemonics, components | `frontend/src/pages/SubjectDetail.jsx` |
| Settings | Settings form | `frontend/src/pages/Settings.jsx` |
| levels router | Level list + detail API | `backend/routes/levels.py` |

### Data Flow

**MnemonicRenderer**: Input is raw mnemonic string like `"The <radical>ground</radical> is <kanji>One</kanji>"`. Parser splits on `<radical>`, `<kanji>`, `<vocabulary>`, `<meaning>`, `<reading>` tags and renders each as a `<span>` with the corresponding type's CSS class.

**Current Level Computation**: Query all kanji subjects grouped by WK level. For each level 1-60, count how many have `srs_stage >= 5` (Guru+). The current level is `max(level where 90%+ kanji are Guru+) + 1`, clamped to 1-60. If no levels are complete, current level = 1.

**Level Progress**: For the current level, return counts of radicals/kanji/vocab at each SRS stage.

### API Changes

**New: `GET /api/levels`**
```json
{
  "current_level": 12,
  "levels": [
    {
      "level": 1,
      "radical_count": 26,
      "kanji_count": 26,
      "vocab_count": 50,
      "radical_passed": 26,
      "kanji_passed": 26,
      "vocab_passed": 45
    }
  ]
}
```

**New: `GET /api/levels/{level}`**
```json
{
  "level": 12,
  "radicals": [
    {"id": 1, "characters": "一", "type": "radical", "meanings": [...], "srs_stage": 5}
  ],
  "kanji": [...],
  "vocabulary": [...]
}
```

**Enhanced: `GET /api/subjects/{id}`** — add `used_in` field:
```json
{
  "id": 1,
  "used_in": [
    {"id": 45, "characters": "大", "type": "kanji", "meanings": [...]}
  ]
}
```

**Enhanced: `GET /api/summary`** — add level progress:
```json
{
  "current_level": 12,
  "level_progress": {
    "level": 12,
    "kanji_total": 30,
    "kanji_passed": 18,
    "radical_total": 10,
    "radical_passed": 10
  }
}
```

### CSS Design System

```css
:root {
  /* Type colors */
  --color-radical: #00aaff;
  --color-kanji: #cc00ff;
  --color-vocabulary: #7c2ae8;
  --color-kana-vocabulary: #7c2ae8;

  /* SRS stage colors */
  --color-apprentice: #dd0093;
  --color-guru: #882d9e;
  --color-master: #294ddb;
  --color-enlightened: #0093dd;
  --color-burned: #434343;

  /* Base theme (keep dark) */
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-card: #1f2940;
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0b0;
  --text-accent: #ffffff;

  /* Feedback */
  --color-correct: #4ecca3;
  --color-incorrect: #e94560;
}
```

### Routing

```jsx
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/lessons" element={<Lessons />} />
  <Route path="/reviews" element={<Reviews />} />
  <Route path="/subjects" element={<Subjects />} />
  <Route path="/subjects/:id" element={<SubjectDetail />} />
  <Route path="/levels/:level" element={<LevelDetail />} />
  <Route path="/settings" element={<Settings />} />
</Routes>
```

### Code Patterns

**MnemonicRenderer parsing pattern:**
```jsx
function MnemonicRenderer({ text }) {
  if (!text) return null;
  const parts = [];
  const regex = /<(radical|kanji|vocabulary|meaning|reading)>(.*?)<\/\1>/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<span className={`mnemonic-${match[1]}`}>{match[2]}</span>);
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return <span>{parts}</span>;
}
```

**API call pattern (follow existing api.js style):**
```js
export async function fetchLevels() {
  const res = await fetch('/api/levels');
  if (!res.ok) throw new Error('Failed to fetch levels');
  return res.json();
}
```

**Backend route pattern (follow existing routes):**
```python
@router.get("/levels")
def get_levels(db: Session = Depends(get_db)):
    ...
```

## File References

Files the plan agent MUST read before planning:
- `frontend/src/App.jsx` - current routing and navigation
- `frontend/src/App.css` - current styling (will be rewritten)
- `frontend/src/api.js` - API call patterns
- `frontend/src/pages/Dashboard.jsx` - current dashboard implementation
- `frontend/src/pages/Lessons.jsx` - current lesson flow
- `frontend/src/pages/Reviews.jsx` - current review flow
- `frontend/src/pages/Subjects.jsx` - current subjects browser
- `backend/models.py` - SQLAlchemy models (Subject, SrsItem, etc.)
- `backend/routes/subjects.py` - subject API patterns
- `backend/routes/stats.py` - summary endpoint to enhance
- `backend/routes/lessons.py` - lesson API
- `backend/routes/reviews.py` - review API
- `backend/main.py` - FastAPI app setup, router inclusion
- `frontend/package.json` - current dependencies

## Success Criteria

- [ ] CSS variables define all type and SRS colors
- [ ] MnemonicRenderer correctly parses all tag types and renders colored spans
- [ ] Dashboard shows current level with progress bar
- [ ] Dashboard shows SRS stage breakdown in WK colors
- [ ] Lessons have teaching phase with meaning/reading/component screens
- [ ] Lessons quiz separates meaning and reading questions
- [ ] Reviews have wrap-up button that finishes current items then ends
- [ ] Reviews show mnemonic on wrong answer
- [ ] Level grid at /subjects shows 60 levels with progress
- [ ] /levels/:level shows items grouped by type
- [ ] /subjects/:id shows full item detail with components and used-in
- [ ] Settings page reads and writes all settings via API
- [ ] Navigation has level badge and lesson/review count badges
- [ ] Backend /api/levels and /api/levels/:level endpoints work
- [ ] Backend /api/subjects/:id includes used_in
- [ ] Backend /api/summary includes current_level and level_progress
