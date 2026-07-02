# FIGHT IQ — Frontend Critique & Redesign Gameplan (Phase 4)

_Written 2026-07-02 after the first week live. Two lenses: **UI/UX design** (§2–3)
and **software engineering** (§4). Color/brand changes are explicitly in scope —
the current palette is not sacred. §5 proposes the rework; §6 is the staged plan.
ROADMAP §Phase 4 points here. Verify work in the mock preview (`fightiq-mock`,
port 5180) at 375/768/1440/2560 widths; live app = fightiq.fly.dev._

---

## 1. Inventory (what exists)

- **13 views:** Login(+register), FightLab, FighterProfile, FutureCards, RecentCards,
  MyPicks (picks + pick-queue dashboard + card leaderboards), Friends (requests +
  head-to-head + upcoming compare), Leaderboards (fighters), UserLeaderboard,
  Profile, and admin-only Evaluation / UpdateData / UsersAdmin.
- **Shared components (thin):** ui.jsx (SectionCard, StatTile, Tag, Spinner,
  EmptyState, ErrorNote, MeterBar, SplitBar), FighterDisplay (Avatar/Name/Matchup),
  UserAvatar, EloTrendChart, PredictionBreakdown, FighterSearchInput.
- **Shell:** fixed sidebar (groups: Analyze / Events / Intel / Admin) + topbar
  (brand, status pills, user chip). Hash routing at tab level only (`#/picks`).
- **Styling:** ONE `index.css` = **4,537 lines**; tokens in `:root` (520 `var()`
  uses vs 39 stray hex); fonts Barlow Condensed / Inter / JetBrains Mono; dark only.
- **Measured:** shell `max-width: 1460px`; inner columns 720–1180px; **9** media
  queries total; **75** uses of sub-13px font sizes; **one ~860KB JS chunk**
  (three.js included, loaded even at the login screen); **0 frontend tests**.

---

## 2. UX critique

### 2.1 Color & visual language (rework allowed — see §5)

Current palette: near-black blue-tinted backgrounds (`#05060a → #131726`), neon
accents — red `#ff3355`, gold `#f5c451`, blue `#3d7bff`, green `#2fd58b`, amber,
violet. Problems, ranked:

1. **Red is semantically overloaded.** Red is simultaneously: the brand color, the
   primary CTA (`btn-primary`), the "red corner" fighter, loss/error states, focus
   highlight (`input:focus` border), and hover accents. A red button can mean "go"
   or "danger" depending on context — users can't build an instinct. *This is the
   single biggest visual-design flaw.*
2. **Win/loss is a red/green pair** at similar saturation — the classic
   deuteranopia trap (roadmap #6). Needs a colorblind-safe pair AND icon/text
   doubling (✓/✗ already exist in compare — extend everywhere).
3. **Contrast failures at small sizes.** `--faint` (#6b7390) on surface (~#0e111a)
   is ≈4:1 — below WCAG AA (4.5:1) for the 10–12px text it's most used on. Muted
   text + tiny type compounds the friend's "too small" complaint.
4. **Neon-on-near-black halation.** Fully-saturated accents on #05060a "vibrate,"
   especially thin condensed italics. Slightly lifted backgrounds or slightly
   desaturated accents fix this without losing the mood.
5. **Gold means three things** (your-row highlight, admin role, FIGHT IQ rating) —
   acceptable, but should be deliberate: gold = "identity/prestige" only.
6. **Elevation is border-only.** Every card is `1px var(--line)` on near-identical
   surfaces — the UI reads as a wireframe of boxes. A lightness-step elevation
   system (bg → surface → surface-raised) + fewer borders would add depth cheaply.
7. **Dark-only.** Fine for the audience, but tokens should be structured so a light
   theme is a token swap, not a rewrite (roadmap #8).

### 2.2 Typography

No scale — ad-hoc sizes (9.5, 10, 10.5, 11, 12, 12.5, 13, 13.5, 14…) chosen per
element. Condensed-italic-uppercase display is used for headers AND data values AND
buttons — at 15px and below, condensed italic uppercase is measurably harder to
scan. Fix: a modular scale (e.g. 12 / 14 / 16 / 20 / 26 / 34 with `clamp()`), body
floor of 14px, display font reserved for true headlines and hero numbers, sentence
case for labels, tabular-nums for all stat columns (mono is already close).

### 2.3 Layout, density & scale — *the live user complaint*

1460px letterbox + tiny type = "the app is too small and doesn't use the screen."
Direction: fluid shell to ~1800px; multi-column on ≥1400px (My Picks fight list
2-up; Fight Lab verdict beside breakdown; Friends compare side-by-side); density
that comes from *spacing*, not from shrinking text.

### 2.4 Information architecture & flows

- **Nav labels don't match the user's mental model.** "Analyze / Events / Intel"
  is analyst-speak. The friends-game reality is: *Play* (My Picks, Friends),
  *Explore* (Fight Lab, Fighters, Cards), *Standings* (leaderboards). My Picks —
  the heart of the product — is buried mid-list; **it should be the landing tab**
  for non-admins, not Fight Lab.
- **My Picks vs Future Cards is now blurry** (both show model odds since the
  enrichment). Sharpen: Future Cards = "what the engine thinks" (analysis depth),
  My Picks = "the game" (your state, friends, leaderboards). Cross-link instead of
  duplicating.
- **No onboarding.** A new friend lands on Fight Lab with an empty search box.
  First-run should land on My Picks with the next open card and a 3-step hint
  (pick → compare with friends → leaderboard).
- **Developer jargon in the topbar** ("API connected", "Sandbox DB", "Demo data")
  shows to every user, always. Healthy = show nothing; problems only.
- **Banner stacking:** offline + data-age + demo pills can pile into a wall.
  One status slot with priority.

### 2.5 Interaction & feedback

- `window.confirm()` for destructive flows and the temp-password reveal — replace
  with a proper modal (focus-trapped, styled, screen-reader labelled).
- Success feedback is inline text that persists ("Saved.") — use transient toasts.
- No skeletons: every tab switch flashes a spinner then pops. List skeletons for
  leaderboards/cards/friends.
- Cold-start blank screen while the Fly machine wakes (~seconds) looks broken —
  needs a "waking the server…" app-shell state.
- Good already (keep): per-row busy states, optimistic pick toggles, empty-state
  copy voice ("No friends yet — add someone by their username").

### 2.6 Mobile & touch (untested surface)

9 media queries across 13 views. Suspects: 4-col stat tile rows, Users admin table,
2-col pick grids, compare panels, small touch targets (chips ~24px tall; minimum
44px), the three.js login scene on low-end phones. Also no PWA manifest/icons
despite the roadmap goal. Every view needs a 375px and 768px pass.

### 2.7 Accessibility

- Semantics: views are div-soups — no `<main>/<nav>/<h1>` landmark structure per
  view; tab switches don't move focus or update `document.title`.
- Focus styles are browser-default at best; hand-rolled controls (switch, pick
  cards) have aria but no visible focus ring system.
- Emoji nav icons (⚔ ◎ ▸ ♛ …) render platform-dependently and are unlabeled —
  replace with an SVG icon set (`aria-hidden` + text).
- Color-only meaning (win/loss/confidence bands) — double-encode with icons/text.

---

## 3. Per-view priorities (quick hit list)

| View | Top issue | Fix in |
|---|---|---|
| My Picks | Should be home; long single column; 3 features crammed (queue/picks/boards) | W1/W5 |
| Fight Lab | Everything at once; verdict should lead, breakdown collapses | W5 |
| Future Cards | Tag/pill overload per row (6+); overlaps My Picks | W5 |
| Friends | Compare panel is long scroll; upcoming vs record needs tabs/sections | W5 |
| Leaderboards ×2 | Same row UI implemented 3× and drifting | W2 |
| Evaluation | Expert wall; fine now that it's admin-only, still needs Overview/Deep-Dive | W5 (low) |
| Login | three.js cost on mobile; no password-confirm on register | W3/W6 |
| Profile | Fine; add avatar cropping feedback + toast on save | W4 |

---

## 4. Software-engineering critique

1. **`App.jsx` is a god component**: shell + nav + routing + health/data fetching +
   context assembly. Split: `AppShell` (layout), `useHashRoute`, `AppDataProvider`.
2. **`AppContext` is a grab-bag** (imageLookup + weightClasses + fightLabPrefill +
   openProfile + profileFighter). Split domain contexts or adopt a tiny store.
3. **Fetch boilerplate duplicated ~10×** (`useEffect` + `active` flag + error
   state). Extract `useApi(fn, deps)` hook → kills a whole bug class; later a real
   cache (TanStack Query) if warranted. Today every tab revisit refetches.
4. **`MyPicks.jsx` ≈700 lines** doing three features. Decompose into
   PickQueue / CardPicker / CardLeaderboard components.
5. **No error boundaries** — one render throw = white screen for a friend. Add a
   per-view boundary with the EmptyState voice + "reload" action.
6. **`mock.js` (~900 lines) drifts from the real API by hand** — we fixed three
   shape mismatches this week (users, odds fields, getMe ids). Add a contract
   check (mock shapes vs FastAPI OpenAPI schema in CI) or generate mocks.
7. **CSS**: 4,537-line append-only file; naming collisions already bit us twice
   (`.profile-name`, `.pick-option-name`); two tone vocabularies
   (`tone-win/loss/warn/gold` vs `tone-red/green/blue/amber`); dead rules from this
   week's churn. Split per-component (CSS modules or `@layer` files), one tone
   system, stylelint in CI.
8. **Bundle**: single 860KB chunk; every view + three.js eagerly imported.
   `React.lazy` the admin views, charts, and OctagonScene; route-level splitting;
   kill the Vite size warning.
9. **No types**: plain JS with implicit shapes. Pragmatic path: JSDoc typedefs for
   API payloads + `checkJs` — TS migration optional later, don't block redesign.
10. **Testing zero**: Vitest + Testing Library for extracted components + pick
    flow + auth gate; one Playwright smoke (login → pick → leaderboard) against the
    mock server; wire into the existing GitHub Actions CI.
11. **Fighter images hotlink ufcstats.com** — no caching/fallback strategy if they
    block or change; consider proxying/caching through the backend later.
12. **Minor:** `pick-clear` class reused as a generic tertiary button (naming
    lies); `avatarUrl` cache-busting is per-view state; status pills computed in
    shell render.

---

## 5. Color/theme rework proposal (recommended: Direction A)

**Direction A — "Fight-night broadcast, matured"** (evolution, low risk):
keep the near-black arena mood; fix the semantics.

Draft token roles (values illustrative — tune in browser):

| Token | Role | Draft |
|---|---|---|
| `--bg / --surface / --raised` | 3-step elevation (replaces border-everywhere) | `#0a0d14 / #10141d / #171c28` |
| `--brand` | FIGHT IQ identity, hero moments only | keep red `#ff3355` **or** shift crimson `#e63950` |
| `--action` | buttons/links/focus (NEW — decoupled from brand) | electric blue `#4d8dff` or gold |
| `--positive` | wins/correct (colorblind-safe vs red) | teal `#2dd4bf` |
| `--negative` | losses/errors/destructive ONLY | red family |
| `--gold` | rating/prestige/"you" | keep `#f5c451` |
| `--text / --text-dim` | AA-checked at 14px (dim ≥ 4.5:1) | `#f2f4fb / #98a2be→lighter` |

Rules: red never means "primary action" again; win/loss = teal/red **plus** ✓/✗;
accents desaturate ~10% at small sizes; every token pair ships with a checked
contrast ratio in a comment. Light theme = second token block, later.

**Direction B — full rebrand** (new palette, e.g. warm "octagon canvas" darks with
gold-first identity): only if A feels insufficient after W1; costs a full re-shoot
of every state color and delays everything else. Not recommended first.

---

## 6. Workstreams (each independently shippable)

- **W0 — Tokens v2 + palette re-role (Direction A).** New token set, semantic
  renames, one tone vocabulary, contrast-checked. *Do first — everything else
  paints with these.* _Accept: no red primary buttons; win/loss double-encoded;
  all body text ≥4.5:1; tone-* unified._
- **W1 — Scale & density (the friend feedback).** Fluid shell → ~1800px, `clamp()`
  type scale (14px floor), multi-column ≥1400px, spacing-driven density.
  _Accept: 1440p screenshot uses ≥80% width; zero sub-12px body text._
- **W2 — Component extraction + CSS split + error boundaries + `useApi` hook.**
  Button/Tag/Switch/Modal(replaces window.confirm)/Toast/UserBadge/LeaderboardRow;
  per-component CSS; stylelint. _Accept: leaderboard row = ONE component in all 3
  places; a thrown view renders a boundary, not a white screen._
- **W3 — Mobile pass + PWA.** 375/768 audit of all views, tables→cards, 44px
  targets, manifest+icons, lazy three.js on login. _Accept: full pick + compare
  flow one-handed on a phone; installable._
- **W4 — A11y.** SVG icon set, focus-visible system, landmarks + per-tab
  `document.title` + focus management, axe-core clean on main flows.
- **W5 — IA & hierarchy.** Nav regrouped (Play/Explore/Standings), **My Picks as
  landing tab**, first-run hint, verdict-first Fight Lab, tag de-clutter, Future
  Cards/My Picks role sharpening, banner priority slot, hide healthy status pills.
- **W6 — Performance.** Route-level code splitting, skeletons, "waking server"
  state, kill the 860KB warning.
- **W7 — Deep URLs.** `#/fighters/<name>`, `#/picks/<event>`, compare links;
  scroll restoration.
- **W8 — Frontend tests + mock contract.** Vitest/RTL + Playwright smoke in CI;
  mock-vs-OpenAPI shape check.

**Order:** W0 → W1 (users feel it) → W2+W8 (foundation) → W3 → W4+W6 → W5 → W7.
W0+W1 together are the "wow, it looks better" release; ship them as one deploy.
