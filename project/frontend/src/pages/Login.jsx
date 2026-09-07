import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const DEMO_ACCOUNTS = [
  { username: "ministry", password: "ministry123", label: "Ministry", detail: "National oversight — all India", home: "/ministry" },
  { username: "state_up", password: "state123", label: "State Nodal Authority", detail: "Uttar Pradesh", home: "/state" },
  { username: "mp_priya_saroj", password: "mp123", label: "Member of Parliament", detail: "Priya Saroj", home: "/mp" },
  { username: "district_jaunpur", password: "district123", label: "District Authority", detail: "Jaunpur", home: "/district" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e, home) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const data = await login(username, password);
      const target = home || DEMO_ACCOUNTS.find((a) => a.username === username)?.home || "/works";
      navigate(target);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function fillAndSubmit(account) {
    setUsername(account.username);
    setPassword(account.password);
    setError(null);
    setSubmitting(true);
    login(account.username, account.password)
      .then(() => navigate(account.home))
      .catch((err) => setError(err.message))
      .finally(() => setSubmitting(false));
  }

  return (
    <div className="min-h-screen bg-ink flex items-center justify-center px-4">
      <div className="w-full max-w-4xl grid md:grid-cols-2 gap-0 border border-white/10">
        <div className="bg-ink text-white p-10 flex flex-col justify-between">
          <div>
            <div className="font-display text-2xl leading-tight">MPLADS Monitor</div>
            <div className="text-sm text-white/60 mt-1">AI-Powered Fund Utilization &amp; Anomaly Oversight</div>
          </div>
          <div className="text-xs text-white/40 leading-relaxed mt-12">
            Smart India Hackathon · Ministry of Statistics &amp; Programme Implementation
            <br />
            Trained on 49,000 sanctioned works across every state and union territory.
          </div>
        </div>

        <div className="bg-surface p-10">
          <h1 className="font-display text-xl text-ink mb-1">Sign in</h1>
          <p className="text-sm text-muted mb-6">Choose a demo account, or sign in manually below.</p>

          <div className="grid grid-cols-2 gap-2 mb-6">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.username}
                onClick={() => fillAndSubmit(a)}
                disabled={submitting}
                className="text-left border border-line px-3 py-2.5 hover:border-accent hover:bg-accent-light/40 transition-colors disabled:opacity-50"
              >
                <div className="text-sm font-medium text-ink">{a.label}</div>
                <div className="text-xs text-muted">{a.detail}</div>
              </button>
            ))}
          </div>

          <div className="text-xs text-muted mb-4 flex items-center gap-2">
            <span className="flex-1 h-px bg-line" /> or sign in manually <span className="flex-1 h-px bg-line" />
          </div>

          <form onSubmit={(e) => handleSubmit(e)} className="space-y-3">
            <div>
              <label className="block text-xs text-muted mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-line px-3 py-2 text-sm focus:border-accent outline-none"
                placeholder="e.g. ministry"
              />
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-line px-3 py-2 text-sm focus:border-accent outline-none"
              />
            </div>
            {error && <div className="text-xs text-risk-high">{error}</div>}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-accent text-white text-sm font-medium py-2.5 hover:bg-accent-dark transition-colors disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
