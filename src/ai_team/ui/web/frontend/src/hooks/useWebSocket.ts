import { useCallback, useEffect, useRef, useState } from "react";
import { getWsBase } from "../config";
import type { MonitorState } from "../types";

const WS_BASE = getWsBase();

interface WSMessage {
  type: string;
  data?: unknown;
  run_id?: string;
  project_id?: string;
  message?: string;
  run_status?: string;
}

export type RunWsStatus =
  | "idle"
  | "connecting"
  | "running"
  | "awaiting_human"
  | "complete"
  | "cancelled"
  | "error";

export function useRunWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const statusRef = useRef<RunWsStatus>("idle");
  const [monitor, setMonitor] = useState<MonitorState | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunWsStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hitlPayload, setHitlPayload] = useState<Record<string, unknown> | null>(null);

  const setRunStatus = useCallback((next: RunWsStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const closeSocket = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => () => closeSocket(), [closeSocket]);

  const handleMessage = useCallback(
    (msg: WSMessage) => {
      if (msg.type === "run_started" && msg.run_id) {
        setRunId(msg.run_id);
        setProjectId(msg.project_id ?? msg.run_id);
      } else if (msg.type === "monitor_update" && msg.data) {
        setMonitor(msg.data as MonitorState);
      } else if (msg.type === "event" && msg.data) {
        setEvents((prev) => [...prev, msg.data]);
      } else if (msg.type === "result" && msg.data) {
        setEvents((prev) => [...prev, msg.data]);
      } else if (msg.type === "hitl_required" && msg.data) {
        setHitlPayload(msg.data as Record<string, unknown>);
        setRunStatus("awaiting_human");
      } else if (msg.type === "complete") {
        const cancelled = msg.run_status === "cancelled";
        setRunStatus(cancelled ? "cancelled" : "complete");
        if (msg.project_id) setProjectId(msg.project_id);
        if (msg.data) setMonitor(msg.data as MonitorState);
      } else if (msg.type === "error") {
        setRunStatus("error");
        setErrorMessage(msg.message ?? "Run failed");
      }
    },
    [setRunStatus],
  );

  const startRun = useCallback(
    (
      backend: string,
      profile: string,
      description: string,
      complexity: string,
      estimateUsd?: number | null,
      comparisonId?: string | null,
    ) => {
      closeSocket();
      setRunStatus("connecting");
      setEvents([]);
      setMonitor(null);
      setRunId(null);
      setProjectId(null);
      setErrorMessage(null);
      setHitlPayload(null);

      const ws = new WebSocket(`${WS_BASE}/ws/run`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            backend,
            profile,
            description,
            complexity,
            estimate_usd: estimateUsd ?? null,
            comparison_id: comparisonId ?? null,
          }),
        );
        setRunStatus("running");
      };

      ws.onmessage = (e) => handleMessage(JSON.parse(e.data) as WSMessage);

      ws.onerror = () => {
        setRunStatus("error");
        setErrorMessage("WebSocket connection failed");
      };

      ws.onclose = () => {
        if (statusRef.current === "running") setRunStatus("complete");
      };
    },
    [closeSocket, handleMessage, setRunStatus],
  );

  const disconnect = useCallback(() => {
    closeSocket();
    setRunStatus("idle");
  }, [closeSocket, setRunStatus]);

  return {
    monitor,
    events,
    runId,
    projectId,
    status,
    errorMessage,
    hitlPayload,
    startRun,
    disconnect,
  };
}

export function useMonitorWebSocket(runId: string | null) {
  const [monitor, setMonitor] = useState<MonitorState | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [hitlPayload, setHitlPayload] = useState<Record<string, unknown> | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setMonitor(null);
      setRunStatus(null);
      setHitlPayload(null);
      setErrorMessage(null);
      return;
    }

    const ws = new WebSocket(`${WS_BASE}/ws/monitor/${runId}`);

    ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data);
      if (msg.type === "monitor_update" && msg.data) {
        const data = msg.data as MonitorState & { run_status?: string };
        setMonitor(data);
        if (data.run_status) setRunStatus(data.run_status);
      } else if (msg.type === "hitl_required" && msg.data) {
        setHitlPayload(msg.data as Record<string, unknown>);
        setRunStatus("awaiting_human");
      } else if (msg.type === "complete" && msg.data) {
        setMonitor(msg.data as MonitorState);
        setRunStatus(msg.run_status === "cancelled" ? "cancelled" : "complete");
      } else if (msg.type === "error") {
        setErrorMessage(msg.message ?? "Monitor error");
        setRunStatus("error");
      }
    };

    return () => ws.close();
  }, [runId]);

  return { monitor, runStatus, hitlPayload, errorMessage };
}
