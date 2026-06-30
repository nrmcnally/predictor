import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider.jsx";
import {
  changePassword,
  getMyStats,
  setVisibility,
  updateProfile,
} from "../api/client.js";
import { ErrorNote, SectionCard, StatTile, Tag } from "../components/ui.jsx";

function pct(value) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function signedPct(value) {
  if (value === null || value === undefined) return "—";
  const points = Math.round(value * 100);
  return `${points > 0 ? "+" : ""}${points}%`;
}

function initials(value) {
  const base = String(value || "").split("@")[0];
  const parts = base.replace(/[._-]+/g, " ").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export default function Profile() {
  const { user, logout, refreshUser } = useAuth();

  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [email, setEmail] = useState(user.email || "");
  const [accountMsg, setAccountMsg] = useState("");
  const [accountErr, setAccountErr] = useState("");
  const [accountBusy, setAccountBusy] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const [isPublic, setIsPublic] = useState(!!user.is_public);
  const [visBusy, setVisBusy] = useState(false);

  const [stats, setStats] = useState(null);

  useEffect(() => {
    let active = true;
    getMyStats()
      .then((data) => active && setStats(data))
      .catch(() => {
        /* stats are non-critical; leave tiles at — on failure */
      });
    return () => {
      active = false;
    };
  }, []);

  const saveAccount = async (event) => {
    event.preventDefault();
    setAccountErr("");
    setAccountMsg("");
    setAccountBusy(true);
    try {
      await updateProfile(email.trim(), displayName.trim());
      await refreshUser();
      setAccountMsg("Saved.");
    } catch (err) {
      setAccountErr(err.message);
    } finally {
      setAccountBusy(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    setPwErr("");
    setPwMsg("");
    setPwBusy(true);
    try {
      await changePassword(currentPw, newPw);
      setPwMsg("Password updated.");
      setCurrentPw("");
      setNewPw("");
    } catch (err) {
      setPwErr(err.message);
    } finally {
      setPwBusy(false);
    }
  };

  const toggleVisibility = async () => {
    const next = !isPublic;
    setVisBusy(true);
    try {
      await setVisibility(next);
      setIsPublic(next);
      await refreshUser();
    } catch {
      /* leave the toggle as-is on failure */
    } finally {
      setVisBusy(false);
    }
  };

  return (
    <div className="view">
      <header>
        <p className="eyebrow">Your corner</p>
        <h1 className="view-title">Profile</h1>
      </header>

      <div className="profile-identity">
        <div className="profile-avatar">{initials(user.display_name || user.email)}</div>
        <div className="profile-identity-body">
          <div className="profile-name">{user.display_name || user.email}</div>
          <div className="profile-email">{user.email}</div>
          <div className="profile-meta">
            <Tag tone={user.role === "admin" ? "gold" : "neutral"}>{user.role}</Tag>
            <span className="muted">
              Member since {String(user.created_at || "").slice(0, 10) || "—"}
            </span>
          </div>
        </div>
      </div>

      <SectionCard
        eyebrow="Tale of the tape"
        title="Your record"
        description={
          stats && stats.graded > 0
            ? `${stats.graded} graded pick${stats.graded === 1 ? "" : "s"}${
                stats.pending ? ` · ${stats.pending} awaiting results` : ""
              }.`
            : "Your record builds as your picks get graded. Head to My Picks and call some fights."
        }
      >
        <div className="tile-row four">
          <StatTile
            label="FIGHT IQ"
            value={stats ? stats.rating : "—"}
            hint="rating"
            tone="gold"
          />
          <StatTile
            label="Record"
            value={stats && stats.graded > 0 ? `${stats.record.wins}–${stats.record.losses}` : "—"}
            hint="W–L"
          />
          <StatTile
            label="Accuracy"
            value={pct(stats?.accuracy)}
            hint="win rate"
            tone="win"
          />
          <StatTile
            label="Streak"
            value={stats?.streak ? `${stats.streak.type}${stats.streak.count}` : "—"}
            hint="current"
          />
        </div>
        {stats && (stats.vs_model || stats.method?.picks > 0) && (
          <p className="muted profile-stat-note">
            {stats.vs_model && (
              <>vs the engine {signedPct(stats.vs_model.delta)} on {stats.vs_model.overlap} shared
              pick{stats.vs_model.overlap === 1 ? "" : "s"}</>
            )}
            {stats.vs_model && stats.method?.picks > 0 && " · "}
            {stats.method?.picks > 0 && (
              <>method called on {stats.method.picks} ({pct(stats.method.accuracy)} correct)</>
            )}
          </p>
        )}
      </SectionCard>

      <SectionCard eyebrow="Account" title="Email & display name">
        <ErrorNote message={accountErr} />
        {accountMsg && <p className="form-ok">{accountMsg}</p>}
        <form className="profile-form" onSubmit={saveAccount}>
          <label className="profile-field">
            <span>Display name</span>
            <input value={displayName} maxLength={60} onChange={(e) => setDisplayName(e.target.value)} />
          </label>
          <label className="profile-field">
            <span>Email</span>
            <input type="email" value={email} required onChange={(e) => setEmail(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={accountBusy}>
            {accountBusy ? "Saving…" : "Save"}
          </button>
        </form>
      </SectionCard>

      <SectionCard eyebrow="Security" title="Change password">
        <ErrorNote message={pwErr} />
        {pwMsg && <p className="form-ok">{pwMsg}</p>}
        <form className="profile-form" onSubmit={savePassword}>
          <label className="profile-field">
            <span>Current password</span>
            <input
              type="password"
              value={currentPw}
              required
              autoComplete="current-password"
              onChange={(e) => setCurrentPw(e.target.value)}
            />
          </label>
          <label className="profile-field">
            <span>New password</span>
            <input
              type="password"
              value={newPw}
              required
              minLength={8}
              autoComplete="new-password"
              onChange={(e) => setNewPw(e.target.value)}
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={pwBusy}>
            {pwBusy ? "Updating…" : "Update password"}
          </button>
        </form>
      </SectionCard>

      <SectionCard eyebrow="Privacy" title="Public profile">
        <div className="profile-toggle-row">
          <div>
            <div className="profile-toggle-label">{isPublic ? "Public" : "Private"}</div>
            <div className="muted">
              {isPublic
                ? "You can appear on leaderboards and be compared by friends."
                : "Hidden from leaderboards and comparisons (opt-in any time)."}
            </div>
          </div>
          <button
            type="button"
            className={`switch ${isPublic ? "on" : ""}`}
            onClick={toggleVisibility}
            disabled={visBusy}
            role="switch"
            aria-checked={isPublic}
            aria-label="Toggle public profile"
          >
            <span className="switch-knob" />
          </button>
        </div>
      </SectionCard>

      <div className="profile-logout">
        <button type="button" className="btn btn-ghost" onClick={logout}>
          Log out
        </button>
      </div>
    </div>
  );
}
