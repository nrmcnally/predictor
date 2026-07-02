# FIGHT IQ — Frontend UI Critique & Redesign Gameplan (Phase 4)

_Written 2026-07-02, after the first week live with real users. This is the working
brief for the Phase 4 redesign: what exists, what's wrong (grounded in measurements
and real user feedback), and a staged plan. ROADMAP.md §Phase 4 points here._

---

## 1. Current state — inventory

**Views (13):** Login (+ register), FightLab, FighterProfile, FutureCards,
RecentCards, MyPicks (picks + card leaderboards + pick queue dashboard), Friends
(requests + head-to-head + upcoming compare), Leaderboards (fighters),
UserLeaderboard, Evaluation (admin), UpdateData (admin), UsersAdmin (admin), Profile.

**Shared components (thin layer):** `ui.jsx` (SectionCard, StatTile, Tag, Spinner,
EmptyState, ErrorNote, MeterBar, SplitBar), `FighterDisplay.jsx` (FighterAvatar/Name/
Matchup), `UserAvatar.jsx`, `EloTrendChart`, `PredictionBreakdown`,
`FighterSearchInput`. Everything else is per-view markup.

**Navigation:** fixed sidebar (nav groups Analyze/Events/Intel/Admin) + topbar
(brand, status pills, user chip). Tab state syncs to the URL hash (`#/picks`) —
Back/Forward work at tab level only; **no deep state in URLs** (fighter profile,
selected card, expanded compare are all in-memory).

**Styling:** one `index.css` — **4,537 lines**, no modules/scoping; design tokens in
`:root` are real and mostly used (520 `var()` refs vs 39 stray hex), but naming has
drifted (`tone-win/loss/warn/gold` vs `tone-red/green/blue/amber` both exist).
Fonts: Barlow Condensed (display) / Inter (body) / JetBrains Mono. Dark theme only.

**Measured problems:**
- Shell capped at `max-width: 1460px`; inner content columns at 720–1180px.
- Only **9 media queries** in 4,537 lines — desktop-first with token responsiveness.
- **75 occurrences of sub-13px font sizes** — the app leans tiny everywhere.
- **0 frontend tests**; no loading skeletons (spinners only); `window.confirm` for
  destructive/confirm flows; emoji-glyph icons (⚔ ◎ ▸ ↺ ♛ ◉ ◈ ◫ ⚇ ⟳) render
  inconsistently across platforms.

---

## 2. Critique — ranked by user impact

### 2.1 Density & scale (REAL USER FEEDBACK — top priority)
First live feedback: *"UI is too small and should use up more of the screen."*
Measurements agree: on a 1440p+ monitor, ≥40% of the viewport is dead margin
(1460px shell), and inside it the type is small (12–13px body in many places, 10–11px
labels). The app reads like a dense dashboard shrunk into a letterboxed column.
**Fix direction:** fluid shell (~90vw up to ~1800px), a spacing/type scale that grows
with viewport (CSS `clamp()`), and per-view multi-column use of the width (e.g. My
Picks fight list could be 2-up on wide screens; Fight Lab verdict + breakdown side by
side). Raise the *floor* font size to 13–14px; reserve 10–11px for true captions.

### 2.2 Mobile is untested and likely broken in places
Friends will check picks from phones. 9 media queries can't cover 13 views; known
suspects: the 4-column stat tile rows, the Users admin table, MyPicks pick cards
(2-col grid), compare panels, the sidebar (has a scrim toggle — good — but touch
targets are small). **Fix direction:** audit every view at 375px & 768px; stack
tile rows; tables → card lists on small screens; minimum 44px touch targets.

### 2.3 Information hierarchy / progressive disclosure
Screens front-load everything: Fight Lab shows verdict + probabilities + method +
breakdown + context at once; Future Cards rows carry 6+ tags/pills each (roadmap
critique #5 "de-clutter tags" still open); Evaluation is a wall of expert panels
(roadmap #4 Overview-vs-Deep-Dive split still open). **Fix direction:** each screen
gets ONE headline answer, details behind expanders; define 2–3 tag slots max per
row; move rarely-used controls into menus.

### 2.4 Consistency drift (organic growth showing)
- Two button systems (`.btn*` vs `.chip`) with unclear roles; `pick-clear` reused as
  a generic tertiary button in Friends/Profile (naming lies).
- Two tone vocabularies for tags/tiles; podium styling duplicated across three
  leaderboard renderings (Leaderboards, UserLeaderboard, MyPicks card boards).
- Row patterns re-implemented per view (friend-row vs leaderboard-row vs data-table).
**Fix direction:** extract a real component set — `LeaderboardRow`, `UserBadge`
(avatar+name), `Button` (primary/secondary/tertiary/danger), `ToggleSwitch`,
`ConfirmDialog` — and delete the per-view copies.

### 2.5 Accessibility (roadmap #6, untouched)
- Color-only signals in places (win/loss green/red, calibration colors) — needs
  icons/text doubling; palette not checked for color-blind safety.
- Sub-12px text fails comfortable-reading; contrast of `--faint` (#6b7390) on
  `--bg0` is borderline for small text.
- Focus states are default-browser at best; keyboard flow through pick cards works
  (role=button work done) but most cards/rows aren't focusable; `window.confirm`
  dialogs aren't styled or screen-reader friendly.
- Emoji icons have no aria labels and render platform-dependently → replace with an
  SVG icon set (lucide or hand-rolled) with `aria-hidden` + text labels.

### 2.6 CSS architecture
One 4,537-line file with append-only history (several "profile" blocks, two tag tone
systems). It works, but every change risks collisions (we hit `.profile-name` and
`.pick-option-name` conflicts this week). **Fix direction:** split by
component/view into CSS modules or at least `@layer`-organized files; single tone
vocabulary; document the tokens; delete dead rules (audit — the file has grown ~700
lines in a week).

### 2.7 Perceived performance & feedback
- Spinners everywhere, no skeletons — tab switches flash empty then pop.
- The JS bundle is one ~860KB chunk (Vite warns); three.js loads even for users who
  go straight past login. **Fix:** lazy-load OctagonScene + admin/evaluation views
  (`React.lazy`), skeleton rows for lists, optimistic UI already exists for picks
  (good — keep).
- Machine cold-start (Fly auto-sleep) shows as a long white load — add an app-shell
  "waking the server…" state so it doesn't look broken.

### 2.8 Navigation depth
Hash routing covers tabs only. Missing: fighter profile URLs (`#/fighters/Tom-
Aspinall`), selected card on picks (`#/picks/evt123`), compare deep-link
(`#/friends/compare/5`). Also no document.title updates per tab, no scroll
restoration on Back.

### 2.9 Small paper cuts (collect-as-you-go list)
- `window.confirm`/temp-password reveal → proper modal component.
- No favicon-level PWA bits (manifest, icons) — roadmap wants PWA-capable.
- Data-age banner + offline banner + sandbox pill can stack into a wall of banners.
- Login page: three.js scene on mobile is heavy; register form has no password-
  confirm field.
- Empty states are good copy-wise — keep that voice through the redesign.

---

## 3. Design direction (what "done" looks like)

Keep the identity — dark, broadcast-premium, deco-sport (it's distinctive and the
users like it). The redesign is about **scale, hierarchy, and consistency**, not a
new brand. Principles:
1. **Fill the screen**: fluid width, density that adapts, desktop gets multi-column.
2. **One answer per screen**, details on demand.
3. **One component system**, one tone vocabulary, tokens documented.
4. **Feels native on a phone** (PWA-ready), readable by everyone (a11y pass).
5. **Ship in slices** — each workstream deployable alone; no big-bang rewrite.

## 4. Workstreams (ordered; each independently shippable)

**W1 — Scale & density pass (the friend feedback, ~quick):**
fluid shell to ~1800px, `clamp()` type scale, raise font floor to 13px, widen inner
columns, 2-up layouts on ≥1400px for MyPicks/FightLab/Friends-compare.
_Accept: side-by-side screenshot at 1440p shows ≥80% width used; no sub-12px body._

**W2 — Component extraction & CSS split:**
Button/Tag/ToggleSwitch/ConfirmDialog/UserBadge/LeaderboardRow; one tone system;
split index.css per component/view; delete dead rules.
_Accept: leaderboard row rendered from ONE component in all three places; index.css
< 1500 lines of truly-global styles._

**W3 — Mobile audit & fixes:** every view at 375/768px; tables→cards; 44px targets;
manifest + icons (PWA install).
_Accept: full pick flow + friends compare completable one-handed on a phone._

**W4 — A11y & icons:** SVG icon set with labels, focus-visible styles, color-blind-
safe win/loss (icon + color), contrast fixes, modal focus traps.
_Accept: axe-core clean on the main flows; keyboard-only pick placement works._

**W5 — Hierarchy passes per view:** Evaluation Overview/Deep-Dive split (#4), tag
de-clutter (#5), Fight Lab verdict-first collapse.
_Accept: each main view has exactly one H1-level takeaway above the fold._

**W6 — Perceived perf:** lazy-load three.js + admin views, skeletons, cold-start
"waking server" state, code-splitting (kills the 860KB chunk warning).
_Accept: no Vite chunk warning; tab switch shows skeleton not blank._

**W7 — Deep URLs + titles:** fighter/card/compare hash params, document.title,
scroll restoration.
_Accept: refresh on a fighter profile restores it; shared link opens exact state._

**W8 — First frontend tests (roadmap Phase 4 item):** Vitest + Testing Library on
the extracted components + pick flow + auth gate; add to CI.
_Accept: CI runs frontend tests; pick flow regression-covered._

## 5. Suggested order & sizing

| Slice | Streams | Size |
|---|---|---|
| 1 (feels better immediately) | W1 | S |
| 2 (foundation) | W2 + W8 started | M |
| 3 (friends on phones) | W3 | M |
| 4 (polish) | W4 + W6 | M |
| 5 (depth) | W5 + W7 | M/L |

Notes for the implementing session: verify against the mock preview
(`fightiq-mock`, port 5180) per view at 375/768/1440/2560 widths; the live app is
fightiq.fly.dev (deploy = `fly deploy --remote-only`); keep the existing empty-state
copy voice; friend feedback lives in ROADMAP §Phase 4.
