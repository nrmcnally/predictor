import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppContext } from "./AppContext.js";
import {
  USE_MOCK,
  checkHealth,
  getDataQualitySummary,
  getFighterImages,
  getWeightClasses,
} from "./api/client.js";
import { normalizeFighterName } from "./lib/format.js";
import { parseRoute, routeHash } from "./lib/routing.js";
// Eager: the two screens on the critical path — the auth gate and the landing tab.
import Login from "./views/Login.jsx";
import MyPicks from "./views/MyPicks.jsx";
// Route-level code splitting (W6): every other tab is its own chunk, fetched on
// first visit. Shared components stay in the main bundle via MyPicks.
const FightLab = lazy(() => import("./views/FightLab.jsx"));
const FighterProfile = lazy(() => import("./views/FighterProfile.jsx"));
const FutureCards = lazy(() => import("./views/FutureCards.jsx"));
const RecentCards = lazy(() => import("./views/RecentCards.jsx"));
const Leaderboards = lazy(() => import("./views/Leaderboards.jsx"));
const UserLeaderboard = lazy(() => import("./views/UserLeaderboard.jsx"));
const Evaluation = lazy(() => import("./views/Evaluation.jsx"));
const UpdateData = lazy(() => import("./views/UpdateData.jsx"));
const UsersAdmin = lazy(() => import("./views/UsersAdmin.jsx"));
const Profile = lazy(() => import("./views/Profile.jsx"));
const Friends = lazy(() => import("./views/Friends.jsx"));
import { AuthProvider } from "./auth/AuthProvider.jsx";
import { useAuth } from "./auth/authContext.js";
import { UserAvatar } from "./components/UserAvatar.jsx";
import { ErrorBoundary } from "./components/ErrorBoundary.jsx";
import { SkeletonRows } from "./components/Skeleton.jsx";
import { useSlowHint } from "./hooks/useSlowHint.js";
import { useTheme } from "./hooks/useTheme.js";
import {
  IconActivity,
  IconCalendar,
  IconCrown,
  IconDatabase,
  IconFighter,
  IconFriends,
  IconHistory,
  IconLab,
  IconLogout,
  IconMenu,
  IconMoon,
  IconPicks,
  IconPodium,
  IconShield,
  IconSun,
} from "./components/icons.jsx";

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

// Grouped by what users DO, not by analyst taxonomy (W5): the game first.
const NAV_GROUPS = [
  {
    label: "Play",
    items: [
      { value: "picks", label: "My picks", icon: IconPicks },
      { value: "friends", label: "Friends", icon: IconFriends },
    ],
  },
  {
    label: "Explore",
    items: [
      { value: "lab", label: "Fight lab", icon: IconLab },
      { value: "fighters", label: "Fighters", icon: IconFighter },
      { value: "future", label: "Future cards", icon: IconCalendar },
      { value: "recent", label: "Recent cards", icon: IconHistory },
    ],
  },
  {
    label: "Standings",
    items: [
      { value: "user-leaderboard", label: "User leaderboard", icon: IconPodium },
      { value: "leaderboards", label: "Fighter rankings", icon: IconCrown },
    ],
  },
];

// Admin-only nav — appended for admins, hidden from regular users. Evaluation lives
// here too: those endpoints retrain/score models and are too heavy for everyone.
const ADMIN_NAV_GROUP = {
  label: "Admin",
  items: [
    { value: "evaluation", label: "Evaluation", icon: IconActivity },
    { value: "users", label: "User admin", icon: IconShield },
    { value: "update", label: "Data ops", icon: IconDatabase },
  ],
};

const ADMIN_VIEWS = new Set(["users", "update", "evaluation"]);

// Per-tab document titles (W4) — so history entries, bookmarks, and screen
// readers say where you are instead of ten identical "FIGHT IQ" tabs.
const VIEW_TITLES = Object.fromEntries(
  [...NAV_GROUPS, ADMIN_NAV_GROUP]
    .flatMap((group) => group.items)
    .map((item) => [item.value, item.label])
);
VIEW_TITLES.profile = "Profile";

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
// W7: an optional second segment deep-links into a view — #/fighters/<name>,
// #/picks/<event_id>, #/friends/<username>.
const VIEW_NAMES = new Set(Object.keys(VIEWS));

function routeFromHash() {
  // The game is the landing tab (W5) — Fight Lab is a destination, not home.
  return parseRoute(window.location.hash, VIEW_NAMES, "picks");
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
  const waking = useSlowHint(loading);

  if (loading) {
    return (
      <div className="login-screen">
        <div className="login-boot">
          {waking
            ? "Waking the server — first visit after a quiet spell takes a few seconds…"
            : "Loading FIGHT IQ…"}
        </div>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <AppShell />;
}

// "2026-06-27" -> "Jun 27, 2026" for the freshness banner.
function formatEventDate(isoDate) {
  const parsed = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return isoDate;
  }
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Coarse "refreshed 3 hours ago" for the freshness banner.
function relativeTime(isoDateTime) {
  const then = new Date(isoDateTime);
  if (Number.isNaN(then.getTime())) {
    return null;
  }
  const minutes = Math.round((Date.now() - then.getTime()) / 60000);
  if (minutes < 2) return "just now";
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function AppShell() {
  const [route, setRoute] = useState(routeFromHash);
  const [navOpen, setNavOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const view = route.view;
  const mainRef = useRef(null);
  const mountedRef = useRef(false);
  const routeRef = useRef(route);
  // Per-tab scroll positions (W7). Only Back/Forward restores them — a fresh
  // in-app navigation clears the target's slot so it lands at the top.
  const scrollMemoryRef = useRef({});

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  // Navigating sets the hash (which pushes a history entry); the hashchange
  // listener is the single place state updates, so Back/Forward work the same
  // as in-app clicks.
  const setView = useCallback((next, param = "") => {
    delete scrollMemoryRef.current[next];
    const target = routeHash(next, param);
    if (window.location.hash === target) {
      setRoute(routeFromHash());
      return;
    }
    window.location.hash = target.slice(1);
  }, []);

  // Deep-linkable state inside a view (selected card, opened compare) mirrors
  // into the URL without pushing history — Back should leave the tab, not
  // unwind every card click.
  const reflectRoute = useCallback((viewName, param = "") => {
    const target = routeHash(viewName, param);
    if (window.location.hash !== target) {
      window.history.replaceState(null, "", target);
    }
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      scrollMemoryRef.current[routeRef.current.view] = window.scrollY;
      setRoute(routeFromHash());
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // W4: title tracks the tab; focus moves to the new view so keyboard/screen-
  // reader users don't have to walk back through the whole sidebar. Skipped on
  // mount — stealing focus from the page on load is worse than not managing it.
  // W7: scroll returns to where you left the tab (Back/Forward) or the top.
  useEffect(() => {
    document.title = VIEW_TITLES[view]
      ? `${VIEW_TITLES[view]} · FIGHT IQ`
      : "FIGHT IQ";
    if (mountedRef.current) {
      mainRef.current?.focus({ preventScroll: true });
      const saved = scrollMemoryRef.current[view] ?? 0;
      requestAnimationFrame(() => window.scrollTo(0, saved));
    }
    mountedRef.current = true;
  }, [view]);
  const [apiOnline, setApiOnline] = useState(null);
  const [apiMode, setApiMode] = useState(null);
  const [weightClasses, setWeightClasses] = useState(FALLBACK_WEIGHT_CLASSES);
  const [imageLookup, setImageLookup] = useState({});
  const [fightLabPrefill, setFightLabPrefill] = useState({ a: "", b: "" });
  const [profileFighter, setProfileFighter] = useState("");
  const [dataFreshness, setDataFreshness] = useState(null);
  const { user, logout } = useAuth();

  // #/fighters/<name> drives which profile loads; the state survives leaving
  // the tab so revisiting Fighters shows the last-opened fighter.
  useEffect(() => {
    if (route.view === "fighters" && route.param) {
      // URL-sync effect: the hash is the external source of truth here.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setProfileFighter(route.param);
    }
  }, [route]);

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

    setView("fighters", cleaned);
    setNavOpen(false);
  }, [setView]);

  const sendToFightLab = useCallback(({ a, b }) => {
    setFightLabPrefill((current) => ({
      a: a ?? current.a,
      b: b ?? current.b,
    }));
    setView("lab");
    setNavOpen(false);
  }, [setView]);

  const contextValue = useMemo(
    () => ({
      imageLookup,
      weightClasses,
      openProfile,
      sendToFightLab,
      fightLabPrefill,
      profileFighter,
      routeParam: route.param,
      reflectRoute,
    }),
    [imageLookup, weightClasses, openProfile, sendToFightLab, fightLabPrefill, profileFighter, route.param, reflectRoute]
  );

  const isAdmin = user?.role === "admin";
  const navGroups = isAdmin ? [...NAV_GROUPS, ADMIN_NAV_GROUP] : NAV_GROUPS;
  const ActiveView =
    ADMIN_VIEWS.has(view) && !isAdmin ? FightLab : VIEWS[view] ?? FightLab;

  return (
    <AppContext.Provider value={contextValue}>
      <div className="app-shell">
        {/* preventDefault: a real #main-content hash would bounce viewFromHash
            back to the picks tab — focus the landmark directly instead. */}
        <a
          className="skip-link"
          href="#main-content"
          onClick={(event) => {
            event.preventDefault();
            mainRef.current?.focus();
          }}
        >
          Skip to content
        </a>
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="nav-toggle"
              aria-label="Toggle navigation"
              aria-expanded={navOpen}
              aria-controls="primary-nav"
              onClick={() => setNavOpen((open) => !open)}
            >
              <IconMenu size={20} />
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
            {/* Healthy = quiet (W5): pills only for states that need attention. */}
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            >
              {theme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />}
            </button>
            {USE_MOCK && <span className="mode-pill mock">Demo data</span>}
            {apiMode === "demo" && <span className="mode-pill mock">Sandbox DB</span>}
            {apiOnline === false && (
              <span className="mode-pill offline">
                <span className="status-dot" />
                API offline
              </span>
            )}
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
                  <IconLogout size={15} />
                </button>
              </div>
            )}
          </div>
        </header>

        <div className="shell-body">
          <nav
            id="primary-nav"
            className={`sidebar ${navOpen ? "open" : ""}`}
            aria-label="Primary"
          >
            {navGroups.map((group) => (
              <div className="nav-group" key={group.label}>
                <span className="nav-group-label">{group.label}</span>
                {group.items.map((item) => {
                  const ItemIcon = item.icon;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      className={`nav-item ${view === item.value ? "active" : ""}`}
                      aria-current={view === item.value ? "page" : undefined}
                      onClick={() => {
                        setView(item.value);
                        setNavOpen(false);
                      }}
                    >
                      <span className="nav-icon">
                        <ItemIcon />
                      </span>
                      {item.label}
                    </button>
                  );
                })}
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

          <main className="main-content" id="main-content" ref={mainRef} tabIndex={-1}>
            {apiOnline === false && !USE_MOCK && (
              <div className="offline-banner">
                Backend unreachable at the configured API URL. Start it with{" "}
                <code>uvicorn app.main:app --reload</code> in <code>backend/</code>, or
                run the frontend with <code>npm run dev:mock</code> for demo data.
              </div>
            )}
            {/* Two different facts: "results through" = the last completed event
                (doesn't move between fight nights); "refreshed" = when the update
                pipeline last actually ran — the signal that data is being kept
                current. The old banner only showed the first, which made a fresh
                update look like nothing happened. */}
            {dataFreshness?.latest_event_date && (
              <div
                className={`data-age-banner ${
                  dataFreshness.days_since_latest_event > 30 ? "stale" : ""
                }`}
              >
                {dataFreshness.days_since_latest_event > 30 ? "⚠ " : ""}
                Results through {formatEventDate(dataFreshness.latest_event_date)}
                {dataFreshness.last_refreshed_at &&
                relativeTime(dataFreshness.last_refreshed_at)
                  ? ` · data refreshed ${relativeTime(dataFreshness.last_refreshed_at)}`
                  : Number.isFinite(dataFreshness.days_since_latest_event)
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
              <Suspense fallback={<SkeletonRows rows={4} height={92} />}>
                <ActiveView />
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </AppContext.Provider>
  );
}
