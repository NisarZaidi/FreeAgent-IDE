import { useEffect, useRef, useState, useCallback } from "react";
import { wsUrl } from "../api";

export type WsEvent = Record<string, unknown> & { type: string };

export function useWebSocket(onEvent?: (ev: WsEvent) => void) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<WsEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let closed = false;
    let retry: number | undefined;

    const connect = () => {
      if (closed) return;
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        retry = window.setTimeout(connect, 2000);
      };
      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data) as WsEvent;
          setEvents((prev) => [...prev.slice(-400), data]);
          onEventRef.current?.(data);
        } catch {
          /* ignore */
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      wsRef.current?.close();
    };
  }, []);

  const send = useCallback((payload: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  return { connected, events, send, clearEvents: () => setEvents([]) };
}
