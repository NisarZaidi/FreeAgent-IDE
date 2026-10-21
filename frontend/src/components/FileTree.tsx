import { FileEntry } from "../api";

type Props = {
  entries: FileEntry[];
  activePath: string | null;
  onOpen: (path: string) => void;
};

export function FileTree({ entries, activePath, onOpen }: Props) {
  return (
    <div className="file-tree">
      <div className="panel-title">Explorer</div>
      <div className="tree-list">
        {entries.length === 0 && <div className="muted">Open a folder to begin</div>}
        {entries.map((e) => {
          const depth = e.path.split("/").length - 1;
          if (e.type === "dir") {
            return (
              <div
                key={e.path}
                className="tree-item dir"
                style={{ paddingLeft: 8 + depth * 12 }}
              >
                <span className="icon">▸</span> {e.name}
              </div>
            );
          }
          return (
            <button
              key={e.path}
              className={`tree-item file ${activePath === e.path ? "active" : ""}`}
              style={{ paddingLeft: 8 + depth * 12 }}
              onClick={() => onOpen(e.path)}
              title={e.path}
            >
              <span className="icon">·</span> {e.name}
            </button>
          );
        })}
      </div>
      <style>{`
        .file-tree { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
        .panel-title {
          padding: 0.65rem 0.75rem;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--text-muted);
          border-bottom: 1px solid var(--border-soft);
        }
        .tree-list { overflow: auto; flex: 1; padding: 0.35rem 0; }
        .tree-item {
          display: block;
          width: 100%;
          text-align: left;
          border: none;
          background: transparent;
          color: var(--text);
          padding: 0.22rem 0.5rem;
          border-radius: 0;
          font-family: var(--font-mono);
          font-size: 12px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .tree-item.dir { color: var(--text-muted); cursor: default; }
        .tree-item.file:hover { background: #1a222d; }
        .tree-item.file.active {
          background: var(--accent-glow);
          color: var(--accent);
        }
        .icon { opacity: 0.55; margin-right: 0.25rem; }
        .muted { color: var(--text-muted); padding: 0.75rem; font-size: 12px; }
      `}</style>
    </div>
  );
}
