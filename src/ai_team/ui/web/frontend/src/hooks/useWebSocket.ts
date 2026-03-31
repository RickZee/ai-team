import { useCallback, useEffect, useRef, useState } from "react";
import type { MonitorState } from "../types";

const WS_BASE = `ws://${window.location.hostname}:8421`;

interface WSMessage {
  type: string;
  data?: unknown;
  run_id?: string;
  message?: string;
}

export function useRunWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [monitor, setMonitor] = useState<MonitorState | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "connecting" | "running" | "complete" | "error">("idle");

  const startRun = useCallback(
    (backend: string, profile: string, description: string, complexity: string) => {
      setStatus("connecting");
      setEvents([]);
      setMonitor(null);

      const ws = new WebSocket(`${WS_BASE}/ws/run`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ backend, profile, description, complexity }));
        setStatus("running");
      };

      ws.onmessage = (e) => {
        const msg: WSMessage = JSON.parse(e.data);
        if (msg.type === "run_started" && msg.run_id) {
          setRunId(msg.run_id);
        } else if (msg.type === "monitor_update" && msg.data) {
          setMonitor(msg.data as MonitorState);
        } else if (msg.type === "event" && msg.data) {
          setEvents((prev) => [...prev, msg.data]);
        } else if (msg.type === "result" && msg.data) {
          setEvents((prev) => [...prev, msg.data]);
        } else if (msg.type === "complete") {
          setStatus("complete");
          if (msg.data) setMonitor(msg.data as MonitorState);
        } else if (msg.type === "error") {
          setStatus("error");
        }
      };

      ws.onerror = () => setStatus("error");
      ws.onclose = () => {
        if (status === "running") setStatus("complete");
      };
    },
    [status],
  );

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return { monitor, events, runId, status, startRun, disconnect };
}

export function useMonitorWebSocket(runId: string | null) {
  const [monitor, setMonitor] = useState<MonitorState | null>(null);

  useEffect(() => {
    if (!runId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/monitor/${runId}`);

    ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data);
      if (msg.type === "monitor_update" && msg.data) {
        setMonitor(msg.data as MonitorState);
      }
    };

    return () => ws.close();
  }, [runId]);

  return monitor;
}
