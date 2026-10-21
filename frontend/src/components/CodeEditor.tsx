import Editor from "@monaco-editor/react";

type Props = {
  path: string | null;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  dirty: boolean;
};

function languageFromPath(path: string | null): string {
  if (!path) return "plaintext";
  const ext = path.split(".").pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    py: "python",
    json: "json",
    md: "markdown",
    css: "css",
    html: "html",
    sh: "shell",
    ps1: "powershell",
    yml: "yaml",
    yaml: "yaml",
    toml: "ini",
    rs: "rust",
    go: "go",
  };
  return map[ext || ""] || "plaintext";
}

export function CodeEditor({ path, value, onChange, onSave, dirty }: Props) {
  return (
    <div className="editor-wrap" onKeyDown={(e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        onSave();
      }
    }}>
      <div className="editor-tabs">
        {path ? (
          <div className={`tab active ${dirty ? "dirty" : ""}`}>
            {path.split("/").pop()}
            {dirty ? " •" : ""}
          </div>
        ) : (
          <div className="tab muted">No file open</div>
        )}
        <div className="spacer" />
        <button disabled={!path || !dirty} onClick={onSave}>
          Save
        </button>
      </div>
      <div className="editor-body">
        {path ? (
          <Editor
            height="100%"
            theme="vs-dark"
            language={languageFromPath(path)}
            value={value}
            onChange={(v) => onChange(v ?? "")}
            options={{
              fontFamily: "IBM Plex Mono, monospace",
              fontSize: 13,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              padding: { top: 12 },
            }}
          />
        ) : (
          <div className="empty">Select a file from the explorer</div>
        )}
      </div>
      <style>{`
        .editor-wrap { height: 100%; display: flex; flex-direction: column; background: #0d1117; }
        .editor-tabs {
          display: flex; align-items: center; gap: 0.5rem;
          padding: 0 0.5rem; height: 36px;
          border-bottom: 1px solid var(--border-soft);
          background: var(--bg-panel);
        }
        .tab {
          padding: 0.35rem 0.75rem;
          font-family: var(--font-mono);
          font-size: 12px;
          border-bottom: 2px solid var(--accent);
        }
        .tab.muted { border-bottom: none; color: var(--text-muted); }
        .tab.dirty { color: var(--warning); }
        .spacer { flex: 1; }
        .editor-body { flex: 1; min-height: 0; }
        .empty {
          height: 100%; display: grid; place-items: center;
          color: var(--text-muted); letter-spacing: 0.02em;
        }
      `}</style>
    </div>
  );
}
