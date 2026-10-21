import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  onDone: (workspace: string) => void;
};

export function FirstRunWizard({ onDone }: Props) {
  const [path, setPath] = useState("");
  const [ram, setRam] = useState<number | null>(null);
  const [rec, setRec] = useState<{ tier: string; model: string; provider: string } | null>(null);
  const [theme, setTheme] = useState("dark");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<{ name: string; provider: string; available: boolean }[]>([]);
  const [model, setModel] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await api.recommend();
        setRam(r.ram_gb);
        setRec(r.recommendation);
        setModel(r.recommendation.model);
        const m = await api.models();
        setModels(m.models);
      } catch {
        setRec({ tier: "mid", model: "llama3.2:3b", provider: "ollama" });
        setModel("llama3.2:3b");
      }
    })();
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.openWorkspace(path.trim());
      if (model) {
        await api.selectModel({ provider: rec?.provider || "ollama", model });
      }
      localStorage.setItem("freeagent-theme", theme);
      localStorage.setItem("freeagent-onboarded", "1");
      onDone(res.path);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wizard">
      <div className="wizard-card">
        <div className="brand">FreeAgent IDE</div>
        <h1>Welcome</h1>
        <p className="sub">
          Local-first multi-agent coding. Your code stays on this machine.
        </p>

        {ram != null && rec && (
          <div className="rec">
            Detected ~{ram} GB RAM · recommended <strong>{rec.model}</strong> ({rec.tier} tier)
          </div>
        )}

        <form onSubmit={submit}>
          <label>
            Project folder
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="E:\projects\my-app"
              required
            />
          </label>

          <label>
            Default model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {models.length === 0 && <option value={model}>{model}</option>}
              {models.map((m) => (
                <option key={`${m.provider}:${m.name}`} value={m.name}>
                  {m.provider}:{m.name}
                  {!m.available ? " (offline)" : ""}
                </option>
              ))}
            </select>
          </label>

          <label>
            Theme
            <select value={theme} onChange={(e) => setTheme(e.target.value)}>
              <option value="dark">Dark</option>
              <option value="system">System</option>
            </select>
          </label>

          {error && <div className="error">{error}</div>}

          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Opening…" : "Open workspace"}
          </button>
        </form>
      </div>

      <style>{`
        .wizard {
          min-height: 100%;
          display: grid;
          place-items: center;
          padding: 2rem;
          background:
            radial-gradient(ellipse at 20% 10%, rgba(61,214,198,0.12), transparent 45%),
            radial-gradient(ellipse at 80% 90%, rgba(122,162,247,0.1), transparent 40%),
            linear-gradient(160deg, #0b1016, #121820 55%, #0f1419);
        }
        .wizard-card {
          width: min(480px, 100%);
          background: rgba(18, 24, 32, 0.92);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 2rem;
          box-shadow: 0 24px 60px rgba(0,0,0,0.45);
          animation: rise 0.45s ease;
        }
        @keyframes rise {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: none; }
        }
        .brand {
          font-weight: 700;
          letter-spacing: 0.04em;
          color: var(--accent);
          font-size: 0.85rem;
          text-transform: uppercase;
        }
        h1 { margin: 0.4rem 0 0.35rem; font-size: 1.8rem; font-weight: 600; }
        .sub { color: var(--text-muted); margin: 0 0 1.25rem; line-height: 1.45; }
        .rec {
          background: var(--accent-glow);
          border: 1px solid var(--accent-dim);
          border-radius: var(--radius);
          padding: 0.65rem 0.75rem;
          margin-bottom: 1rem;
          font-size: 13px;
        }
        form { display: flex; flex-direction: column; gap: 0.85rem; }
        label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 13px; color: var(--text-muted); }
        .error { color: var(--danger); font-size: 13px; }
        button.primary { margin-top: 0.35rem; padding: 0.7rem; }
      `}</style>
    </div>
  );
}
