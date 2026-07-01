import { useState } from "react";
import { useAuth } from "../auth/authContext.js";
import OctagonScene from "../three/OctagonScene.jsx";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      // On success the auth gate swaps this screen for the app.
    } catch (err) {
      setError(err?.message || "Something went wrong.");
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-bg" aria-hidden="true">
        <OctagonScene className="login-scene" />
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
          <h1 className="login-title">Fighter Access</h1>
          <p className="login-sub">Sign in to the predictor. Accounts are invite-only.</p>
        </div>

        <label className="login-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="username"
            autoFocus
            required
          />
        </label>

        <label className="login-field">
          <span>Passcode</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
        </label>

        {error && <p className="login-error" role="alert">{error}</p>}

        <button type="submit" className="login-enter" disabled={busy}>
          {busy ? "…" : "Enter ▸"}
        </button>

        <p className="login-demo">
          Demo · <code>demo@fightiq.local / demo12345</code>
        </p>
      </form>
    </div>
  );
}
