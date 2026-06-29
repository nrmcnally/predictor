import { useState } from "react";
import { useAuth } from "../auth/AuthProvider.jsx";

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      // On success the auth gate swaps this screen for the app.
    } catch (err) {
      setError(err?.message || "Something went wrong.");
      setBusy(false);
    }
  };

  const toggleMode = () => {
    setMode((current) => (current === "login" ? "register" : "login"));
    setError("");
  };

  return (
    <div className="login-screen">
      <div className="login-bg" aria-hidden="true">
        <div className="login-octagon login-octagon-outer" />
        <div className="login-octagon login-octagon-inner" />
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
          <h1 className="login-title">
            {mode === "login" ? "Fighter Access" : "New Challenger"}
          </h1>
          <p className="login-sub">
            {mode === "login"
              ? "Step in to the predictor."
              : "Create your corner and step in."}
          </p>
        </div>

        <label className="login-field">
          <span>Fighter</span>
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="username"
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
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />
        </label>

        {error && <p className="login-error" role="alert">{error}</p>}

        <button type="submit" className="login-enter" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Enter ▸" : "Create & Enter ▸"}
        </button>

        <p className="login-toggle">
          {mode === "login" ? "New challenger? " : "Already have a corner? "}
          <button type="button" onClick={toggleMode}>
            {mode === "login" ? "Create account" : "Sign in"}
          </button>
        </p>

        <p className="login-demo">
          Demo · <code>demo / demo12345</code>
        </p>
      </form>
    </div>
  );
}
