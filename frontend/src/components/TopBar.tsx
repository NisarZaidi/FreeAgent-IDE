type Props = {
  workspace: string | null;
  connected: boolean;
  models: { name: string; provider: string }[];
  activeModel: string;
  agentStatus: string;
  onModelChange: (model: string, provider: string) => void;
  onOpenFolder: () => void;
  onUndo: () => void;
  onGitCommit: () => void;
};

export function TopBar({
  workspace,
  connected,
  models,
  activeModel,
  agentStatus,
  onModelChange,
  onOpenFolder,
  onUndo,
  onGitCommit,
}: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo">FA</span>
        <span className="name">FreeAgent IDE</span>
      </div>
      <div className="workspace" title={workspace || ""}>
        {workspace || "No workspace"}
      </div>
      <div className="controls">
        <select
          value={activeModel}
          onChange={(e) => {
            const m = models.find((x) => x.name === e.target.value);
            onModelChange(e.target.value, m?.provider || "ollama");
          }}
        >
          {models.length === 0 && <option value={activeModel}>{activeModel}</option>}
          {models.map((m) => (
            <option key={`${m.provider}:${m.name}`} value={m.name}>
              {m.provider}:{m.name}
            </option>
          ))}
        </select>
        <span className={`dot ${connected ? "on" : "off"}`} title={connected ? "WS connected" : "WS offline"} />
        <span className="agent-status">{agentStatus}</span>
        <button onClick={onOpenFolder}>Open folder</button>
        <button onClick={onUndo}>Undo AI</button>
        <button onClick={onGitCommit}>Commit</button>
      </div>
      <style>{`
        .topbar {
          height: var(--topbar-h);
          display: flex;
          align-items: center;
          gap: 1rem;
          padding: 0 0.75rem;
          border-bottom: 1px solid var(--border);
          background: linear-gradient(90deg, #10161e, #141b24);
        }
        .brand { display: flex; align-items: center; gap: 0.5rem; min-width: 160px; }
        .logo {
          width: 26px; height: 26px; border-radius: 7px;
          display: grid; place-items: center;
          background: linear-gradient(135deg, var(--accent), #2a7fff);
          color: #041018; font-weight: 700; font-size: 11px;
        }
        .name { font-weight: 600; letter-spacing: 0.02em; }
        .workspace {
          flex: 1;
          font-family: var(--font-mono);
          font-size: 12px;
          color: var(--text-muted);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .controls { display: flex; align-items: center; gap: 0.45rem; }
        .controls select { max-width: 220px; font-size: 12px; }
        .dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--danger);
        }
        .dot.on { background: var(--success); box-shadow: 0 0 8px rgba(127,217,98,0.5); }
        .agent-status {
          font-size: 11px;
          color: var(--text-muted);
          min-width: 90px;
          font-family: var(--font-mono);
        }
      `}</style>
    </header>
  );
}
