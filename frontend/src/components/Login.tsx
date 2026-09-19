// Ekran logowania administratora.

import { useState, type FormEvent } from "react";
import { api } from "../api";

export function Login({ onLoggedIn }: { onLoggedIn: (username: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(username.trim(), password);
      onLoggedIn(result.username);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Logowanie nie powiodło się.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="brand large">
          <span className="brand-mark">N</span>
          <span className="brand-name">Danaco Nexus</span>
        </div>
        <p className="login-subtitle">Prywatny asystent AI do pracy z dokumentami, obrazami i plikami</p>
        <label>
          Login
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
        </label>
        <label>
          Hasło
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            autoFocus
            required
          />
        </label>
        {error && <div className="login-error">{error}</div>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Logowanie…" : "Zaloguj się"}
        </button>
      </form>
    </div>
  );
}
