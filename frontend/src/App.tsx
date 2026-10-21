import { useCallback, useEffect, useState } from "react";
import { api, FileEntry } from "./api";
import { useWebSocket, WsEvent } from "./hooks/useWebSocket";
import { FileTree } from "./components/FileTree";
import { CodeEditor } from "./components/CodeEditor";
import { ChatPanel } from "./components/ChatPanel";
import { TerminalPane } from "./components/Terminal";
import { FirstRunWizard } from "./components/FirstRunWizard";
import { TopBar } from "./components/TopBar";

export default function App() {
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [models, setModels] = useState<{ name: string; provider: string }[]>([]);
  const [activeModel, setActiveModel] = useState("llama3.2:3b");
  const [running, setRunning] = useState(false);
  const [agentStatus, setAgentStatus] = useState("Idle");
  const [termEvents, setTermEvents] = useState<WsEvent[]>([]);
  const [chatEvents, setChatEvents] = useState<WsEvent[]>([]);

  const refreshTree = useCallback(async () => {
    try {
      const res = await api.tree();
      setEntries(res.entries);
    } catch {
      /* workspace may be closed */
    }
  }, []);

  const onEvent = useCallback(
    (ev: WsEvent) => {
      setChatEvents((prev) => [...prev.slice(-300), ev]);
      setTermEvents((prev) => [...prev.slice(-300), ev]);
      if (ev.type === "agent_started") setAgentStatus(String(ev.agent));
      if (ev.type === "session_finished" || ev.type === "session_error") setAgentStatus("Idle");
      if (ev.type === "file_written" || ev.type === "undo_applied" || ev.type === "workspace_opened") {
        void refreshTree();
      }
    },
    [refreshTree]
  );

  const { connected } = useWebSocket(onEvent);

  useEffect(() => {
    (async () => {
      try {
        const ws = await api.workspace();
        if (ws.path) {
          setWorkspace(ws.path);
          setShowWizard(false);
          await refreshTree();
        } else if (localStorage.getItem("freeagent-onboarded") === "1") {
          setShowWizard(true);
        }
        const m = await api.models();
        setModels(m.models.map((x) => ({ name: x.name, provider: x.provider })));
        const health = await api.health();
        const active = (health.models as { active?: { model?: string } })?.active;
        if (active?.model) setActiveModel(active.model);
      } catch {
        setShowWizard(true);
      }
    })();
  }, []);

  async function openFile(path: string) {
    const file = await api.readFile(path);
    setActivePath(path);
    setContent(file.content);
    setSavedContent(file.content);
  }

  async function saveFile() {
    if (!activePath) return;
    await api.writeFile(activePath, content);
    setSavedContent(content);
    await refreshTree();
  }

  async function handleWizardDone(path: string) {
    setWorkspace(path);
    setShowWizard(false);
    await refreshTree();
  }

  async function openFolderPrompt() {
    const path = window.prompt("Folder path to open", workspace || "");
    if (!path) return;
    const res = await api.openWorkspace(path);
    setWorkspace(res.path);
    setActivePath(null);
    setContent("");
    setSavedContent("");
    await refreshTree();
  }

  async function onModelChange(model: string, provider: string) {
    setActiveModel(model);
    await api.selectModel({ model, provider });
  }

  async function onUndo() {
    const list = await api.undos();
    if (!list.snapshots.length) {
      window.alert("No AI snapshots to undo");
      return;
    }
    const latest = list.snapshots[0];
    if (!window.confirm(`Undo ${latest.reason}?`)) return;
    await api.undo(latest.id);
    if (activePath) await openFile(activePath);
    await refreshTree();
  }

  async function onGitCommit() {
    const message = window.prompt("Commit message", "chore: update via FreeAgent");
    if (!message) return;
    const res = await api.gitCommit(message);
    window.alert(JSON.stringify(res));
  }

  if (showWizard) {
    return <FirstRunWizard onDone={handleWizardDone} />;
  }

  return (
    <div className="app-shell">
      <TopBar
        workspace={workspace}
        connected={connected}
        models={models}
        activeModel={activeModel}
        agentStatus={running ? agentStatus : "Idle"}
        onModelChange={onModelChange}
        onOpenFolder={openFolderPrompt}
        onUndo={onUndo}
        onGitCommit={onGitCommit}
      />
      <div className="main-grid">
        <aside className="col-tree">
          <FileTree entries={entries} activePath={activePath} onOpen={openFile} />
        </aside>
        <section className="col-center">
          <div className="editor-area">
            <CodeEditor
              path={activePath}
              value={content}
              onChange={setContent}
              onSave={saveFile}
              dirty={content !== savedContent}
            />
          </div>
          <div className="term-area">
            <TerminalPane events={termEvents} enabled={Boolean(workspace)} />
          </div>
        </section>
        <aside className="col-chat">
          <ChatPanel events={chatEvents} running={running} onRunningChange={setRunning} />
        </aside>
      </div>
      <footer className="statusbar">
        <span>{connected ? "Connected" : "Reconnecting…"}</span>
        <span>Local-first · No telemetry</span>
      </footer>
      <style>{`
        .app-shell { height: 100%; display: flex; flex-direction: column; }
        .main-grid {
          flex: 1;
          min-height: 0;
          display: grid;
          grid-template-columns: 240px 1fr 340px;
        }
        .col-tree, .col-chat { min-width: 0; border-right: 1px solid var(--border-soft); background: var(--bg-panel); }
        .col-chat { border-right: none; border-left: 1px solid var(--border-soft); }
        .col-center { min-width: 0; display: grid; grid-template-rows: 1fr 220px; }
        .editor-area, .term-area { min-height: 0; }
        .term-area { border-top: 1px solid var(--border); }
        .statusbar {
          height: var(--statusbar-h);
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 0.75rem;
          font-size: 11px;
          color: var(--text-muted);
          border-top: 1px solid var(--border);
          background: #0c1117;
        }
        @media (max-width: 960px) {
          .main-grid { grid-template-columns: 1fr; grid-template-rows: 160px 1fr 280px; }
          .col-center { grid-template-rows: 1fr 160px; }
        }
      `}</style>
    </div>
  );
}
