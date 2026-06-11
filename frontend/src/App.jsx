import { useCallback, useEffect, useMemo, useState } from "react";
import { AppContext } from "./AppContext.js";
import { USE_MOCK, checkHealth, getFighterImages, getWeightClasses } from "./api/client.js";
import { normalizeFighterName } from "./lib/format.js";
import FightLab from "./views/FightLab.jsx";
import FighterProfile from "./views/FighterProfile.jsx";
import FutureCards from "./views/FutureCards.jsx";
import RecentCards from "./views/RecentCards.jsx";
import Leaderboards from "./views/Leaderboards.jsx";
import Evaluation from "./views/Evaluation.jsx";
import UpdateData from "./views/UpdateData.jsx";

const FALLBACK_WEIGHT_CLASSES = [
  "Flyweight",
  "Bantamweight",
  "Featherweight",
  "Lightweight",
  "Welterweight",
  "Middleweight",
  "Light Heavyweight",
  "Heavyweight",
];

const NAV_GROUPS = [
  {
    label: "Analyze",
    items: [
      { value: "lab", label: "Fight Lab", icon: "⚔" },
      { value: "fighters", label: "Fighters", icon: "◎" },
    ],
  },
  {
    label: "Events",
    items: [
      { value: "future", label: "Future Cards", icon: "▸" },
      { value: "recent", label: "Recent Cards", icon: "↺" },
    ],
  },
  {
    label: "Intel",
    items: [
      { value: "leaderboards", label: "Leaderboards", icon: "♛" },
      { value: "evaluation", label: "Evaluation", icon: "◫" },
    ],
  },
  {
    label: "System",
    items: [{ value: "update", label: "Data Ops", icon: "⟳" }],
  },
];

const VIEWS = {
  lab: FightLab,
  fighters: FighterProfile,
  future: FutureCards,
  recent: RecentCards,
  leaderboards: Leaderboards,
  evaluation: Evaluation,
  update: UpdateData,
};

export default function App() {
  const [view, setView] = useState("lab");
  const [navOpen, setNavOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState(null);
  const [weightClasses, setWeightClasses] = useState(FALLBACK_WEIGHT_CLASSES);
  const [imageLookup, setImageLookup] = useState({});
  const [fightLabPrefill, setFightLabPrefill] = useState({ a: "", b: "" });
  const [profileFighter, setProfileFighter] = useState("");

  useEffect(() => {
    checkHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));

    getWeightClasses()
      .then((rows) => {
        if (rows.length) {
          setWeightClasses(rows);
        }
      })
      .catch(() => {});

    getFighterImages()
      .then((images) => {
        const lookup = {};

        for (const imageData of images) {
          const fighter = imageData.fighter || imageData.name;

          if (fighter) {
            lookup[normalizeFighterName(fighter)] = imageData;
          }
        }

        setImageLookup(lookup);
      })
      .catch(() => {});
  }, []);

  const openProfile = useCallback((fighterName) => {
    const cleaned = String(fighterName || "").trim();

    if (!cleaned) {
      return;
    }

    setProfileFighter(cleaned);
    setView("fighters");
    setNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const sendToFightLab = useCallback(({ a, b }) => {
    setFightLabPrefill((current) => ({
      a: a ?? current.a,
      b: b ?? current.b,
    }));
    setView("lab");
    setNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const contextValue = useMemo(
    () => ({
      imageLookup,
      weightClasses,
      openProfile,
      sendToFightLab,
      fightLabPrefill,
      profileFighter,
    }),
    [imageLookup, weightClasses, openProfile, sendToFightLab, fightLabPrefill, profileFighter]
  );

  const ActiveView = VIEWS[view] ?? FightLab;

  return (
    <AppContext.Provider value={contextValue}>
      <div className="app-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="nav-toggle"
              aria-label="Toggle navigation"
              onClick={() => setNavOpen((open) => !open)}
            >
              ☰
            </button>
            <img src="/fight-iq-mark.png" alt="" className="brand-mark" />
            <div className="brand-copy">
              <span className="brand-kicker">MMA analytics</span>
              <span className="brand-name">
                FIGHT <em>IQ</em>
              </span>
            </div>
          </div>

          <div className="topbar-right">
            {USE_MOCK && <span className="mode-pill mock">Demo data</span>}
            <span
              className={`mode-pill ${
                apiOnline === null ? "pending" : apiOnline ? "online" : "offline"
              }`}
            >
              <span className="status-dot" />
              {apiOnline === null
                ? "Checking API…"
                : apiOnline
                  ? "API connected"
                  : "API offline"}
            </span>
          </div>
        </header>

        <div className="shell-body">
          <nav className={`sidebar ${navOpen ? "open" : ""}`}>
            {NAV_GROUPS.map((group) => (
              <div className="nav-group" key={group.label}>
                <span className="nav-group-label">{group.label}</span>
                {group.items.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={`nav-item ${view === item.value ? "active" : ""}`}
                    onClick={() => {
                      setView(item.value);
                      setNavOpen(false);
                    }}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            ))}

            <div className="sidebar-footer">
              <p>
                Calibrated UFC fight predictions from scraped UFCStats data. Odds are
                comparison-only.
              </p>
            </div>
          </nav>

          {navOpen && (
            <button
              type="button"
              className="nav-scrim"
              aria-label="Close navigation"
              onClick={() => setNavOpen(false)}
            />
          )}

          <main className="main-content">
            {apiOnline === false && !USE_MOCK && (
              <div className="offline-banner">
                Backend unreachable at the configured API URL. Start it with{" "}
                <code>uvicorn app.main:app --reload</code> in <code>backend/</code>, or
                run the frontend with <code>npm run dev:mock</code> for demo data.
              </div>
            )}
            <ActiveView key={view} />
          </main>
        </div>
      </div>
    </AppContext.Provider>
  );
}
