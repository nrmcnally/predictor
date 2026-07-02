import { lazy, Suspense, useState } from "react";
import { USE_MOCK } from "../api/client.js";
import { useAuth } from "../auth/authContext.js";
import { useSlowHint } from "../hooks/useSlowHint.js";

// three.js is ~half the bundle and pure decoration here — load it lazily and
// skip it entirely on phones (W3: mobile perf + W6 code splitting head start).
const OctagonScene = lazy(() => import("../three/OctagonScene.jsx"));
const SHOW_SCENE =
  typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const waking = useSlowHint(busy);

  const registering = mode === "register";

  const switchMode = () => {
    setMode(registering ? "login" : "register");
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (registering) {
        await register(email.trim(), password, username.trim());
      } else {
        await login(email.trim(), password);
      }
      // On success the auth gate swaps this screen for the app.
    } catch (err) {
      setError(err?.message || "Something went wrong.");
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-bg" aria-hidden="true">
        {SHOW_SCENE && (
          <Suspense fallback={null}>
            <OctagonScene className="login-scene" />
          </Suspense>
        )}
        <div className="login-spot" />
      </div>

      <div className="login-brand">
        <img src="/fight-iq-mark.png" alt="" className="brand-mark" />
        <div className="brand-copy">
          <span className="brand-kicker">MMA analytics</span>
          <span className="brand-name">
            FIGHT <em>IQ</em>
          </span>
        </div>
      </div>

      <form className="login-card" onSubmit={submit}>
        <div className="login-card-head">
          <span className="login-eyebrow">▸ Tale of the Tape</span>
          <h1 className="login-title">{registering ? "Join the Card" : "Fighter Access"}</h1>
          <p className="login-sub">
            {registering
              ? "Pick a username — it's how friends find you on the leaderboard."
              : "Sign in to the predictor."}
          </p>
        </div>

        {registering && (
          <label className="login-field">
            <span>Username</span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="KO_Karen"
              maxLength={60}
              autoCapitalize="off"
              autoCorrect="off"
              autoFocus
              required
            />
          </label>
        )}

        <label className="login-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="username"
            autoFocus={!registering}
            required
          />
        </label>

        <label className="login-field">
          <span>Passcode</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={registering ? "8+ characters" : "••••••••"}
            autoComplete={registering ? "new-password" : "current-password"}
            minLength={registering ? 8 : undefined}
            required
          />
        </label>

        {error && <p className="login-error" role="alert">{error}</p>}

        <button type="submit" className="login-enter" disabled={busy}>
          {busy ? "…" : registering ? "Create account ▸" : "Enter ▸"}
        </button>
        {waking && (
          <p className="login-demo">Waking the server — this first request can take a few seconds…</p>
        )}

        <button type="button" className="login-switch" onClick={switchMode}>
          {registering ? "Have an account? Sign in" : "New here? Create an account"}
        </button>

        {USE_MOCK && (
          <p className="login-demo">
            Demo · <code>demo@fightiq.local / demo12345</code>
          </p>
        )}
      </form>
    </div>
  );
}
