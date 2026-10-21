import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { WsEvent } from "../hooks/useWebSocket";

type Msg = {
  id: string;
  agent: string;
  content: string;
  kind?: string;
};

type Pending = {
  id: string;
  action_type: string;
  agent: string;
  summary: string;
  payload?: Record<string, unknown>;
};

type Props = {
  events: WsEvent[];
  running: boolean;
  onRunningChange: (v: boolean) => void;
};

const AGENT_COLORS: Record<string, string> = {
  planner: "var(--planner)",
  coder: "var(--coder)",
  reviewer: "var(--reviewer)",
  tester: "var(--tester)",
  user: "var(--text)",
  system: "var(--text-muted)",
};

export function ChatPanel({ events, running, onRunningChange }: Props) {
  const [task, setTask] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [pending, setPending] = useState<Pending[]>([]);
  const [status, setStatus] = useState("Idle");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  useEffect(() => {
    for (const ev of events.slice(-1)) {
      if (ev.type === "agent_message") {
        setMessages((m) => [
          ...m,
          {
            id: `${Date.now()}-${Math.random()}`,
            agent: String(ev.agent),
            content: String(ev.content),
          },
        ]);
      } else if (ev.type === "agent_started") {
        setStatus(`${String(ev.agent)} working…`);
      } else if (ev.type === "session_started") {
        onRunningChange(true);
        setStatus("Agents started");
        setMessages((m) => [
          ...m,
          {
            id: `${Date.now()}-task`,
            agent: "user",
            content: String(ev.task),
          },
        ]);
      } else if (ev.type === "session_finished") {
        onRunningChange(false);
        setStatus("Done");
        setMessages((m) => [
          ...m,
          {
            id: `${Date.now()}-done`,
            agent: "system",
            content: "Session finished. Review diffs and approvals above.",
            kind: "system",
          },
        ]);
      } else if (ev.type === "session_error") {
        onRunningChange(false);
        setStatus("Error");
        setMessages((m) => [
          ...m,
          {
            id: `${Date.now()}-err`,
            agent: "system",
            content: `Error: ${String(ev.error)}`,
          },
        ]);
      } else if (ev.type === "approval_needed" && ev.action) {
        const a = ev.action as Pending;
        setPending((p) => (p.some((x) => x.id === a.id) ? p : [...p, a]));
      } else if (ev.type === "approval_resolved") {
        setPending((p) => p.filter((x) => x.id !== ev.action_id));
      }
    }
  }, [events, onRunningChange]);

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const res = await api.pending();
        setPending(res.pending);
      } catch {
        /* ignore */
      }
    }, 1500);
    return () => clearInterval(t);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!task.trim() || running) return;
    const value = task.trim();
    setTask("");
    onRunningChange(true);
    setStatus("Starting…");
    try {
      await api.runAgents(value);
    } catch (err) {
      onRunningChange(false);
      setStatus("Failed to start");
      setMessages((m) => [
        ...m,
        {
          id: `${Date.now()}-fail`,
          agent: "system",
          content: String(err),
        },
      ]);
    }
  }

  async function resolve(id: string, approved: boolean) {
    await api.approve(id, approved);
    setPending((p) => p.filter((x) => x.id !== id));
  }

  return (
    <div className="chat-panel">
      <div className="panel-title">
        Agents <span className="status">{status}</span>
      </div>

      {pending.length > 0 && (
        <div className="approvals">
          {pending.map((p) => (
            <div key={p.id} className="approval-card">
              <div className="approval-title">{p.summary}</div>
              <div className="approval-meta">
                {p.agent} · {p.action_type}
              </div>
              <div className="approval-actions">
                <button className="primary" onClick={() => resolve(p.id, true)}>
                  Approve
                </button>
                <button onClick={() => resolve(p.id, false)}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="messages">
        {messages.length === 0 && (
          <div className="hint">
            Describe a coding task. Planner → Coder → Reviewer → Tester will collaborate locally.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className="msg">
            <div className="agent" style={{ color: AGENT_COLORS[m.agent] || "var(--text)" }}>
              {m.agent}
            </div>
            <pre className="content">{m.content}</pre>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. Add a README and a hello.py script"
          rows={3}
          disabled={running}
        />
        <button className="primary" type="submit" disabled={running || !task.trim()}>
          {running ? "Running…" : "Run agents"}
        </button>
      </form>

      <style>{`
        .chat-panel { height: 100%; display: flex; flex-direction: column; background: var(--bg-panel); }
        .panel-title {
          padding: 0.65rem 0.75rem;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--text-muted);
          border-bottom: 1px solid var(--border-soft);
          display: flex; justify-content: space-between; align-items: center;
        }
        .status { text-transform: none; letter-spacing: 0; color: var(--accent); font-family: var(--font-mono); }
        .messages { flex: 1; overflow: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.85rem; }
        .hint { color: var(--text-muted); font-size: 13px; line-height: 1.5; }
        .msg .agent {
          font-size: 11px; font-weight: 600; text-transform: uppercase;
          letter-spacing: 0.06em; margin-bottom: 0.25rem;
        }
        .msg .content {
          margin: 0; white-space: pre-wrap; word-break: break-word;
          font-family: var(--font-mono); font-size: 12px; line-height: 1.45;
          color: var(--text);
        }
        .composer {
          border-top: 1px solid var(--border-soft);
          padding: 0.65rem;
          display: flex; flex-direction: column; gap: 0.5rem;
        }
        .composer textarea { resize: none; min-height: 72px; }
        .approvals {
          padding: 0.5rem 0.65rem 0;
          display: flex; flex-direction: column; gap: 0.5rem;
          max-height: 40%; overflow: auto;
        }
        .approval-card {
          border: 1px solid var(--warning);
          background: rgba(230, 180, 80, 0.08);
          border-radius: var(--radius);
          padding: 0.6rem;
        }
        .approval-title { font-weight: 600; font-size: 13px; }
        .approval-meta { color: var(--text-muted); font-size: 11px; margin: 0.25rem 0 0.5rem; }
        .approval-actions { display: flex; gap: 0.4rem; }
      `}</style>
    </div>
  );
}
