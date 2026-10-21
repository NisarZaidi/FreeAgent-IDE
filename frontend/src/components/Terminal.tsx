import { useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { api } from "../api";
import { WsEvent } from "../hooks/useWebSocket";

type Props = {
  events: WsEvent[];
  enabled: boolean;
};

export function TerminalPane({ events, enabled }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const sessionRef = useRef<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!hostRef.current || termRef.current) return;
    const term = new XTerm({
      theme: {
        background: "#0a0e13",
        foreground: "#d7e0ea",
        cursor: "#3dd6c6",
      },
      fontFamily: "IBM Plex Mono, monospace",
      fontSize: 12,
      convertEol: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    fit.fit();
    termRef.current = term;

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);

    term.onData((data) => {
      if (sessionRef.current) {
        void api.terminalInput(sessionRef.current, data);
      }
    });

    return () => {
      window.removeEventListener("resize", onResize);
      term.dispose();
      termRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!enabled || ready) return;
    (async () => {
      try {
        const res = await api.terminalStart();
        sessionRef.current = res.id;
        setReady(true);
        termRef.current?.writeln("\x1b[36mFreeAgent terminal ready.\x1b[0m");
      } catch (err) {
        termRef.current?.writeln(`\x1b[31mTerminal failed: ${String(err)}\x1b[0m`);
      }
    })();
  }, [enabled, ready]);

  useEffect(() => {
    const last = events[events.length - 1];
    if (!last || !termRef.current) return;
    if (last.type === "terminal_output" && last.data) {
      termRef.current.write(String(last.data));
    }
    if (last.type === "command_result") {
      termRef.current.writeln(`\r\n\x1b[33m$ ${last.command}\x1b[0m`);
      termRef.current.write(String(last.output || ""));
      termRef.current.writeln(`\r\n\x1b[90mexit ${last.exit_code}\x1b[0m`);
    }
  }, [events]);

  return (
    <div className="terminal-pane">
      <div className="panel-title">Terminal</div>
      <div className="term-host" ref={hostRef} />
      <style>{`
        .terminal-pane { height: 100%; display: flex; flex-direction: column; background: #0a0e13; }
        .panel-title {
          padding: 0.4rem 0.75rem;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--text-muted);
          border-bottom: 1px solid var(--border-soft);
        }
        .term-host { flex: 1; min-height: 0; padding: 0.35rem; }
      `}</style>
    </div>
  );
}
