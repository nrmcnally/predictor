import { useCallback, useEffect, useMemo, useState } from "react";
import { AppContext } from "./AppContext.js";
import {
  USE_MOCK,
  checkHealth,
  getDataQualitySummary,
  getFighterImages,
  getWeightClasses,
} from "./api/client.js";
import { normalizeFighterName } from "./lib/format.js";
import FightLab from "./views/FightLab.jsx";
import FighterProfile from "./views/FighterProfile.jsx";
import FutureCards from "./views/FutureCards.jsx";
import RecentCards from "./views/RecentCards.jsx";
import Leaderboards from "./views/Leaderboards.jsx";
import UserLeaderboard from "./views/UserLeaderboard.jsx";
import Evaluation from "./views/Evaluation.jsx";
import UpdateData from "./views/UpdateData.jsx";
import UsersAdmin from "./views/UsersAdmin.jsx";
import Login from "./views/Login.jsx";
import Profile from "./views/Profile.jsx";
import MyPicks from "./views/MyPicks.jsx";
import Friends from "./views/Friends.jsx";
import { AuthProvider } from "./auth/AuthProvider.jsx";
import { useAuth } from "./auth/authContext.js";
import { UserAvatar } from "./components/UserAvatar.jsx";
import { ErrorBoundary } from "./components/ErrorBoundary.jsx";

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
      { value: "picks", label: "My Picks", icon: "✓" },
      { value: "future", label: "Future Cards", icon: "▸" },
      { value: "recent", label: "Recent Cards", icon: "↺" },
    ],
  },
  {
    label: "Intel",
    items: [
      { value: "leaderboards", label: "Leaderboards", icon: "♛" },
      { value: "user-leaderboard", label: "User Leaderboard", icon: "◉" },
      { value: "friends", label: "Friends", icon: "◈" },
    ],
  },
];

// Admin-only nav — appended for admins, hidden from regular users. Evaluation lives
// here too: those endpoints retrain/score models and are too heavy for everyone.
const ADMIN_NAV_GROUP = {
  label: "Admin",
  items: [
    { value: "evaluation", label: "Evaluation", icon: "◫" },
    { value: "users", label: "User Admin", icon: "⚇" },
    { value: "update", label: "Data Ops", icon: "⟳" },
  ],
};

const ADMIN_VIEWS = new Set(["users", "update", "evaluation"]);

const VIEWS = {
  lab: FightLab,
  fighters: FighterProfile,
  picks: MyPicks,
  future: FutureCards,
  recent: RecentCards,
  leaderboards: Leaderboards,
  "user-leaderboard": UserLeaderboard,
  friends: Friends,
  evaluation: Evaluation,
  update: UpdateData,
  users: UsersAdmin,
  profile: Profile,
};

// The active tab lives in the URL hash (e.g. #/picks), so the browser's
// Back/Forward buttons move between tabs, refresh keeps your place, and tab
// links are shareable. Hash-based on purpose: the fragment never reaches the
// server, so deep links need no SPA-fallback or auth-wall changes.
function viewFromHash() {
  const name = window.location.hash.replace(/^#\/?/, "");
  return VIEWS[name] ? name : "lab";
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}

function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-screen">
        <div className="login-boot">Loading FIGHT IQ…</div>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <AppShell />;
}

function AppShell() {
  const [view, setViewState] = useState(viewFromHash);
  const [navOpen, setNavOpen] = useState(false);

  // Navigating sets the hash (which pushes a history entry); the hashchange
  // listener is the single place state updates, so Back/Forward work the same
  // as in-app clicks.
  const setView = useCallback((next) => {
    if (next === viewFromHash()) {
      setViewState(next);
      return;
    }
    window.location.hash = `/${next}`;
  }, []);

  useEffect(() => {
    const onHashChange = () => setViewState(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  const [apiOnline, setApiOnline] = useState(null);
  const [apiMode, setApiMode] = useState(null);
  const [weightClasses, setWeightClasses] = useState(FALLBACK_WEIGHT_CLASSES);
  const [imageLookup, setImageLookup] = useState({});
  const [fightLabPrefill, setFightLabPrefill] = useState({ a: "", b: "" });
  const [profileFighter, setProfileFighter] = useState("");
  const [dataFreshness, setDataFreshness] = useState(null);
  const { user, logout } = useAuth();

  useEffect(() => {
    checkHealth()
      .then((data) => {
        setApiOnline(true);
        setApiMode(data?.mode ?? null);
      })
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

    getDataQualitySummary()
      .then((summary) => setDataFreshness(summary?.data_freshness ?? null))
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
  }, [setView]);

  const sendToFightLab = useCallback(({ a, b }) => {
    setFightLabPrefill((current) => ({
      a: a ?? current.a,
      b: b ?? current.b,
    }));
    setView("lab");
    setNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [setView]);

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

  const isAdmin = user?.role === "admin";
  const navGroups = isAdmin ? [...NAV_GROUPS, ADMIN_NAV_GROUP] : NAV_GROUPS;
  const ActiveView =
    ADMIN_VIEWS.has(view) && !isAdmin ? FightLab : VIEWS[view] ?? FightLab;

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
            {apiMode === "demo" && <span className="mode-pill mock">Sandbox DB</span>}
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
            {user && (
              <div className="user-chip">
                <button
                  type="button"
                  className={`user-name ${view === "profile" ? "active" : ""}`}
                  onClick={() => {
                    setView("profile");
                    setNavOpen(false);
                  }}
                  title="Your profile"
                >
                  <UserAvatar userId={user.id} size={22} className="chip-avatar" />
                  {user.display_name || user.email}
                </button>
                {user.role === "admin" && <span className="user-role">admin</span>}
                <button
                  type="button"
                  className="user-logout"
                  onClick={logout}
                  title="Log out"
                  aria-label="Log out"
                >
                  ⎋
                </button>
              </div>
            )}
          </div>
        </header>

        <div className="shell-body">
          <nav className={`sidebar ${navOpen ? "open" : ""}`}>
            {navGroups.map((group) => (
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
            {dataFreshness?.latest_event_date && (
              <div
                className={`data-age-banner ${
                  dataFreshness.days_since_latest_event > 30 ? "stale" : ""
                }`}
              >
                {dataFreshness.days_since_latest_event > 30 ? "⚠ " : ""}
                Data current through {dataFreshness.latest_event_date}
                {Number.isFinite(dataFreshness.days_since_latest_event)
                  ? ` · ${dataFreshness.days_since_latest_event} day${
                      dataFreshness.days_since_latest_event === 1 ? "" : "s"
                    } ago`
                  : ""}
                {dataFreshness.days_since_latest_event > 30
                  ? " — open Data Ops to refresh."
                  : ""}
              </div>
            )}
            {/* keyed so switching tabs resets a crashed view's boundary */}
            <ErrorBoundary key={view}>
              <ActiveView />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </AppContext.Provider>
  );
}
