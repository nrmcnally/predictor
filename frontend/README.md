# Fight IQ — Frontend

A dark, fight-night-themed React frontend for the UFC Fight Predictor backend. Built with Vite, plain CSS (custom design system, no UI framework), and a three.js animated octagon scene in the Fight Lab view.

## Stack

- React 19 + Vite
- three.js (wireframe octagon stage with red/blue corner lighting and particles)
- Custom CSS design system (`src/index.css`) — Barlow Condensed / Inter / JetBrains Mono
- No component library, no state library — React context + fetch

## Views

| View | What it does |
| --- | --- |
| Fight Lab | Pick a red/blue corner fighter, get calibrated win probability, method-of-ending probabilities, rule-based "why", and matchup edges |
| Fighters | Scouting profile: headline stats, style scores, Elo trend chart, rankings, method tendencies, fight history |
| Future Cards | Upcoming events with model picks, confidence tags, and no-vig market odds comparison |
| Recent Cards | Saved pre-fight predictions vs actual results, model vs market accuracy |
| Leaderboards | Best/worst fighters by category, overall or per weight class |
| Evaluation | Holdout metrics, calibration by confidence bucket, segment tables, model-vs-market and snapshot evaluation |
| Data Ops | Run the incremental update pipeline and inspect the latest report |

## Running

```bash
npm install

# against the real backend (http://127.0.0.1:8000)
npm run dev

# with built-in demo data — no backend, data, or models required
npm run dev:mock
```

The backend URL can be overridden with `VITE_API_BASE_URL`. Mock mode can also be forced with `VITE_USE_MOCK=1`.

`npm run build` produces a production bundle, `npm run lint` runs ESLint.

## Structure

```text
src/
├── api/
│   ├── client.js     # all backend endpoints, error normalization
│   └── mock.js       # deterministic demo data for every endpoint
├── components/       # shared UI: cards, tiles, tags, meters, avatars, search
├── lib/format.js     # formatting helpers
├── three/OctagonScene.jsx
├── views/            # one file per app view
├── App.jsx           # shell: topbar, sidebar nav, app context
└── index.css         # design tokens + all styling
```
